package com.kaaka.callapp;

import android.content.Context;
import androidx.annotation.NonNull;
import androidx.work.Data;
import androidx.work.ExistingWorkPolicy;
import androidx.work.OneTimeWorkRequest;
import androidx.work.WorkManager;
import androidx.work.Worker;
import androidx.work.WorkerParameters;
import java.util.concurrent.TimeUnit;
import org.json.JSONException;
import org.json.JSONObject;

/**
 * One reminder to the responders when an incident is still unacknowledged after the configured delay.
 * One pending job per caller number; a newer call or help SMS from the same number replaces it.
 */
public class EscalationWorker extends Worker {
    private static final String KEY_NUMBER = "number";
    private static final String KEY_KIND = "kind";
    private static final String KEY_AT = "at";

    public EscalationWorker(@NonNull Context context, @NonNull WorkerParameters params) {
        super(context, params);
    }

    /** Schedules the reminder unless escalation is off, the number is hidden or no responders are set. */
    static void schedule(Context context, String number, String kind, long incidentAt) {
        int minutes = GatewayStore.escalateMinutes(context);
        if (minutes <= 0 || number.isEmpty() || GatewayStore.responderNumbers(context).isEmpty()) return;
        Data input = new Data.Builder()
            .putString(KEY_NUMBER, number)
            .putString(KEY_KIND, kind)
            .putLong(KEY_AT, incidentAt > 0 ? incidentAt : System.currentTimeMillis())
            .build();
        OneTimeWorkRequest request = new OneTimeWorkRequest.Builder(EscalationWorker.class)
            .setInitialDelay(minutes, TimeUnit.MINUTES)
            .setInputData(input)
            .build();
        WorkManager.getInstance(context)
            .enqueueUniqueWork("escalate-" + number.replaceAll("\\D", ""), ExistingWorkPolicy.REPLACE, request);
    }

    @NonNull
    @Override
    public Result doWork() {
        Context context = getApplicationContext();
        String number = getInputData().getString(KEY_NUMBER);
        String kind = getInputData().getString(KEY_KIND);
        long at = getInputData().getLong(KEY_AT, 0);
        if (number == null || number.isEmpty()) return Result.success();
        // Settings may have changed since scheduling.
        if (GatewayStore.escalateMinutes(context) <= 0 || GatewayStore.responderNumbers(context).isEmpty()) return Result.success();
        if (GatewayText.handledSince(GatewayStore.eventList(context), number, at)) return Result.success();

        String message = "Kaaka UNACKNOWLEDGED: " + (kind == null ? "call" : kind) + " from " + number
            + " at " + GatewayText.timeOfDay(at) + ". Reply ACK " + number + " to confirm.";
        JSONObject event = new JSONObject();
        try {
            event.put("type", "escalation");
            event.put("number", number);
            event.put("kind", kind);
            event.put("timestamp", GatewayStore.nowIso());
        } catch (JSONException ignored) {
        }
        GatewayStore.notifyResponders(context, message, number, event);
        GatewayStore.appendEvent(context, event);
        return Result.success();
    }
}
