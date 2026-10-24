package com.kaaka.sensors;

import android.Manifest;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.PowerManager;
import android.provider.Settings;
import com.getcapacitor.JSObject;
import com.getcapacitor.PermissionState;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;
import java.util.ArrayList;
import java.util.List;

/**
 * One place for everything the app needs from the phone: runtime permissions, battery exemption
 * and the vendor screens (e.g. MIUI autostart / lock screen / background pop-ups) that apps cannot grant themselves.
 */
@CapacitorPlugin(
    name = "KaakaSetup",
    permissions = {
        @Permission(strings = { Manifest.permission.SEND_SMS, Manifest.permission.RECEIVE_SMS, Manifest.permission.READ_PHONE_STATE }, alias = "sms"),
        @Permission(strings = { Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION }, alias = "location"),
        @Permission(strings = { Manifest.permission.POST_NOTIFICATIONS }, alias = "notifications"),
        // Must be requested after foreground location; Android 11+ shows it as "Allow all the time" in settings.
        @Permission(strings = { Manifest.permission.ACCESS_BACKGROUND_LOCATION }, alias = "backgroundLocation"),
        @Permission(strings = { Manifest.permission.ACTIVITY_RECOGNITION }, alias = "activity")
    }
)
public class KaakaSetupPlugin extends Plugin {

    private boolean granted(String alias) {
        return getPermissionState(alias) == PermissionState.GRANTED;
    }

    private JSObject status() {
        Context context = getContext();
        JSObject result = new JSObject();
        result.put("sms", granted("sms"));
        result.put("location", granted("location"));
        // Runtime notification permission only exists on Android 13+, activity recognition on 10+.
        result.put("notifications", Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU || granted("notifications"));
        result.put("activity", Build.VERSION.SDK_INT < Build.VERSION_CODES.Q || granted("activity"));
        result.put("backgroundLocation", Build.VERSION.SDK_INT < Build.VERSION_CODES.Q || granted("backgroundLocation"));
        PowerManager pm = (PowerManager) context.getSystemService(Context.POWER_SERVICE);
        result.put("batteryExempt", pm != null && pm.isIgnoringBatteryOptimizations(context.getPackageName()));
        result.put("vendor", Build.MANUFACTURER == null ? "" : Build.MANUFACTURER.toLowerCase());
        return result;
    }

    @PluginMethod
    public void getStatus(PluginCall call) {
        call.resolve(status());
    }

    /** Requests every missing runtime permission in one go. */
    @PluginMethod
    public void requestAll(PluginCall call) {
        List<String> missing = new ArrayList<>();
        for (String alias : new String[] { "sms", "location", "notifications", "activity" }) {
            if (alias.equals("notifications") && Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) continue;
            if (alias.equals("activity") && Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) continue;
            if (!granted(alias)) missing.add(alias);
        }
        if (missing.isEmpty()) {
            call.resolve(status());
            return;
        }
        requestPermissionForAliases(missing.toArray(new String[0]), call, "requestAllCallback");
    }

    @PermissionCallback
    private void requestAllCallback(PluginCall call) {
        call.resolve(status());
    }

    /** Background location ("Allow all the time"); only asked once foreground location is granted. */
    @PluginMethod
    public void requestBackgroundLocation(PluginCall call) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q || granted("backgroundLocation") || !granted("location")) {
            call.resolve(status());
            return;
        }
        requestPermissionForAlias("backgroundLocation", call, "requestAllCallback");
    }

    @PluginMethod
    public void requestBatteryExemption(PluginCall call) {
        Context context = getContext();
        try {
            Intent intent = new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS);
            intent.setData(Uri.parse("package:" + context.getPackageName()));
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            context.startActivity(intent);
        } catch (Exception e) {
            openDetails(context);
        }
        call.resolve();
    }

    /** Opens the vendor permission editor where available (MIUI), otherwise the app's settings page. */
    @PluginMethod
    public void openPhoneSettings(PluginCall call) {
        Context context = getContext();
        try {
            Intent miui = new Intent("miui.intent.action.APP_PERM_EDITOR");
            miui.setClassName("com.miui.securitycenter", "com.miui.permcenter.permissions.PermissionsEditorActivity");
            miui.putExtra("extra_pkgname", context.getPackageName());
            miui.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            context.startActivity(miui);
        } catch (Exception e) {
            openDetails(context);
        }
        call.resolve();
    }

    private static void openDetails(Context context) {
        Intent intent = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
        intent.setData(Uri.parse("package:" + context.getPackageName()));
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        context.startActivity(intent);
    }
}
