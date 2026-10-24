import { appSettings } from "./appSettings.svelte.js";
import { Capacitor, registerPlugin } from "@capacitor/core";
import { SvelteDate } from "svelte/reactivity";
import type {
	FullSensorPayload,
	SensorStatus,
	AccelerometerData,
	GyroscopeData,
	MagnetometerData,
	AmbientLightData,
	PedometerData,
	LocationData
} from "#lib/types/sensor.js";

// Native plugin interface
interface KaakaSensorsNativePlugin {
	getSensorStatus(): Promise<{
		accelerometerAvailable: boolean;
		gyroscopeAvailable: boolean;
		magnetometerAvailable: boolean;
		ambientLightAvailable: boolean;
		pedometerHardwareAvailable: boolean;
		isListening: boolean;
		hasActivityRecognitionPermission: boolean;
		hasLocationPermission?: boolean;
	}>;
	requestSensorPermissions(): Promise<{ granted: boolean }>;
	startListening(): Promise<{ success: boolean; message: string }>;
	stopListening(): Promise<{ success: boolean; message: string }>;
	resetStepCount(): Promise<{ success: boolean; currentSteps: number }>;
	getLatestReadings(): Promise<FullSensorPayload>;
	getLocation(): Promise<LocationData & { success: boolean }>;
	addListener(
		eventName: "onSensorUpdate",
		listenerFunc: (data: FullSensorPayload) => void
	): Promise<{ remove: () => Promise<void> }>;
}

const NativeSensors = registerPlugin<KaakaSensorsNativePlugin>("KaakaSensors");

export class SensorManager {
	// Reactive state using Svelte 5 runes
	isNative = $state(Capacitor.isNativePlatform());
	isListening = $state(false);
	isSimulated = $state(false);
	backendSyncEnabled = $state(false);
		syncStatus = $state<"idle" | "syncing" | "error" | "connected">("idle");
	syncMessage = $state("");

	status = $state.raw<SensorStatus>({
		accelerometerAvailable: false,
		gyroscopeAvailable: false,
		magnetometerAvailable: false,
		ambientLightAvailable: false,
		pedometerHardwareAvailable: false,
		isListening: false,
		hasActivityRecognitionPermission: false,
		isNative: false
	});

	accelerometer = $state.raw<AccelerometerData>({ x: 0, y: 0, z: 9.81, magnitude: 9.81 });
	gyroscope = $state.raw<GyroscopeData>({ x: 0, y: 0, z: 0, rate: 0 });
	magnetometer = $state.raw<MagnetometerData>({
		x: 0,
		y: 0,
		z: 0,
		fieldStrength: 45,
		heading: 0,
		cardinal: "N"
	});
	ambientLight = $state.raw<AmbientLightData>({
		lux: 200,
		environment: "Living Room / Normal Indoor"
	});
	pedometer = $state.raw<PedometerData>({
		steps: 0,
		detectedSteps: 0,
		distanceKm: 0,
		caloriesBurned: 0
	});

	location = $state.raw<LocationData>({
		latitude: 0,
		longitude: 0,
		accuracy: 0,
		mapsUrl: "",
		hasCoords: false
	});

	// History buffer for charts (last 25 data points, updated via $state.raw for maximum performance)
	accelHistory = $state.raw<number[]>([]);
	gyroHistory = $state.raw<number[]>([]);
	magHistory = $state.raw<number[]>([]);
	lightHistory = $state.raw<number[]>([]);
	stepHistory = $state.raw<number[]>([]);

	lastUpdateTimestamp = $state(Date.now());
	updateRateHz = $state(0);

	private updateCount = 0;
	private lastRateCheck = Date.now();
	private simInterval: ReturnType<typeof setInterval> | null = null;
	private syncInterval: ReturnType<typeof setInterval> | null = null;
	private rateMeterInterval: ReturnType<typeof setInterval> | null = null;
	private listenerHandle: { remove: () => Promise<void> } | null = null;

	constructor() {
		this.isNative = Capacitor.isNativePlatform();
		this.status.isNative = this.isNative;
	}

