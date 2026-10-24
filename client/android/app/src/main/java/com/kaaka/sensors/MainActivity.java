package com.kaaka.sensors;

import android.content.Context;
import android.content.Intent;
import android.media.AudioAttributes;
import android.os.Build;
import android.os.Bundle;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.os.VibratorManager;
import android.util.Log;
import android.view.WindowManager;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    private static final String TAG = "MainActivity";
    private static long lastProcessedSmsTime = 0;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(KaakaSensorsPlugin.class);
        registerPlugin(DirectSmsPlugin.class);
        registerPlugin(DefaultSmsPlugin.class);
        registerPlugin(KaakaSetupPlugin.class);
        super.onCreate(savedInstanceState);

        hideStatusBar();
        unlockAndTurnOnScreen();
        processIntent(getIntent());
    }

    @Override
    public void onResume() {
        super.onResume();
        hideStatusBar();
        // Do not request the default-SMS role here: if the user declined it permanently, Android
        // denies instantly, onResume runs again and the request loops (~20/s), freezing the UI.
        // The receiver screen has an explicit button for it (DefaultSmsPlugin.requestDefaultSms).
        processIntent(getIntent());
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            hideStatusBar();
        }
    }

    private void hideStatusBar() {
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN);
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);
        WindowInsetsControllerCompat controller = WindowCompat.getInsetsController(getWindow(), getWindow().getDecorView());
        if (controller != null) {
            controller.hide(WindowInsetsCompat.Type.statusBars());
            controller.setSystemBarsBehavior(WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
        }
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        unlockAndTurnOnScreen();
        processIntent(intent);
    }

    private void processIntent(Intent intent) {
        if (intent == null) return;
        if ("com.kaaka.sensors.STOP_BEACON".equals(intent.getAction())) {
            Log.d(TAG, "STOP_BEACON intent received in MainActivity");
            DefaultSmsPlugin.triggerStopBeacon();
            return;
        }
        if (intent.hasExtra("sms_sender")) {
            String sender = intent.getStringExtra("sms_sender");
            String message = intent.getStringExtra("sms_message");
            long now = System.currentTimeMillis();
            if (now - lastProcessedSmsTime > 3000) {
                lastProcessedSmsTime = now;
                Log.d(TAG, "Processing SMS intent in MainActivity: " + sender + " -> " + message);
                DefaultSmsPlugin.handleIncomingSms(sender, message, now);
                triggerVibration();
            } else {
                Log.d(TAG, "Debounced duplicate SMS intent in MainActivity (<3s)");
            }
            intent.removeExtra("sms_sender");
            intent.removeExtra("sms_message");
        }
    }

    private void triggerVibration() {
        try {
            Vibrator vibrator;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                VibratorManager vm = (VibratorManager) getSystemService(Context.VIBRATOR_MANAGER_SERVICE);
                vibrator = (vm != null) ? vm.getDefaultVibrator() : (Vibrator) getSystemService(Context.VIBRATOR_SERVICE);
            } else {
                vibrator = (Vibrator) getSystemService(Context.VIBRATOR_SERVICE);
            }

            if (vibrator != null && vibrator.hasVibrator()) {
                long[] pattern = { 0, 800, 200, 800, 200, 1000 };
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
            Log.e(TAG, "MainActivity vibrator error", e);
        }
    }

    private void unlockAndTurnOnScreen() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(true);
            setTurnScreenOn(true);
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            setInheritShowWhenLocked(true);
        }
        getWindow().addFlags(
            WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED |
            WindowManager.LayoutParams.FLAG_DISMISS_KEYGUARD |
            WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON |
            WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON
        );
    }
}
