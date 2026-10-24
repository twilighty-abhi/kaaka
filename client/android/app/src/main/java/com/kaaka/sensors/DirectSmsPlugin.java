package com.kaaka.sensors;

import android.Manifest;
import android.content.Context;
import android.os.Build;
import android.telephony.SmsManager;
import java.util.ArrayList;
import com.getcapacitor.JSObject;
import com.getcapacitor.PermissionState;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;

@CapacitorPlugin(
    name = "DirectSms",
    permissions = {
        @Permission(
            strings = { Manifest.permission.SEND_SMS },
            alias = "sms"
        )
    }
)
public class DirectSmsPlugin extends Plugin {

    @PluginMethod
    public void sendSms(PluginCall call) {
        String number = call.getString("number");
        String message = call.getString("message");

        if (number == null || number.trim().isEmpty()) {
            call.reject("Recipient phone number is required");
            return;
        }

        if (message == null || message.trim().isEmpty()) {
            call.reject("Message content cannot be empty");
            return;
        }

        if (getPermissionState("sms") != PermissionState.GRANTED) {
            requestPermissionForAlias("sms", call, "smsPermCallback");
        } else {
            sendDirectSms(number, message, call);
        }
    }

    @PermissionCallback
    private void smsPermCallback(PluginCall call) {
        if (getPermissionState("sms") == PermissionState.GRANTED) {
            String number = call.getString("number");
            String message = call.getString("message");
            sendDirectSms(number, message, call);
        } else {
            call.reject("Permission to send SMS was denied.");
        }
    }

    private void sendDirectSms(String number, String message, PluginCall call) {
        try {
            SmsManager smsManager;
            Context context = getContext();
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                smsManager = context.getSystemService(SmsManager.class);
            } else {
                smsManager = SmsManager.getDefault();
            }

            ArrayList<String> parts = smsManager.divideMessage(message);
            if (parts.size() > 1) {
                smsManager.sendMultipartTextMessage(number, null, parts, null, null);
            } else {
                smsManager.sendTextMessage(number, null, message, null, null);
            }

            JSObject ret = new JSObject();
            ret.put("success", true);
            call.resolve(ret);
        } catch (Exception e) {
            call.reject("Failed to send SMS: " + e.getMessage(), e);
        }
    }
}