	async initialize() {
		if (this.isNative) {
			try {
				const nativeStatus = await NativeSensors.getSensorStatus();
				this.status = {
					...nativeStatus,
					isNative: true
				};

				// Register native event listener
				this.listenerHandle = await NativeSensors.addListener(
					"onSensorUpdate",
					(data: FullSensorPayload) => {
						this.handleSensorData(data);
					}
				);
			} catch (err) {
				console.warn("Failed to query native sensors, falling back to simulated mode:", err);
				this.setupFallback();
			}
		} else {
			this.setupFallback();
		}

		// Initialize default history buffers
		this.accelHistory = Array(20).fill(9.81);
		this.gyroHistory = Array(20).fill(0);
		this.magHistory = Array(20).fill(45);
		this.lightHistory = Array(20).fill(250);
		this.stepHistory = Array(20).fill(0);

		await this.refreshLocation();
	}

	private setupFallback() {
		this.status = {
			accelerometerAvailable: true,
			gyroscopeAvailable: true,
			magnetometerAvailable: true,
			ambientLightAvailable: true,
			pedometerHardwareAvailable: true,
			isListening: false,
			hasActivityRecognitionPermission: true,
			isNative: false
		};
		// Try listening to standard browser DeviceMotionEvent if available
		if (typeof window !== "undefined" && "DeviceMotionEvent" in window) {
			try {
				window.addEventListener("devicemotion", (event) => {
					if (!this.isListening) return;
					if (event.accelerationIncludingGravity) {
						const ax = event.accelerationIncludingGravity.x ?? 0;
						const ay = event.accelerationIncludingGravity.y ?? 0;
						const az = event.accelerationIncludingGravity.z ?? 9.81;
						const mag = Math.sqrt(ax * ax + ay * ay + az * az);
						this.accelerometer = {
							x: Math.round(ax * 100) / 100,
							y: Math.round(ay * 100) / 100,
							z: Math.round(az * 100) / 100,
							magnitude: Math.round(mag * 100) / 100
						};
					}
					if (event.rotationRate) {
						const gx = (event.rotationRate.alpha ?? 0) * (Math.PI / 180);
						const gy = (event.rotationRate.beta ?? 0) * (Math.PI / 180);
						const gz = (event.rotationRate.gamma ?? 0) * (Math.PI / 180);
						const rate = Math.sqrt(gx * gx + gy * gy + gz * gz);
						this.gyroscope = {
							x: Math.round(gx * 100) / 100,
							y: Math.round(gy * 100) / 100,
							z: Math.round(gz * 100) / 100,
							rate: Math.round(rate * 100) / 100
						};
					}
				});
			} catch (e) {
				console.debug("Web DeviceMotion not permitted or unavailable", e);
			}
		}
	}

	async requestPermissions() {
		if (this.isNative) {
			try {
				const res = await NativeSensors.requestSensorPermissions();
				this.status.hasActivityRecognitionPermission = res.granted;
				return res.granted;
			} catch (e) {
				console.error("Error requesting permissions", e);
				return false;
			}
		}
		this.status.hasActivityRecognitionPermission = true;
		return true;
	}

	async start() {
		if (this.isListening) return;

		if (this.isNative) {
			try {
				await NativeSensors.startListening();
				this.isListening = true;
				this.status.isListening = true;
			} catch (err) {
				console.error("Failed to start native sensors:", err);
				this.startSimulatedEngine();
			}
		} else {
			this.startSimulatedEngine();
		}

		this.startRateMeter();
		this.refreshLocation();
		if (this.backendSyncEnabled) {
			this.startBackendSync();
		}
	}

	async stop() {
		if (!this.isListening) return;

		if (this.isNative) {
			try {
				await NativeSensors.stopListening();
			} catch (err) {
				console.error("Failed to stop native sensors:", err);
			}
		}

		if (this.simInterval) {
			clearInterval(this.simInterval);
			this.simInterval = null;
		}

		if (this.syncInterval) {
			clearInterval(this.syncInterval);
			this.syncInterval = null;
		}

		if (this.rateMeterInterval) {
			clearInterval(this.rateMeterInterval);
			this.rateMeterInterval = null;
		}

		this.isListening = false;
		this.status.isListening = false;
		this.updateRateHz = 0;
	}

	async resetSteps() {
		if (this.isNative) {
			try {
				await NativeSensors.resetStepCount();
			} catch (e) {
				console.warn(e);
			}
		}
		this.pedometer = {
			steps: 0,
			detectedSteps: 0,
			distanceKm: 0,
			caloriesBurned: 0
		};
		this.stepHistory = Array(20).fill(0);
	}

