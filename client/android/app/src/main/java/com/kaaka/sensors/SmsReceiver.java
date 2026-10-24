package com.kaaka.sensors;

import android.app.ActivityOptions;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.database.Cursor;
import android.media.AudioAttributes;
import android.media.RingtoneManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.os.VibratorManager;
import android.provider.ContactsContract;
import android.provider.Telephony;
import android.telephony.SmsMessage;
import android.util.Log;
import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;

public class SmsReceiver extends BroadcastReceiver {
    private static final String TAG = "SmsReceiver";
    private static final String TARGET_PHONE_SUFFIX = "9495364448";
    private static final String TARGET_PHONE_SUFFIX_ALT = "9995283835";
    
    // Urgent Alert Channel (Authorized Contact ONLY)
    private static final String URGENT_CHANNEL_ID = "sms_urgent_alert_channel_v4";
    private static final int URGENT_NOTIFICATION_ID = 9495;

    // General SMS Channel (All Other Contacts)
    private static final String GENERAL_CHANNEL_ID = "general_sms_channel";

    // Deduplication tracking
    private static long lastEmergencyTimestamp = 0;
    private static String lastEmergencyHash = "";

    private static long lastNormalTimestamp = 0;
    private static String lastNormalHash = "";

    @Override
    public void onReceive(Context context, Intent intent) {
        String action = (intent != null) ? intent.getAction() : null;
        if (Telephony.Sms.Intents.SMS_DELIVER_ACTION.equals(action) ||
            Telephony.Sms.Intents.SMS_RECEIVED_ACTION.equals(action) ||
            "com.kaaka.sensors.TEST_INCOMING_SMS".equals(action) ||
            "com.example.sampleapp.TEST_INCOMING_SMS".equals(action)) {

            String sender = null;
            String completeMessage = "";
            long timestamp = System.currentTimeMillis();

            if ("com.kaaka.sensors.TEST_INCOMING_SMS".equals(action) ||
                "com.example.sampleapp.TEST_INCOMING_SMS".equals(action)) {
                sender = intent.getStringExtra("sender");
                completeMessage = intent.getStringExtra("message");
                if (completeMessage == null) completeMessage = "Test message";
            } else {
                SmsMessage[] messages = Telephony.Sms.Intents.getMessagesFromIntent(intent);
                if (messages != null && messages.length > 0) {
                    StringBuilder fullBody = new StringBuilder();
                    sender = messages[0].getDisplayOriginatingAddress();
                    timestamp = messages[0].getTimestampMillis();

                    for (SmsMessage message : messages) {
                        if (message != null) {
                            String part = message.getDisplayMessageBody();
                            if (part != null) {
                                fullBody.append(part);
                            }
                        }
                    }
                    completeMessage = fullBody.toString();
                }
            }

            if (sender == null) return;

            String digitsOnly = sender.replaceAll("[^0-9]", "");
            Log.d(TAG, "Incoming SMS action [" + action + "] from sender: " + sender + " (digits: " + digitsOnly + ")");

            // 1. As default SMS app, save incoming SMS to telephony inbox
            if (Telephony.Sms.Intents.SMS_DELIVER_ACTION.equals(action)) {
                saveSmsToInbox(context, sender, completeMessage, timestamp);
            }

            // 2. CHECK SENDER & CONTENT: Is it an authorized emergency contact or emergency trigger keyword?
            boolean isAuthorizedSender = digitsOnly.endsWith(TARGET_PHONE_SUFFIX) || digitsOnly.endsWith(TARGET_PHONE_SUFFIX_ALT);
            String lowerMsg = completeMessage != null ? completeMessage.toLowerCase() : "";
            boolean isEmergencyTrigger = lowerMsg.contains("call") || lowerMsg.contains("emergency") || lowerMsg.contains("alert") || lowerMsg.contains("kaaka");

            if (!isAuthorizedSender && !isEmergencyTrigger) {
                // Regular contact: post normal notification (NO auto-open, NO alarm vibration)
                Log.d(TAG, "Regular SMS from " + sender + ": posting standard notification.");
                postNormalSmsNotification(context, sender, completeMessage, timestamp);
                return;
            }

            // 3. AUTHORIZED EMERGENCY CONTACT (9495364448):
            // Deduplicate within 4 seconds for identical sender + message
            String messageKey = sender + ":" + completeMessage;
            long now = System.currentTimeMillis();
            if (now - lastEmergencyTimestamp < 4000 && messageKey.equals(lastEmergencyHash)) {
                Log.d(TAG, "Duplicate emergency SMS event ignored within debounce window.");
                return;
            }
            lastEmergencyTimestamp = now;
            lastEmergencyHash = messageKey;

            Log.d(TAG, "🚨 MATCHED TARGET NUMBER (" + TARGET_PHONE_SUFFIX + ")! Triggering app auto-open, urgent notification, and alarm vibration.");

            // Function A: Instantly bring app to foreground (zero delay before anything else)
            launchMainActivity(context, sender, completeMessage);

            // Function B: Wake up screen and acquire temporary wake lock
            acquireWakeLock(context);

            // Function C: Trigger aggressive emergency vibration
            triggerEmergencyVibration(context);

            // Function D: Post High-Priority Heads-Up Notification with FullScreenIntent
            postHighPriorityNotification(context, sender, completeMessage);

            // Function E: Notify Capacitor frontend
            DefaultSmsPlugin.handleIncomingSms(sender, completeMessage, timestamp);
        }
    }

