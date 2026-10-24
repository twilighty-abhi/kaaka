package com.kaaka.callapp;

import android.Manifest;
import android.app.role.RoleManager;
import android.content.Context;
import android.content.pm.PackageManager;
import android.os.BatteryManager;
import android.os.Build;
import android.os.PowerManager;
import androidx.work.Constraints;
import androidx.work.ExistingPeriodicWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.PeriodicWorkRequest;
import androidx.work.WorkManager;
import java.util.concurrent.TimeUnit;
import org.json.JSONException;
import org.json.JSONObject;

/**
 * Tells the optional dashboard every 15 minutes that the gateway phone is alive and set up
 * (POST {dashboard}/api/heartbeat). Does nothing while no dashboard URL is set.
 */
final class Heartbeat {
    private static final String WORK_NAME = "kaaka-heartbeat";

    private Heartbeat() {}

    /** Schedules the periodic heartbeat once; calling it again keeps the existing schedule. */
    static void schedule(Context context) {
        PeriodicWorkRequest request = new PeriodicWorkRequest.Builder(HeartbeatWorker.class, 15, TimeUnit.MINUTES)
            .setConstraints(new Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .build();
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(WORK_NAME, ExistingPeriodicWorkPolicy.KEEP, request);
    }

    /** Sends one heartbeat on a background thread. */
    static void sendNow(Context context) {
        Context app = context.getApplicationContext();
        new Thread(() -> send(app)).start();
    }

    /** Blocking; call from a background thread. */
    static void send(Context context) {
        if (GatewayStore.dashboardUrl(context).isEmpty()) return;
        JSONObject body = new JSONObject();
        try {
            BatteryManager battery = context.getSystemService(BatteryManager.class);
            int percent = battery == null ? -1 : battery.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY);
            body.put("timestamp", GatewayStore.nowIso());
            body.put("battery", percent > 0 ? percent : -1);
            body.put("charging", battery != null && battery.isCharging());
            body.put("screeningRole", screeningRole(context));
            body.put("smsGranted", granted(context, Manifest.permission.SEND_SMS) && granted(context, Manifest.permission.RECEIVE_SMS));
            body.put("contactCalls", contactCalls(context));
        } catch (JSONException ignored) {
        }
        GatewayStore.postToDashboard(context, "/api/heartbeat", body);
    }

    static boolean screeningRole(Context context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return false;
        RoleManager rm = context.getSystemService(RoleManager.class);
        return rm != null && rm.isRoleAvailable(RoleManager.ROLE_CALL_SCREENING) && rm.isRoleHeld(RoleManager.ROLE_CALL_SCREENING);
    }

    static boolean contactCalls(Context context) {
        return granted(context, Manifest.permission.READ_PHONE_STATE)
            && granted(context, Manifest.permission.READ_CALL_LOG)
            && (Build.VERSION.SDK_INT < Build.VERSION_CODES.O || granted(context, Manifest.permission.ANSWER_PHONE_CALLS));
    }

    /** True if Android's battery optimisation will not put the app to sleep. */
    static boolean batteryExempt(Context context) {
        PowerManager pm = context.getSystemService(PowerManager.class);
        return pm != null && pm.isIgnoringBatteryOptimizations(context.getPackageName());
    }

    private static boolean granted(Context context, String permission) {
        return context.checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED;
    }
}