	async refreshLocation(): Promise<LocationData> {
		if (this.isNative) {
			try {
				const res = await NativeSensors.getLocation();
				if (res && res.hasCoords && res.latitude !== 0) {
					this.location = {
						latitude: res.latitude,
						longitude: res.longitude,
						accuracy: res.accuracy,
						altitude: res.altitude,
						mapsUrl: res.mapsUrl || `https://maps.google.com/?q=${res.latitude},${res.longitude}`,
						hasCoords: true
					};
					return this.location;
				}
			} catch (e) {
				console.warn("Native getLocation failed, trying web fallback:", e);
			}
		}

		if (typeof navigator !== "undefined" && "geolocation" in navigator) {
			try {
				const pos = await new Promise<GeolocationPosition>((resolve, reject) => {
					navigator.geolocation.getCurrentPosition(resolve, reject, {
						enableHighAccuracy: true,
						timeout: 4000,
						maximumAge: 30000
					});
				});
				const lat = pos.coords.latitude;
				const lon = pos.coords.longitude;
				this.location = {
					latitude: lat,
					longitude: lon,
					accuracy: pos.coords.accuracy,
					altitude: pos.coords.altitude ?? undefined,
					mapsUrl: `https://maps.google.com/?q=${lat},${lon}`,
					hasCoords: true
				};
				return this.location;
			} catch (e) {
				console.debug("Geolocation unavailable:", e);
			}
		}

		return this.location;
	}

	private handleSensorData(data: FullSensorPayload) {
		this.accelerometer = data.accelerometer;
		this.gyroscope = data.gyroscope;
		this.magnetometer = data.magnetometer;
		this.ambientLight = data.ambientLight;
		this.pedometer = data.pedometer;
		this.lastUpdateTimestamp = data.timestamp;
		this.isListening = data.isListening;

		if (data.location && data.location.hasCoords) {
			this.location = data.location;
		}

		// Append to history buffers with immutable slice to pair with $state.raw for ultra-fast render cycles
		this.accelHistory = this.pushHistory(this.accelHistory, data.accelerometer.magnitude);
		this.gyroHistory = this.pushHistory(this.gyroHistory, data.gyroscope.rate);
		this.magHistory = this.pushHistory(this.magHistory, data.magnetometer.fieldStrength);
		this.lightHistory = this.pushHistory(this.lightHistory, data.ambientLight.lux);
		this.stepHistory = this.pushHistory(this.stepHistory, data.pedometer.steps);

		this.updateCount++;
	}

	private pushHistory(arr: number[], val: number): number[] {
		if (arr.length >= 25) {
			return [...arr.slice(1), val];
		}
		return [...arr, val];
	}

	private startRateMeter() {
		if (this.rateMeterInterval) clearInterval(this.rateMeterInterval);
		this.rateMeterInterval = setInterval(() => {
			if (!this.isListening) {
				this.updateRateHz = 0;
				return;
			}
			const now = Date.now();
			const elapsedSec = (now - this.lastRateCheck) / 1000;
			if (elapsedSec > 0) {
				this.updateRateHz = Math.round(this.updateCount / elapsedSec);
			}
			this.updateCount = 0;
			this.lastRateCheck = now;
		}, 1000);
	}

