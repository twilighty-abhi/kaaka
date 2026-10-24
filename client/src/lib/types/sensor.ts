export interface Vector3D {
	x: number;
	y: number;
	z: number;
}

export interface AccelerometerData extends Vector3D {
	magnitude: number;
}

export interface GyroscopeData extends Vector3D {
	rate: number;
}

export interface MagnetometerData extends Vector3D {
	fieldStrength: number;
	heading: number;
	cardinal: string;
}

export interface AmbientLightData {
	lux: number;
	environment: string;
}

export interface PedometerData {
	steps: number;
	detectedSteps: number;
	distanceKm: number;
	caloriesBurned: number;
}

export interface LocationData {
	latitude: number;
	longitude: number;
	accuracy?: number;
	altitude?: number;
	mapsUrl: string;
	hasCoords: boolean;
}

export interface SensorStatus {
	accelerometerAvailable: boolean;
	gyroscopeAvailable: boolean;
	magnetometerAvailable: boolean;
	ambientLightAvailable: boolean;
	pedometerHardwareAvailable: boolean;
	isListening: boolean;
	hasActivityRecognitionPermission: boolean;
	hasLocationPermission?: boolean;
	isNative: boolean;
}

export interface FullSensorPayload {
	accelerometer: AccelerometerData;
	gyroscope: GyroscopeData;
	magnetometer: MagnetometerData;
	ambientLight: AmbientLightData;
	pedometer: PedometerData;
	location?: LocationData;
	timestamp: number;
	isListening: boolean;
}
