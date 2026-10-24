import { sensorManager } from "./sensorManager.svelte.js";
import { sendSms } from "./smsService.js";

export class TelemetryBeaconService {
	// Svelte 5 runes for reactive state
	isActive = $state(false);
	targetNumber = $state("9495364448");
	intervalSeconds = $state(60);
	secondsRemaining = $state(60);
	updatesSentCount = $state(0);
	lastSentTime = $state<string | null>(null);
	lastReport = $state<string | null>(null);
	status = $state<{ type: "success" | "error" | "info"; text: string } | null>(null);
	isSending = $state(false);

	private countdownTimer: ReturnType<typeof setInterval> | null = null;

	buildReport(): string {
		const steps = sensorManager.pedometer.steps;
		const distance = sensorManager.pedometer.distanceKm.toFixed(2);
		const lux = Math.round(sensorManager.ambientLight.lux);
		const accel = sensorManager.accelerometer.magnitude.toFixed(1);
		const gyro = sensorManager.gyroscope.rate.toFixed(1);
		const heading = Math.round(sensorManager.magnetometer.heading);
		const cardinal = sensorManager.magnetometer.cardinal;
		const loc = sensorManager.location;

		const lines = [
			"Kaaka Alert: Emergency assistance requested",
			"",
			"Live Sensors (5/5):",
			`• Pedometer: ${steps} steps (${distance} km)`,
			`• Light: ${lux} lx`,
			`• Accelerometer: ${accel} m/s²`,
			`• Gyroscope: ${gyro} rad/s`,
			`• Magnetometer: ${heading}° ${cardinal}`
		];

		if (loc && loc.hasCoords && loc.latitude !== 0) {
			lines.push(`• Coords: ${loc.latitude.toFixed(6)}, ${loc.longitude.toFixed(6)}`);
			lines.push(`• Maps: https://maps.google.com/?q=${loc.latitude.toFixed(6)},${loc.longitude.toFixed(6)}`);
		}

		return lines.join("\n");
	}

	async sendUpdate(): Promise<boolean> {
		if (this.isSending) return false;
		this.isSending = true;

		// Ensure sensors and location are fresh
		if (!sensorManager.isListening) {
			await sensorManager.start();
		}
		await sensorManager.refreshLocation();

		const report = this.buildReport();
		this.lastReport = report;
		const target = this.targetNumber.trim() || "9495364448";

		// 1. Direct WebSocket fallback to server (if on same local Wi-Fi)
		for (const host of ["192.168.2.7", "192.168.2.38"]) {
			try {
				const ws = new WebSocket(`ws://${host}:8765`);
				ws.onopen = () => {
					ws.send(JSON.stringify({
						type: "CLIENT_TELEMETRY",
						report,
						sender: "Phone B (Client)"
					}));
					setTimeout(() => ws.close(), 1500);
				};
			} catch (e) {
				// ignore offline
			}
		}

		// 2. Cellular SMS dispatch to Gateway (Phone A)
		const res = await sendSms(target, report);
		this.isSending = false;

		const nowStr = new Date().toLocaleTimeString();
		if (res.success) {
			this.updatesSentCount++;
			this.lastSentTime = nowStr;
			this.status = {
				type: "success",
				text: `Update #${this.updatesSentCount} dispatched (${nowStr})`
			};
			return true;
		} else {
			this.status = {
				type: "error",
				text: `Dispatch error: ${res.message}`
			};
			return false;
		}
	}

	async sendImmediateUpdate(): Promise<boolean> {
		const success = await this.sendUpdate();
		if (this.isActive) {
			this.secondsRemaining = this.intervalSeconds;
		}
		return success;
	}

	startBeacon(target?: string) {
		if (target) {
			const clean = target.replace(/[^0-9]/g, "");
			this.targetNumber = clean.length >= 10 ? clean.slice(-10) : (clean || "9495364448");
		}
		if (this.isActive) return;

		// Ensure sensors are actively capturing
		if (!sensorManager.isListening) {
			sensorManager.start();
		}

		this.isActive = true;
		this.secondsRemaining = this.intervalSeconds;
		this.status = {
			type: "info",
			text: `Emergency beacon active. Updating every 60s.`
		};

		// Send Update #1 immediately
		this.sendUpdate();

		// Countdown tick timer (1s)
		if (this.countdownTimer) clearInterval(this.countdownTimer);
		this.countdownTimer = setInterval(() => {
			if (!this.isActive) return;
			if (this.secondsRemaining > 1) {
				this.secondsRemaining--;
			} else {
				this.secondsRemaining = this.intervalSeconds;
				this.sendUpdate();
			}
		}, 1000);
	}

	stopBeacon() {
		this.isActive = false;
		if (this.countdownTimer) {
			clearInterval(this.countdownTimer);
			this.countdownTimer = null;
		}
		this.secondsRemaining = this.intervalSeconds;
		this.status = {
			type: "info",
			text: `Telemetry beacon stopped. Total updates sent: ${this.updatesSentCount}`
		};
	}
}

export const telemetryBeacon = new TelemetryBeaconService();