    private void saveSmsToInbox(Context context, String sender, String message, long timestamp) {
        try {
            ContentValues values = new ContentValues();
            values.put(Telephony.Sms.Inbox.ADDRESS, sender != null ? sender : "Unknown");
            values.put(Telephony.Sms.Inbox.BODY, message != null ? message : "");
            values.put(Telephony.Sms.Inbox.DATE, timestamp > 0 ? timestamp : System.currentTimeMillis());
            values.put(Telephony.Sms.Inbox.READ, 0);
            context.getContentResolver().insert(Telephony.Sms.Inbox.CONTENT_URI, values);
            Log.d(TAG, "Saved SMS into telephony inbox for: " + sender);
        } catch (Exception e) {
            Log.e(TAG, "Error saving SMS to inbox", e);
        }
    }

    private void postNormalSmsNotification(Context context, String sender, String message, long timestamp) {
        try {
            // Deduplicate normal notification within 3 seconds
            String key = (sender != null ? sender : "") + ":" + (message != null ? message : "");
            long now = System.currentTimeMillis();
            if (now - lastNormalTimestamp < 3000 && key.equals(lastNormalHash)) {
                return;
            }
            lastNormalTimestamp = now;
            lastNormalHash = key;

            NotificationManager nm = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm == null) return;

            // Create standard messages notification channel for Android O+
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                NotificationChannel channel = nm.getNotificationChannel(GENERAL_CHANNEL_ID);
                if (channel == null) {
                    channel = new NotificationChannel(
                        GENERAL_CHANNEL_ID,
                        "Messages",
                        NotificationManager.IMPORTANCE_HIGH
                    );
                    channel.setDescription("Incoming SMS text messages");
                    channel.enableLights(true);
                    channel.enableVibration(true);

                    Uri defaultSound = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION);
                    AudioAttributes audioAttributes = new AudioAttributes.Builder()
                        .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                        .setUsage(AudioAttributes.USAGE_NOTIFICATION)
                        .build();
                    channel.setSound(defaultSound, audioAttributes);

                    nm.createNotificationChannel(channel);
                }
            }

            // Intent to open app if user taps notification
            Intent openIntent = new Intent(context, MainActivity.class);
            openIntent.addFlags(
                Intent.FLAG_ACTIVITY_NEW_TASK |
                Intent.FLAG_ACTIVITY_SINGLE_TOP
            );
            openIntent.putExtra("normal_sms_sender", sender);
            openIntent.putExtra("normal_sms_message", message);

            int flags = PendingIntent.FLAG_UPDATE_CURRENT;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                flags |= PendingIntent.FLAG_IMMUTABLE;
            }

            int notifId = (sender != null) ? sender.hashCode() : (int) System.currentTimeMillis();
            PendingIntent pendingIntent = PendingIntent.getActivity(
                context,
                notifId,
                openIntent,
                flags
            );

            String displayName = resolveContactName(context, sender);

            NotificationCompat.Builder builder = new NotificationCompat.Builder(context, GENERAL_CHANNEL_ID)
                .setSmallIcon(android.R.drawable.sym_action_chat)
                .setContentTitle(displayName)
                .setContentText(message)
                .setStyle(new NotificationCompat.BigTextStyle().bigText(message))
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setCategory(NotificationCompat.CATEGORY_MESSAGE)
                .setAutoCancel(true)
                .setContentIntent(pendingIntent);

            NotificationManagerCompat.from(context).notify(notifId, builder.build());
            Log.d(TAG, "Standard notification posted for sender: " + displayName);
        } catch (Exception e) {
            Log.e(TAG, "Failed to post standard SMS notification", e);
        }
    }

    private String resolveContactName(Context context, String address) {
        if (address == null || address.trim().isEmpty()) {
            return "Unknown";
        }
        try {
            Uri uri = Uri.withAppendedPath(ContactsContract.PhoneLookup.CONTENT_FILTER_URI, Uri.encode(address));
            String[] projection = new String[]{ContactsContract.PhoneLookup.DISPLAY_NAME};
            try (Cursor cursor = context.getContentResolver().query(uri, projection, null, null, null)) {
                if (cursor != null && cursor.moveToFirst()) {
                    int nameIdx = cursor.getColumnIndex(ContactsContract.PhoneLookup.DISPLAY_NAME);
                    if (nameIdx >= 0) {
                        String name = cursor.getString(nameIdx);
                        if (name != null && !name.trim().isEmpty()) {
                            return name;
                        }
                    }
                }
            }
        } catch (Exception e) {
            // Permission or resolution error, fallback to raw address
        }
        return address;
    }

    private void acquireWakeLock(Context context) {
        try {
            PowerManager pm = (PowerManager) context.getSystemService(Context.POWER_SERVICE);
            if (pm != null) {
                PowerManager.WakeLock wakeLock = pm.newWakeLock(
                    PowerManager.FULL_WAKE_LOCK |
                    PowerManager.ACQUIRE_CAUSES_WAKEUP |
                    PowerManager.ON_AFTER_RELEASE,
                    "kaaka:SmsUrgentWakeLock"
                );
                wakeLock.acquire(10000);
            }
        } catch (Exception e) {
            Log.e(TAG, "WakeLock error", e);
        }
    }

    private void triggerEmergencyVibration(Context context) {
        try {
            Vibrator vibrator;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                VibratorManager vm = (VibratorManager) context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE);
                vibrator = (vm != null) ? vm.getDefaultVibrator() : (Vibrator) context.getSystemService(Context.VIBRATOR_SERVICE);
            } else {
                vibrator = (Vibrator) context.getSystemService(Context.VIBRATOR_SERVICE);
            }

            if (vibrator != null && vibrator.hasVibrator()) {
                long[] pattern = { 0, 800, 200, 800, 200, 1000, 200, 1000 };
                AudioAttributes audioAttributes = new AudioAttributes.Builder()
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .setUsage(AudioAttributes.USAGE_ALARM)
                    .build();

                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    vibrator.vibrate(VibrationEffect.createWaveform(pattern, -1), audioAttributes);
                } else {
                    vibrator.vibrate(pattern, -1);
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "Emergency vibrator error", e);
        }
    }

    private void postHighPriorityNotification(Context context, String sender, String message) {
        try {
            NotificationManager nm = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm == null) return;

            // Create high priority notification channel for Android O+
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                NotificationChannel channel = new NotificationChannel(
                    URGENT_CHANNEL_ID,
                    "Emergency SMS Alerts",
                    NotificationManager.IMPORTANCE_HIGH
                );
                channel.setDescription("Critical notifications for incoming SMS from " + TARGET_PHONE_SUFFIX);
                channel.enableLights(true);
                channel.enableVibration(true);
                channel.setVibrationPattern(new long[]{ 0, 800, 200, 800, 200, 1000 });
                channel.setLockscreenVisibility(android.app.Notification.VISIBILITY_PUBLIC);
                channel.setBypassDnd(true);

                Uri alarmSound = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION);
                if (alarmSound == null) {
                    alarmSound = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE);
                }
                AudioAttributes audioAttributes = new AudioAttributes.Builder()
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .setUsage(AudioAttributes.USAGE_ALARM)
                    .build();
                channel.setSound(alarmSound, audioAttributes);

                nm.createNotificationChannel(channel);
            }

            // PendingIntent for clicking or full-screen launch
            Intent activityIntent = new Intent(context, MainActivity.class);
            activityIntent.addFlags(
                Intent.FLAG_ACTIVITY_NEW_TASK |
                Intent.FLAG_ACTIVITY_CLEAR_TOP |
                Intent.FLAG_ACTIVITY_SINGLE_TOP |
                Intent.FLAG_ACTIVITY_REORDER_TO_FRONT
            );
            activityIntent.putExtra("sms_sender", sender);
            activityIntent.putExtra("sms_message", message);

            int flags = PendingIntent.FLAG_UPDATE_CURRENT;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                flags |= PendingIntent.FLAG_IMMUTABLE;
            }

            Bundle optsBundle = null;
            if (Build.VERSION.SDK_INT >= 34) { // Android 14+
                ActivityOptions options = ActivityOptions.makeBasic();
                options.setPendingIntentBackgroundActivityStartMode(
                    ActivityOptions.MODE_BACKGROUND_ACTIVITY_START_ALLOWED
                );
                options.setPendingIntentCreatorBackgroundActivityStartMode(
                    ActivityOptions.MODE_BACKGROUND_ACTIVITY_START_ALLOWED
                );
                optsBundle = options.toBundle();
            }

            PendingIntent pendingIntent = (optsBundle != null)
                ? PendingIntent.getActivity(context, URGENT_NOTIFICATION_ID, activityIntent, flags, optsBundle)
                : PendingIntent.getActivity(context, URGENT_NOTIFICATION_ID, activityIntent, flags);

            NotificationCompat.Builder builder = new NotificationCompat.Builder(context, URGENT_CHANNEL_ID)
                .setSmallIcon(android.R.drawable.ic_dialog_alert)
                .setContentTitle("🚨 Emergency Alert (" + TARGET_PHONE_SUFFIX + ")")
                .setContentText(message)
                .setStyle(new NotificationCompat.BigTextStyle().bigText(message))
                .setPriority(NotificationCompat.PRIORITY_MAX)
                .setCategory(NotificationCompat.CATEGORY_ALARM)
                .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
                .setAutoCancel(true)
                .setOngoing(false)
                .setContentIntent(pendingIntent)
                .setFullScreenIntent(pendingIntent, true)
                .setVibrate(new long[]{ 0, 800, 200, 800, 200, 1000 });

            NotificationManagerCompat.from(context).notify(URGENT_NOTIFICATION_ID, builder.build());
            Log.d(TAG, "High-priority emergency call-category notification posted successfully.");
        } catch (Exception e) {
            Log.e(TAG, "Emergency notification post failed", e);
        }
    }

    private void launchMainActivity(Context context, String sender, String message) {
        Intent launchIntent = new Intent(context, MainActivity.class);
        launchIntent.addFlags(
            Intent.FLAG_ACTIVITY_NEW_TASK |
            Intent.FLAG_ACTIVITY_CLEAR_TOP |
            Intent.FLAG_ACTIVITY_SINGLE_TOP |
            Intent.FLAG_ACTIVITY_REORDER_TO_FRONT |
            Intent.FLAG_ACTIVITY_NO_ANIMATION
        );
        launchIntent.putExtra("sms_sender", sender);
        launchIntent.putExtra("sms_message", message);

        Bundle optsBundle = null;
        if (Build.VERSION.SDK_INT >= 34) { // Android 14+
            ActivityOptions options = ActivityOptions.makeBasic();
            options.setPendingIntentBackgroundActivityStartMode(
                ActivityOptions.MODE_BACKGROUND_ACTIVITY_START_ALLOWED
            );
            options.setPendingIntentCreatorBackgroundActivityStartMode(
                ActivityOptions.MODE_BACKGROUND_ACTIVITY_START_ALLOWED
            );
            optsBundle = options.toBundle();
        }

        // 1. Try PendingIntent with background activity start mode allowed (Android 10 - 14+)
        try {
            int flags = PendingIntent.FLAG_UPDATE_CURRENT;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                flags |= PendingIntent.FLAG_IMMUTABLE;
            }
            PendingIntent pi = (optsBundle != null)
                ? PendingIntent.getActivity(context, URGENT_NOTIFICATION_ID + 50, launchIntent, flags, optsBundle)
                : PendingIntent.getActivity(context, URGENT_NOTIFICATION_ID + 50, launchIntent, flags);

            if (optsBundle != null) {
                pi.send(context, 0, null, null, null, null, optsBundle);
            } else {
                pi.send();
            }
            Log.d(TAG, "Launched MainActivity via PendingIntent.send()");
        } catch (Exception e) {
            Log.e(TAG, "PendingIntent launch failed", e);
        }

        // 2. Also execute direct startActivity with NEW_TASK & REORDER_TO_FRONT with options bundle
        try {
            if (optsBundle != null) {
                context.startActivity(launchIntent, optsBundle);
            } else {
                context.startActivity(launchIntent);
            }
            Log.d(TAG, "Launched MainActivity via context.startActivity()");
        } catch (Exception e) {
            Log.e(TAG, "Direct startActivity failed", e);
        }

        // 3. Repeated ultra-fast foreground re-assertion to overcome in-call dialers and post-call screens (Truecaller)
        Intent reorderIntent = new Intent(context, MainActivity.class);
        reorderIntent.addFlags(
            Intent.FLAG_ACTIVITY_NEW_TASK |
            Intent.FLAG_ACTIVITY_REORDER_TO_FRONT |
            Intent.FLAG_ACTIVITY_SINGLE_TOP |
            Intent.FLAG_ACTIVITY_NO_ANIMATION
        );

        final Bundle finalOpts = optsBundle;
        final Context appContext = context.getApplicationContext();
        Handler handler = new Handler(Looper.getMainLooper());
        int[] retryDelays = { 50, 150, 350, 700, 1200, 2000, 3500 };
        for (int delay : retryDelays) {
            handler.postDelayed(() -> {
                try {
                    if (finalOpts != null) {
                        appContext.startActivity(reorderIntent, finalOpts);
                    } else {
                        appContext.startActivity(reorderIntent);
                    }
                    Log.d(TAG, "Re-asserted MainActivity foreground after " + delay + "ms delay.");
                } catch (Exception e) {
                    Log.w(TAG, "Delayed activity launch attempt failed at " + delay + "ms: " + e.getMessage());
                }
            }, delay);
        }
    }
}
