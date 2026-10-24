package com.kaaka.sensors;

import android.Manifest;
import android.content.Context;
import android.content.pm.PackageManager;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Looper;
import androidx.core.content.ContextCompat;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;

@CapacitorPlugin(
    name = "KaakaSensors",
    permissions = {
        @Permission(
            strings = { Manifest.permission.ACTIVITY_RECOGNITION },
            alias = "activityRecognition"
        ),
        @Permission(
            strings = { Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION },
            alias = "location"
        )
    }
)
public class KaakaSensorsPlugin extends Plugin implements SensorEventListener {

    private SensorManager sensorManager;
    private LocationManager locationManager;
    private Location lastKnownLocation;

    private final LocationListener locationListener = new LocationListener() {
        @Override
        public void onLocationChanged(Location location) {
            if (location != null) {
                lastKnownLocation = location;
            }
        }
        @Override
        public void onStatusChanged(String provider, int status, Bundle extras) {}
        @Override
        public void onProviderEnabled(String provider) {}
        @Override
        public void onProviderDisabled(String provider) {}
    };

    private Sensor accelerometer;
    private Sensor gyroscope;
    private Sensor magnetometer;
    private Sensor lightSensor;
    private Sensor stepCounter;
    private Sensor stepDetector;

    // Latest readings cache
    private float[] lastAccelerometer = new float[3];
    private float[] lastGyroscope = new float[3];
    private float[] lastMagnetometer = new float[3];
    private float lastLightLux = 0f;
    private int baselineStepCount = -1;
    private int currentStepCount = 0;
    private int detectedStepCount = 0;

    // Compass calculation
    private float[] rotationMatrix = new float[9];
    private float[] orientationValues = new float[3];
    private float calculatedHeading = 0f;

    // Software step detector fallback (accelerometer-based) for hardware without step detector
    private double lastAccelMagnitude = 9.81;
    private long lastStepTime = 0;
    private static final double STEP_THRESHOLD = 11.2;
    private static final long MIN_STEP_INTERVAL_MS = 250;

    private boolean isListening = false;
    private long lastEmitTimestamp = 0;
    private static final long EMIT_THROTTLE_MS = 60; // ~16 updates per second for smooth UI

