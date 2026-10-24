package com.kaaka.callapp;

import android.Manifest;
import android.app.role.RoleManager;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import androidx.activity.result.ActivityResult;
import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.PermissionState;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.ActivityCallback;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;
import org.json.JSONException;

/** Bridge between the Svelte UI and the native gateway (role, permissions, settings, event log). */
@CapacitorPlugin(
    name = "Gateway",
    permissions = {
        @Permission(strings = { Manifest.permission.SEND_SMS, Manifest.permission.RECEIVE_SMS }, alias = "sms")
    }
)
public class GatewayPlugin extends Plugin {

    private RoleManager roleManager() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return null;
        return getContext().getSystemService(RoleManager.class);
    }

    private JSObject status() {
        RoleManager rm = roleManager();
        boolean available = rm != null && rm.isRoleAvailable(RoleManager.ROLE_CALL_SCREENING);
        JSObject result = new JSObject();
        result.put("screeningSupported", available);
        result.put("screeningRole", available && rm.isRoleHeld(RoleManager.ROLE_CALL_SCREENING));
        result.put("sendSms", getContext().checkSelfPermission(Manifest.permission.SEND_SMS) == android.content.pm.PackageManager.PERMISSION_GRANTED);
        result.put("receiveSms", getContext().checkSelfPermission(Manifest.permission.RECEIVE_SMS) == android.content.pm.PackageManager.PERMISSION_GRANTED);
        return result;
    }

    @PluginMethod
    public void getStatus(PluginCall call) {
        call.resolve(status());
    }

    @PluginMethod
    public void requestScreeningRole(PluginCall call) {
        RoleManager rm = roleManager();
        if (rm == null || !rm.isRoleAvailable(RoleManager.ROLE_CALL_SCREENING)) {
            call.reject("Call screening needs Android 10 or newer");
            return;
        }
        if (rm.isRoleHeld(RoleManager.ROLE_CALL_SCREENING)) {
            call.resolve(status());
            return;
        }
        Intent intent = rm.createRequestRoleIntent(RoleManager.ROLE_CALL_SCREENING);
        startActivityForResult(call, intent, "roleResult");
    }

    @ActivityCallback
    private void roleResult(PluginCall call, ActivityResult result) {
        call.resolve(status());
    }

    @PluginMethod
    public void requestSmsPermissions(PluginCall call) {
        if (getPermissionState("sms") == PermissionState.GRANTED) {
            call.resolve(status());
        } else {
            requestPermissionForAlias("sms", call, "smsPermsCallback");
        }
    }

    @PermissionCallback
    private void smsPermsCallback(PluginCall call) {
        call.resolve(status());
    }

    @PluginMethod
    public void getSettings(PluginCall call) {
        Context context = getContext();
        JSObject result = new JSObject();
        result.put("rejectCalls", GatewayStore.rejectCalls(context));
        result.put("replyMessage", GatewayStore.replyMessage(context));
        result.put("dashboardUrl", GatewayStore.dashboardUrl(context));
        call.resolve(result);
    }

    @PluginMethod
    public void saveSettings(PluginCall call) {
        GatewayStore.saveSettings(
            getContext(),
            call.getBoolean("rejectCalls", true),
            call.getString("replyMessage", GatewayStore.DEFAULT_REPLY),
            call.getString("dashboardUrl", "")
        );
        call.resolve();
    }

    @PluginMethod
    public void getEvents(PluginCall call) {
        JSObject result = new JSObject();
        try {
            result.put("events", new JSArray(GatewayStore.getEvents(getContext()).toString()));
        } catch (JSONException e) {
            result.put("events", new JSArray());
        }
        call.resolve(result);
    }

    @PluginMethod
    public void clearEvents(PluginCall call) {
        GatewayStore.clearEvents(getContext());
        call.resolve();
    }
}