	startSimulatedEngine() {
		this.isListening = true;
		this.status.isListening = true;
		this.isSimulated = true;

		let stepCount = this.pedometer.steps;
		let angle = 0;
		let luxBase = 320;

		this.simInterval = setInterval(() => {
			angle += 0.1;
			const wobble = Math.sin(angle * 2.5) * 1.8;
			const ax = Math.round(Math.sin(angle) * 1.5 * 100) / 100;
			const ay = Math.round(Math.cos(angle * 1.2) * 2.1 * 100) / 100;
			const az = Math.round((9.8 + wobble) * 100) / 100;
			const accelMag = Math.round(Math.sqrt(ax * ax + ay * ay + az * az) * 100) / 100;

			const gx = Math.round(Math.sin(angle * 0.8) * 0.45 * 100) / 100;
			const gy = Math.round(Math.cos(angle * 1.4) * 0.35 * 100) / 100;
			const gz = Math.round(Math.sin(angle * 2.0) * 0.25 * 100) / 100;
			const gyroRate = Math.round(Math.sqrt(gx * gx + gy * gy + gz * gz) * 100) / 100;

			const heading = Math.round(((Math.sin(angle * 0.3) * 180 + 180) % 360) * 10) / 10;
			const mx = Math.round(Math.cos(angle * 0.3) * 28 * 100) / 100;
			const my = Math.round(Math.sin(angle * 0.3) * 35 * 100) / 100;
			const mz = -42.5;
			const magStrength = Math.round(Math.sqrt(mx * mx + my * my + mz * mz) * 100) / 100;

			// Ambient light variation
			const lux = Math.max(5, Math.round(luxBase + Math.sin(angle * 0.2) * 120));
			let env = "Living Room / Normal Indoor";
			if (lux < 50) env = "Dim / Dark Indoors";
			else if (lux > 500) env = "Bright Office / Daylight";

			// Pedometer: step every ~1.2s
			if (Math.abs(wobble) > 1.4) {
				stepCount++;
			}
			const dist = Math.round(((stepCount * 0.75) / 1000) * 100) / 100;
			const cal = Math.round(stepCount * 0.04 * 10) / 10;

			const payload: FullSensorPayload = {
				accelerometer: { x: ax, y: ay, z: az, magnitude: accelMag },
				gyroscope: { x: gx, y: gy, z: gz, rate: gyroRate },
				magnetometer: {
					x: mx,
					y: my,
					z: mz,
					fieldStrength: magStrength,
					heading,
					cardinal: this.getHeadingCardinal(heading)
				},
				ambientLight: { lux, environment: env },
				pedometer: {
					steps: stepCount,
					detectedSteps: stepCount,
					distanceKm: dist,
					caloriesBurned: cal
				},
				timestamp: Date.now(),
				isListening: true
			};

			this.handleSensorData(payload);
		}, 80);
	}

	private getHeadingCardinal(deg: number): string {
		if (deg >= 337.5 || deg < 22.5) return "N";
		if (deg >= 22.5 && deg < 67.5) return "NE";
		if (deg >= 67.5 && deg < 112.5) return "E";
		if (deg >= 112.5 && deg < 157.5) return "SE";
		if (deg >= 157.5 && deg < 202.5) return "S";
		if (deg >= 202.5 && deg < 247.5) return "SW";
		if (deg >= 247.5 && deg < 292.5) return "W";
		return "NW";
	}

	toggleBackendSync() {
		this.backendSyncEnabled = !this.backendSyncEnabled;
		if (this.backendSyncEnabled) {
			this.startBackendSync();
		} else {
			if (this.syncInterval) {
				clearInterval(this.syncInterval);
				this.syncInterval = null;
			}
			this.syncStatus = "idle";
			this.syncMessage = "Sync stopped";
		}
	}

	startBackendSync() {
		if (this.syncInterval) clearInterval(this.syncInterval);
		this.syncStatus = "syncing";
		this.syncMessage = "Connecting to backend...";

		// Send telemetry payload every 1 second
		this.syncInterval = setInterval(async () => {
			if (!this.backendSyncEnabled || !this.isListening) return;
			if (!appSettings.backendUrl) {
				this.syncStatus = "error";
				this.syncMessage = "Backend URL not set (Settings)";
				return;
			}

			const payload = {
				deviceId: appSettings.deviceId,
				platform: this.isNative ? "android-capacitor" : "web-preview",
				timestamp: this.lastUpdateTimestamp,
				sensors: {
					accelerometer: this.accelerometer,
					gyroscope: this.gyroscope,
					magnetometer: this.magnetometer,
					ambientLight: this.ambientLight,
					pedometer: this.pedometer
				}
			};

			try {
				const res = await fetch(`${appSettings.backendUrl}/api/telemetry`, {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify(payload)
				});
				if (res.ok) {
					this.syncStatus = "connected";
					this.syncMessage = `Synced at ${new SvelteDate().toLocaleTimeString()}`;
				} else {
					this.syncStatus = "error";
					this.syncMessage = `HTTP ${res.status}`;
				}
			} catch (err: unknown) {
				this.syncStatus = "error";
				this.syncMessage = err instanceof Error ? err.message : "Sync failed";
			}
		}, 1000);
	}

	destroy() {
		this.stop();
		if (this.listenerHandle) {
			this.listenerHandle.remove();
		}
	}
}

export const sensorManager = new SensorManager();
