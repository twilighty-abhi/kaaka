package com.kaaka.sensors;

import android.app.role.RoleManager;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.provider.Telephony;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

@CapacitorPlugin(name = "DefaultSms")
public class DefaultSmsPlugin extends Plugin {

    private static DefaultSmsPlugin instance;
    private static JSObject lastTrigger = null;

    @Override
    public void load() {
        super.load();
        instance = this;
        if (lastTrigger != null) {
            notifyListeners("smsReceived", lastTrigger);
        }
    }

    @Override
    protected void handleOnDestroy() {
        if (instance == this) {
            instance = null;
        }
        super.handleOnDestroy();
    }

    public static void handleIncomingSms(String sender, String message, long timestamp) {
        JSObject data = new JSObject();
        data.put("sender", sender);
        data.put("message", message);
        data.put("timestamp", timestamp);
        lastTrigger = data;
        if (instance != null) {
            instance.notifyListeners("smsReceived", data);
        }
    }

    public static void triggerStopBeacon() {
        if (instance != null) {
            instance.notifyListeners("stopBeaconTriggered", new JSObject());
        }
    }

    @PluginMethod
    public void getLastTrigger(PluginCall call) {
        if (lastTrigger != null) {
            call.resolve(lastTrigger);
        } else {
            call.resolve(new JSObject());
        }
    }

    @PluginMethod
    public void isDefaultSms(PluginCall call) {
        Context context = getContext();
        boolean isDefault = false;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            RoleManager roleManager = getActivity().getSystemService(RoleManager.class);
            if (roleManager != null && roleManager.isRoleAvailable(RoleManager.ROLE_SMS)) {
                isDefault = roleManager.isRoleHeld(RoleManager.ROLE_SMS);
            }
        } else {
            String defaultSms = Telephony.Sms.getDefaultSmsPackage(context);
            isDefault = context.getPackageName().equals(defaultSms);
        }
        JSObject ret = new JSObject();
        ret.put("isDefault", isDefault);
        call.resolve(ret);
    }

    @PluginMethod
    public void requestDefaultSms(PluginCall call) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            RoleManager roleManager = getActivity().getSystemService(RoleManager.class);
            if (roleManager != null && roleManager.isRoleAvailable(RoleManager.ROLE_SMS)) {
                if (!roleManager.isRoleHeld(RoleManager.ROLE_SMS)) {
                    Intent intent = roleManager.createRequestRoleIntent(RoleManager.ROLE_SMS);
                    getActivity().startActivityForResult(intent, 1001);
                }
            }
        } else {
            Intent intent = new Intent(Telephony.Sms.Intents.ACTION_CHANGE_DEFAULT);
            intent.putExtra(Telephony.Sms.Intents.EXTRA_PACKAGE_NAME, getContext().getPackageName());
            getActivity().startActivityForResult(intent, 1001);
        }
        call.resolve();
    }
}
