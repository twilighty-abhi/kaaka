export interface Vector3D {
  x: number;
  y: number;
  z: number;
}

export interface AccelerometerReading extends Vector3D {
  magnitude: number;
}

export interface GyroscopeReading extends Vector3D {
  rate: number;
}

export interface MagnetometerReading extends Vector3D {
  fieldStrength: number;
  heading: number;
  cardinal: string;
}

export interface AmbientLightReading {
  lux: number;
  environment: string;
}

export interface PedometerReading {
  steps: number;
  detectedSteps: number;
  distanceKm: number;
  caloriesBurned: number;
}

export interface SensorPayload {
  accelerometer: AccelerometerReading;
  gyroscope: GyroscopeReading;
  magnetometer: MagnetometerReading;
  ambientLight: AmbientLightReading;
  pedometer: PedometerReading;
}

export interface DeviceTelemetryPacket {
  id?: string;
  deviceId: string;
  platform: string;
  timestamp: number;
  receivedAt?: number;
  sensors: SensorPayload;
  alerts?: TelemetryAlert[];
}

export interface TelemetryAlert {
  id: string;
  type: "IMPACT" | "ROTATION" | "MAGNETIC_ANOMALY" | "LOW_LIGHT" | "STEP_MILESTONE";
  severity: "INFO" | "WARNING" | "CRITICAL";
  message: string;
  timestamp: number;
}
