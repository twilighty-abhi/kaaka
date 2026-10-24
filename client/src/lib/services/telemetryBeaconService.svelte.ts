import { sensorManager } from "./sensorManager.svelte.js";
import { sendSms } from "./smsService.js";
import { appSettings, sendToServer } from "./appSettings.svelte.js";

const DURATION_KEY = "kaaka_beacon_minutes";
const INTERVAL_KEY = "kaaka_beacon_interval";
// Seconds between reports; faster updates help when the person is moving (e.g. in a vehicle).
export const BEACON_INTERVALS = [15, 30, 60] as const;
const DEFAULT_INTERVAL_S = 60;
const DEFAULT_DURATION_MIN = 30;
// Do not hold the first report back for a GPS fix: send what we have after this long.
const LOCATION_WAIT_MS = 5000;

function loadDuration(): number {
	try {
		const n = Number(localStorage.getItem(DURATION_KEY));
		return n > 0 ? n : DEFAULT_DURATION_MIN;
	} catch {
		return DEFAULT_DURATION_MIN;
	}
}

function loadInterval(): number {
	try {
		const n = Number(localStorage.getItem(INTERVAL_KEY));
		return (BEACON_INTERVALS as readonly number[]).includes(n) ? n : DEFAULT_INTERVAL_S;
	} catch {
		return DEFAULT_INTERVAL_S;
	}
}

export type BeaconTrigger = "manual" | "sos" | "fall" | "safety timer" | "gateway reply";

export class TelemetryBeaconService {
	// Svelte 5 runes for reactive state
	isActive = $state(false);
	targetNumber = $state(appSettings.gatewayNumber);
	intervalSeconds = $state(loadInterval());
	secondsRemaining = $state(loadInterval());
	updatesSentCount = $state(0);
	lastSentTime = $state<string | null>(null);
	lastReport = $state<string | null>(null);
	status = $state<{ type: "success" | "error" | "info"; text: string } | null>(null);
	isSending = $state(false);
	/** Beacon stops by itself after this many minutes. */
	durationMinutes = $state(loadDuration());
	/** When the running beacon will stop (ms epoch), or null. */
	endsAt = $state<number | null>(null);
	/** Why the beacon was started; included in every report. */
	trigger = $state<BeaconTrigger>("manual");

	/** Called when the user stops the beacon (not when it ends by itself), e.g. to clear SOS timers. */
	onStoppedByUser: (() => void) | null = null;

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
		} else {
			lines.push("• Location: unavailable");
		}
		lines.push(`• Trigger: ${this.trigger}`);

		return lines.join("\n");
	}

	async sendUpdate(): Promise<boolean> {
		if (this.isSending) return false;
		const target = this.targetNumber.trim();
		if (!target) {
			this.status = { type: "error", text: "Gateway number not set. Enter it here or in Settings." };
			return false;
		}
		this.isSending = true;

		// Ensure sensors and location are fresh
		if (!sensorManager.isListening) {
			await sensorManager.start();
		}
		// Refresh GPS, but send anyway after LOCATION_WAIT_MS (later reports pick up the fix).
		await Promise.race([
			sensorManager.refreshLocation().catch(() => undefined),
			new Promise((resolve) => setTimeout(resolve, LOCATION_WAIT_MS))
		]);

		const report = this.buildReport();
		this.lastReport = report;

		// 1. Direct WebSocket copy to the Mac server (only if a server address is configured)
		sendToServer({ type: "CLIENT_TELEMETRY", report, sender: "Phone B (Client)" });

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

	setIntervalSeconds(seconds: number) {
		if (!(BEACON_INTERVALS as readonly number[]).includes(seconds)) return;
		this.intervalSeconds = seconds;
		try {
			localStorage.setItem(INTERVAL_KEY, String(seconds));
		} catch {
			// keep in memory only
		}
		if (this.isActive && this.secondsRemaining > seconds) this.secondsRemaining = seconds;
	}

	setDuration(minutes: number) {
		const n = Math.round(minutes);
		if (!(n > 0)) return;
		this.durationMinutes = n;
		try {
			localStorage.setItem(DURATION_KEY, String(n));
		} catch {
			// keep in memory only
		}
		if (this.isActive) this.endsAt = Date.now() + n * 60_000;
	}

	startBeacon(target?: string, trigger: BeaconTrigger = "manual") {
		if (target) {
			const clean = target.replace(/[^0-9]/g, "");
			if (clean) this.targetNumber = clean.length >= 10 ? clean.slice(-10) : clean;
		} else if (!this.targetNumber) {
			this.targetNumber = appSettings.gatewayNumber;
		}
		if (!this.targetNumber.trim()) {
			this.status = { type: "error", text: "Gateway number not set. Enter it here or in Settings." };
			return;
		}
		if (this.isActive) return;
		this.trigger = trigger;

		// Ensure sensors are actively capturing
		if (!sensorManager.isListening) {
			sensorManager.start();
		}

		this.isActive = true;
		this.updatesSentCount = 0;
		this.lastSentTime = null;
		this.secondsRemaining = this.intervalSeconds;
		this.endsAt = Date.now() + this.durationMinutes * 60_000;
		this.status = {
			type: "info",
			text: `Emergency beacon active. Updating every ${this.intervalSeconds}s for ${this.durationMinutes} min.`
		};

		// Send Update #1 immediately
		this.sendUpdate();

		// Countdown tick timer (1s)
		if (this.countdownTimer) clearInterval(this.countdownTimer);
		this.countdownTimer = setInterval(() => {
			if (!this.isActive) return;
			if (this.endsAt && Date.now() >= this.endsAt) {
				this.stopBeacon(`Beacon finished after ${this.durationMinutes} min.`, false);
				return;
			}
			if (this.secondsRemaining > 1) {
				this.secondsRemaining--;
			} else {
				this.secondsRemaining = this.intervalSeconds;
				this.sendUpdate();
			}
		}, 1000);
	}

	stopBeacon(reason = "Telemetry beacon stopped.", byUser = true) {
		this.isActive = false;
		this.endsAt = null;
		if (this.countdownTimer) {
			clearInterval(this.countdownTimer);
			this.countdownTimer = null;
		}
		this.secondsRemaining = this.intervalSeconds;
		this.status = {
			type: "info",
			text: `${reason} Total updates sent: ${this.updatesSentCount}`
		};
		if (byUser) this.onStoppedByUser?.();
	}
}

export const telemetryBeacon = new TelemetryBeaconService();
