package com.kaaka.callapp;

import android.content.Context;
import androidx.annotation.NonNull;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

/** Periodic WorkManager job that sends the dashboard heartbeat (see {@link Heartbeat}). */
public class HeartbeatWorker extends Worker {
    public HeartbeatWorker(@NonNull Context context, @NonNull WorkerParameters params) {
        super(context, params);
    }

    @NonNull
    @Override
    public Result doWork() {
        Heartbeat.send(getApplicationContext());
        return Result.success();
    }
}
