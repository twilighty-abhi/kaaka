package com.kaaka.sensors;

import android.Manifest;
import android.content.Context;
import android.content.pm.PackageManager;
import android.location.Location;
import android.location.LocationManager;
import android.os.Build;
import android.os.CancellationSignal;
import android.os.Handler;
import android.os.Looper;
import android.telephony.SmsManager;
import android.telephony.SubscriptionManager;
import android.util.Log;
import java.util.ArrayList;
import java.util.Locale;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Sends the first "Kaaka Alert" report straight from native code when the Kaaka number replies.
 * Android 14+ blocks apps from opening themselves from the background, so the web beacon may not
 * start until the user taps the alarm notification; this guarantees at least one location report.
 * Format matches the web report so the gateway ("Kaaka Alert") and dashboard (Coords/Maps) parse it.
 */
final class NativeAlert {
    private static final String TAG = "KaakaNativeAlert";

    private NativeAlert() {}

    private static final long FRESH_MS = 2 * 60_000;
    private static final long FIX_TIMEOUT_MS = 8_000;

    /**
     * Uses a recent last-known fix if there is one, otherwise asks for a current fix (up to 8 s),
     * then sends. {@code done} runs after sending (used to finish the receiver's goAsync()).
     */
    static void send(Context context, String gatewayNumber, Runnable done) {
        if (gatewayNumber == null || gatewayNumber.trim().isEmpty()
            || context.checkSelfPermission(Manifest.permission.SEND_SMS) != PackageManager.PERMISSION_GRANTED) {
            Log.w(TAG, "No gateway number or SEND_SMS not granted; no native alert");
            done.run();
            return;
        }
        Location last = lastKnownLocation(context);
        if (last != null && System.currentTimeMillis() - last.getTime() < FRESH_MS) {
            sendReport(context, gatewayNumber, last);
            done.run();
            return;
        }
        LocationManager lm = (LocationManager) context.getSystemService(Context.LOCATION_SERVICE);
        String provider = lm == null ? null
            : lm.isProviderEnabled(LocationManager.GPS_PROVIDER) ? LocationManager.GPS_PROVIDER
            : lm.isProviderEnabled(LocationManager.NETWORK_PROVIDER) ? LocationManager.NETWORK_PROVIDER : null;
        if (provider == null || Build.VERSION.SDK_INT < Build.VERSION_CODES.R || !hasLocationPermission(context)) {
            sendReport(context, gatewayNumber, last);
            done.run();
            return;
        }
        AtomicBoolean sent = new AtomicBoolean(false);
        CancellationSignal cancel = new CancellationSignal();
        Handler main = new Handler(Looper.getMainLooper());
        Runnable fallback = () -> {
            if (sent.compareAndSet(false, true)) {
                cancel.cancel();
                sendReport(context, gatewayNumber, last);
                done.run();
            }
        };
        main.postDelayed(fallback, FIX_TIMEOUT_MS);
        try {
            lm.getCurrentLocation(provider, cancel, context.getMainExecutor(), fix -> {
                if (sent.compareAndSet(false, true)) {
                    main.removeCallbacks(fallback);
                    sendReport(context, gatewayNumber, fix != null ? fix : last);
                    done.run();
                }
            });
        } catch (SecurityException e) {
            main.removeCallbacks(fallback);
            fallback.run();
        }
    }

    private static boolean hasLocationPermission(Context context) {
        return context.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
            || context.checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED;
    }

    private static void sendReport(Context context, String gatewayNumber, Location location) {
        StringBuilder report = new StringBuilder("Kaaka Alert: Emergency assistance requested\n\n");
        if (location != null) {
            String lat = String.format(Locale.US, "%.6f", location.getLatitude());
            String lon = String.format(Locale.US, "%.6f", location.getLongitude());
            report.append("• Coords: ").append(lat).append(", ").append(lon).append("\n");
            report.append("• Maps: https://maps.google.com/?q=").append(lat).append(",").append(lon).append("\n");
        } else {
            report.append("• Location: unavailable\n");
        }
        report.append("• Trigger: gateway reply");
        try {
            int subId = SubscriptionManager.getDefaultSmsSubscriptionId();
            SmsManager sms = subId == SubscriptionManager.INVALID_SUBSCRIPTION_ID
                ? (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S ? context.getSystemService(SmsManager.class) : SmsManager.getDefault())
                : (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S
                    ? context.getSystemService(SmsManager.class).createForSubscriptionId(subId)
                    : SmsManager.getSmsManagerForSubscriptionId(subId));
            ArrayList<String> parts = sms.divideMessage(report.toString());
            sms.sendMultipartTextMessage(gatewayNumber.trim(), null, parts, null, null);
            Log.i(TAG, "Native Kaaka Alert sent to " + gatewayNumber + (location != null ? " with location" : " without location"));
        } catch (Exception e) {
            Log.w(TAG, "Native Kaaka Alert failed: " + e.getMessage());
        }
    }

    /** Freshest last-known fix from any provider (no waiting; the receiver must return quickly). */
    private static Location lastKnownLocation(Context context) {
        if (!hasLocationPermission(context)) return null;
        LocationManager lm = (LocationManager) context.getSystemService(Context.LOCATION_SERVICE);
        if (lm == null) return null;
        Location best = null;
        for (String provider : lm.getProviders(true)) {
            try {
                Location l = lm.getLastKnownLocation(provider);
                if (l != null && (best == null || l.getTime() > best.getTime())) best = l;
            } catch (SecurityException ignored) {
            }
        }
        return best;
    }
}
