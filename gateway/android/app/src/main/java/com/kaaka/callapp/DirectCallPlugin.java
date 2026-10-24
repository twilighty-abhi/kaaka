package com.kaaka.callapp;

import android.Manifest;
import android.content.Intent;
import android.net.Uri;
import com.getcapacitor.PermissionState;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;

@CapacitorPlugin(
    name = "DirectCall",
    permissions = {
        @Permission(
            strings = { Manifest.permission.CALL_PHONE },
            alias = "call"
        )
    }
)
public class DirectCallPlugin extends Plugin {

    @PluginMethod
    public void makeCall(PluginCall call) {
        String number = call.getString("number");
        if (number == null || number.trim().isEmpty()) {
            call.reject("Phone number is required");
            return;
        }

        if (getPermissionState("call") != PermissionState.GRANTED) {
            requestPermissionForAlias("call", call, "callPermCallback");
        } else {
            startDirectCall(number, call);
        }
    }

    @PermissionCallback
    private void callPermCallback(PluginCall call) {
        if (getPermissionState("call") == PermissionState.GRANTED) {
            String number = call.getString("number");
            startDirectCall(number, call);
        } else {
            call.reject("Permission to make calls was denied.");
        }
    }

    private void startDirectCall(String number, PluginCall call) {
        try {
            Intent intent = new Intent(Intent.ACTION_CALL);
            intent.setData(Uri.parse("tel:" + Uri.encode(number)));
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            getContext().startActivity(intent);
            call.resolve();
        } catch (Exception e) {
            call.reject("Failed to initiate call: " + e.getMessage(), e);
        }
    }
}