    @Override
    public void load() {
        super.load();
        Context context = getContext();
        sensorManager = (SensorManager) context.getSystemService(Context.SENSOR_SERVICE);
        try {
            locationManager = (LocationManager) context.getSystemService(Context.LOCATION_SERVICE);
        } catch (Exception ignored) {}

        if (sensorManager != null) {
            accelerometer = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER);
            gyroscope = sensorManager.getDefaultSensor(Sensor.TYPE_GYROSCOPE);
            magnetometer = sensorManager.getDefaultSensor(Sensor.TYPE_MAGNETIC_FIELD);
            lightSensor = sensorManager.getDefaultSensor(Sensor.TYPE_LIGHT);
            stepCounter = sensorManager.getDefaultSensor(Sensor.TYPE_STEP_COUNTER);
            stepDetector = sensorManager.getDefaultSensor(Sensor.TYPE_STEP_DETECTOR);
        }
    }

    @PluginMethod
    public void getSensorStatus(PluginCall call) {
        JSObject ret = new JSObject();
        ret.put("accelerometerAvailable", accelerometer != null);
        ret.put("gyroscopeAvailable", gyroscope != null);
        ret.put("magnetometerAvailable", magnetometer != null);
        ret.put("ambientLightAvailable", lightSensor != null);
        ret.put("pedometerHardwareAvailable", (stepCounter != null || stepDetector != null));
        ret.put("isListening", isListening);

        boolean hasActivityPerm = true;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            hasActivityPerm = ContextCompat.checkSelfPermission(
                getContext(),
                Manifest.permission.ACTIVITY_RECOGNITION
            ) == PackageManager.PERMISSION_GRANTED;
        }
        ret.put("hasActivityRecognitionPermission", hasActivityPerm);

        boolean hasLocPerm = ContextCompat.checkSelfPermission(
            getContext(),
            Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED;
        ret.put("hasLocationPermission", hasLocPerm);

        call.resolve(ret);
    }

    @PluginMethod
    public void requestSensorPermissions(PluginCall call) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            if (getPermissionState("activityRecognition") != com.getcapacitor.PermissionState.GRANTED) {
                requestPermissionForAlias("activityRecognition", call, "permissionCallback");
                return;
            }
        }
        if (getPermissionState("location") != com.getcapacitor.PermissionState.GRANTED) {
            requestPermissionForAlias("location", call, "permissionCallback");
            return;
        }
        JSObject result = new JSObject();
        result.put("granted", true);
        call.resolve(result);
    }

    @PermissionCallback
    private void permissionCallback(PluginCall call) {
        JSObject result = new JSObject();
        boolean actGranted = (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) ||
            (getPermissionState("activityRecognition") == com.getcapacitor.PermissionState.GRANTED);
        boolean locGranted = (getPermissionState("location") == com.getcapacitor.PermissionState.GRANTED);
        result.put("granted", actGranted && locGranted);
        call.resolve(result);
    }

    public Location getBestLocation() {
        if (lastKnownLocation != null && (System.currentTimeMillis() - lastKnownLocation.getTime() < 60000)) {
            return lastKnownLocation;
        }
        if (locationManager == null) {
            return lastKnownLocation;
        }
        Context context = getContext();
        boolean hasFine = ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED;
        boolean hasCoarse = ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED;
        if (!hasFine && !hasCoarse) {
            return lastKnownLocation;
        }

        Location best = lastKnownLocation;
        String[] providers = new String[] {
            LocationManager.FUSED_PROVIDER,
            LocationManager.GPS_PROVIDER,
            LocationManager.NETWORK_PROVIDER,
            LocationManager.PASSIVE_PROVIDER
        };

        for (String provider : providers) {
            try {
                Location l = locationManager.getLastKnownLocation(provider);
                if (l != null) {
                    if (best == null || l.getTime() > best.getTime()) {
                        best = l;
                    }
                }
            } catch (Exception ignored) {}
        }
        if (best != null) {
            lastKnownLocation = best;
        }
        return best;
    }

    @PluginMethod
    public void getLocation(PluginCall call) {
        Location loc = getBestLocation();
        JSObject res = new JSObject();
        if (loc != null) {
            res.put("success", true);
            res.put("hasCoords", true);
            res.put("latitude", loc.getLatitude());
            res.put("longitude", loc.getLongitude());
            res.put("accuracy", round(loc.getAccuracy()));
            res.put("altitude", round((float) loc.getAltitude()));
            res.put("mapsUrl", "https://maps.google.com/?q=" + loc.getLatitude() + "," + loc.getLongitude());
        } else {
            res.put("success", false);
            res.put("hasCoords", false);
        }
        call.resolve(res);
    }

    @PluginMethod
    public void startListening(PluginCall call) {
        if (sensorManager == null) {
            call.reject("SensorManager is not available on this device.");
            return;
        }

        if (!isListening) {
            int rate = SensorManager.SENSOR_DELAY_UI;

            if (accelerometer != null) {
                sensorManager.registerListener(this, accelerometer, rate);
            }
            if (gyroscope != null) {
                sensorManager.registerListener(this, gyroscope, rate);
            }
            if (magnetometer != null) {
                sensorManager.registerListener(this, magnetometer, rate);
            }
            if (lightSensor != null) {
                sensorManager.registerListener(this, lightSensor, rate);
            }
            if (stepCounter != null) {
                sensorManager.registerListener(this, stepCounter, SensorManager.SENSOR_DELAY_NORMAL);
            }
            if (stepDetector != null) {
                sensorManager.registerListener(this, stepDetector, SensorManager.SENSOR_DELAY_FASTEST);
            }

            // Register continuous location updates
            if (locationManager != null) {
                Context context = getContext();
                boolean hasFine = ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED;
                boolean hasCoarse = ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED;
                if (hasFine || hasCoarse) {
                    try {
                        if (locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
                            locationManager.requestLocationUpdates(LocationManager.GPS_PROVIDER, 5000, 5, locationListener, Looper.getMainLooper());
                        }
                        if (locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
                            locationManager.requestLocationUpdates(LocationManager.NETWORK_PROVIDER, 5000, 5, locationListener, Looper.getMainLooper());
                        }
                    } catch (Exception ignored) {}
                }
            }

            isListening = true;
        }

        JSObject res = new JSObject();
        res.put("success", true);
        res.put("message", "All available sensors registered successfully.");
        call.resolve(res);
    }

    @PluginMethod
    public void stopListening(PluginCall call) {
        if (sensorManager != null && isListening) {
            sensorManager.unregisterListener(this);
            isListening = false;
        }
        if (locationManager != null) {
            try {
                locationManager.removeUpdates(locationListener);
            } catch (Exception ignored) {}
        }

        JSObject res = new JSObject();
        res.put("success", true);
        res.put("message", "Sensors unregistered.");
        call.resolve(res);
    }

    @PluginMethod
    public void resetStepCount(PluginCall call) {
        baselineStepCount = -1;
        currentStepCount = 0;
        detectedStepCount = 0;

        JSObject res = new JSObject();
        res.put("success", true);
        res.put("currentSteps", 0);
        call.resolve(res);
    }

    @PluginMethod
    public void getLatestReadings(PluginCall call) {
        call.resolve(buildSensorsSnapshot());
    }

    @Override
    public void onSensorChanged(SensorEvent event) {
        long now = System.currentTimeMillis();

        int type = event.sensor.getType();
        if (type == Sensor.TYPE_ACCELEROMETER) {
            lastAccelerometer[0] = event.values[0];
            lastAccelerometer[1] = event.values[1];
            lastAccelerometer[2] = event.values[2];

            // Calculate compass orientation if magnetometer is also available
            calculateOrientation();

            // Software step detector fallback
            double magnitude = Math.sqrt(
                lastAccelerometer[0] * lastAccelerometer[0] +
                lastAccelerometer[1] * lastAccelerometer[1] +
                lastAccelerometer[2] * lastAccelerometer[2]
            );

            if (stepCounter == null && stepDetector == null) {
                if (magnitude > STEP_THRESHOLD && (now - lastStepTime) > MIN_STEP_INTERVAL_MS) {
                    detectedStepCount++;
                    currentStepCount = detectedStepCount;
                    lastStepTime = now;
                }
            }
            lastAccelMagnitude = magnitude;

        } else if (type == Sensor.TYPE_GYROSCOPE) {
            lastGyroscope[0] = event.values[0];
            lastGyroscope[1] = event.values[1];
            lastGyroscope[2] = event.values[2];

        } else if (type == Sensor.TYPE_MAGNETIC_FIELD) {
            lastMagnetometer[0] = event.values[0];
            lastMagnetometer[1] = event.values[1];
            lastMagnetometer[2] = event.values[2];
            calculateOrientation();

        } else if (type == Sensor.TYPE_LIGHT) {
            lastLightLux = event.values[0];

        } else if (type == Sensor.TYPE_STEP_COUNTER) {
            int totalStepsFromReboot = (int) event.values[0];
            if (baselineStepCount < 0) {
                baselineStepCount = totalStepsFromReboot;
            }
            currentStepCount = totalStepsFromReboot - baselineStepCount;

        } else if (type == Sensor.TYPE_STEP_DETECTOR) {
            detectedStepCount++;
            if (stepCounter == null) {
                currentStepCount = detectedStepCount;
            }
        }

        // Throttle emits to avoid flooding the Capacitor JS bridge while keeping 16-20fps
        if (now - lastEmitTimestamp >= EMIT_THROTTLE_MS) {
            lastEmitTimestamp = now;
            JSObject snapshot = buildSensorsSnapshot();
            notifyListeners("onSensorUpdate", snapshot);
        }
    }

    private void calculateOrientation() {
        boolean success = SensorManager.getRotationMatrix(
            rotationMatrix,
            null,
            lastAccelerometer,
            lastMagnetometer
        );
        if (success) {
            SensorManager.getOrientation(rotationMatrix, orientationValues);
            // orientationValues[0] is azimuth in radians [-PI to PI]
            float azimuthInDegrees = (float) Math.toDegrees(orientationValues[0]);
            calculatedHeading = (azimuthInDegrees + 360f) % 360f;
        }
    }

    private JSObject buildSensorsSnapshot() {
        JSObject data = new JSObject();
        long now = System.currentTimeMillis();

        // 1. Accelerometer
        JSObject accel = new JSObject();
        accel.put("x", round(lastAccelerometer[0]));
        accel.put("y", round(lastAccelerometer[1]));
        accel.put("z", round(lastAccelerometer[2]));
        double totalAccel = Math.sqrt(
            lastAccelerometer[0] * lastAccelerometer[0] +
            lastAccelerometer[1] * lastAccelerometer[1] +
            lastAccelerometer[2] * lastAccelerometer[2]
        );
        accel.put("magnitude", round((float) totalAccel));
        data.put("accelerometer", accel);

        // 2. Gyroscope
        JSObject gyro = new JSObject();
        gyro.put("x", round(lastGyroscope[0]));
        gyro.put("y", round(lastGyroscope[1]));
        gyro.put("z", round(lastGyroscope[2]));
        double totalGyro = Math.sqrt(
            lastGyroscope[0] * lastGyroscope[0] +
            lastGyroscope[1] * lastGyroscope[1] +
            lastGyroscope[2] * lastGyroscope[2]
        );
        gyro.put("rate", round((float) totalGyro));
        data.put("gyroscope", gyro);

        // 3. Magnetometer
        JSObject mag = new JSObject();
        mag.put("x", round(lastMagnetometer[0]));
        mag.put("y", round(lastMagnetometer[1]));
        mag.put("z", round(lastMagnetometer[2]));
        double totalMag = Math.sqrt(
            lastMagnetometer[0] * lastMagnetometer[0] +
            lastMagnetometer[1] * lastMagnetometer[1] +
            lastMagnetometer[2] * lastMagnetometer[2]
        );
        mag.put("fieldStrength", round((float) totalMag));
        mag.put("heading", round(calculatedHeading));
        mag.put("cardinal", getCardinalDirection(calculatedHeading));
        data.put("magnetometer", mag);

        // 4. Ambient Light Sensor
        JSObject light = new JSObject();
        light.put("lux", round(lastLightLux));
        light.put("environment", getLightEnvironment(lastLightLux));
        data.put("ambientLight", light);

        // 5. Pedometer
        JSObject pedometer = new JSObject();
        int steps = Math.max(0, currentStepCount);
        pedometer.put("steps", steps);
        pedometer.put("detectedSteps", detectedStepCount);
        // Approx distance in km (0.75m per step average)
        double distanceKm = (steps * 0.75) / 1000.0;
        pedometer.put("distanceKm", round((float) distanceKm));
        // Approx calories (0.04 kcal per step average)
        double calories = steps * 0.04;
        pedometer.put("caloriesBurned", round((float) calories));
        data.put("pedometer", pedometer);

        // 6. Location Coords
        JSObject locationObj = new JSObject();
        Location loc = getBestLocation();
        if (loc != null) {
            double lat = loc.getLatitude();
            double lon = loc.getLongitude();
            locationObj.put("latitude", lat);
            locationObj.put("longitude", lon);
            locationObj.put("accuracy", round(loc.getAccuracy()));
            locationObj.put("altitude", round((float) loc.getAltitude()));
            locationObj.put("mapsUrl", "https://maps.google.com/?q=" + lat + "," + lon);
            locationObj.put("hasCoords", true);
        } else {
            locationObj.put("hasCoords", false);
        }
        data.put("location", locationObj);

        data.put("timestamp", now);
        data.put("isListening", isListening);

        return data;
    }

    private String getLightEnvironment(float lux) {
        if (lux < 10) return "Pitch Black / Night";
        if (lux < 50) return "Dim / Dark Indoors";
        if (lux < 250) return "Living Room / Normal Indoor";
        if (lux < 1000) return "Bright Office / Desk";
        if (lux < 10000) return "Overcast / Shaded Outdoors";
        if (lux < 30000) return "Daylight Indoors";
        return "Direct Bright Sunlight";
    }

    private String getCardinalDirection(float heading) {
        if (heading >= 337.5 || heading < 22.5) return "N";
        if (heading >= 22.5 && heading < 67.5) return "NE";
        if (heading >= 67.5 && heading < 112.5) return "E";
        if (heading >= 112.5 && heading < 157.5) return "SE";
        if (heading >= 157.5 && heading < 202.5) return "S";
        if (heading >= 202.5 && heading < 247.5) return "SW";
        if (heading >= 247.5 && heading < 292.5) return "W";
        return "NW";
    }

    private float round(float val) {
        return Math.round(val * 100.0f) / 100.0f;
    }

    @Override
    public void onAccuracyChanged(Sensor sensor, int accuracy) {
        // Not used
    }

    @Override
    protected void handleOnPause() {
        super.handleOnPause();
    }

    @Override
    protected void handleOnResume() {
        super.handleOnResume();
    }

    @Override
    protected void handleOnDestroy() {
        if (sensorManager != null && isListening) {
            sensorManager.unregisterListener(this);
            isListening = false;
        }
        if (locationManager != null) {
            try {
                locationManager.removeUpdates(locationListener);
            } catch (Exception ignored) {}
        }
        super.handleOnDestroy();
    }
}
