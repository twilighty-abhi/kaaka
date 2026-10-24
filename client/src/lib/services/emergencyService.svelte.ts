import { appSettings } from "./appSettings.svelte.js";
import { sensorManager } from "./sensorManager.svelte.js";
import { telemetryBeacon } from "./telemetryBeaconService.svelte.js";

const FALL_KEY = "kaaka_auto_sos_on_fall";

// Fall heuristic (simple on purpose, tune on real devices):
// an impact above IMPACT_MS2 followed by STILL_MS of near-stillness within FALL_WINDOW_MS.
const GRAVITY = 9.81;
const IMPACT_MS2 = 2.5 * GRAVITY; // ~24.5 m/s²
const SETTLE_MS = 300; // ignore the bounce right after the impact
const STILL_MS = 2000;
const STILL_ACCEL_TOLERANCE = 1.5; // |magnitude - g| below this counts as still
const STILL_GYRO_MAX = 0.6; // rad/s
const FALL_WINDOW_MS = 6000;
const COUNTDOWN_S = 15;

function loadAutoSos(): boolean {
	try {
		return localStorage.getItem(FALL_KEY) === "1";
	} catch {
		return false;
	}
}

class EmergencyService {
	/** Auto SOS when a fall is detected (default off). Only works while the app is open. */
	autoSosOnFall = $state(loadAutoSos());
	/** Seconds left before a detected fall sends SOS, or null when no countdown is running. */
	fallCountdown = $state<number | null>(null);
	status = $state<{ type: "success" | "error" | "info"; text: string } | null>(null);

	private impactAt: number | null = null;
	private stillSince: number | null = null;
	private countdownTimer: ReturnType<typeof setInterval> | null = null;

	constructor() {
		sensorManager.onSample = (accel, gyro, t) => this.onSample(accel, gyro, t);
	}

	setAutoSosOnFall(enabled: boolean) {
		this.autoSosOnFall = enabled;
		try {
			localStorage.setItem(FALL_KEY, enabled ? "1" : "0");
		} catch {
			// keep in memory only
		}
		if (!enabled) this.cancelFall();
	}

	/** Sends one Kaaka Alert report to the gateway number now and starts the beacon. */
	async triggerSos(reason: "sos" | "fall" = "sos"): Promise<boolean> {
		const gateway = appSettings.gatewayNumber.trim();
		if (!gateway) {
			this.status = { type: "error", text: "Gateway number not set. Add it in Settings first." };
			return false;
		}
		let ok: boolean;
		if (telemetryBeacon.isActive) {
			ok = await telemetryBeacon.sendImmediateUpdate();
		} else {
			telemetryBeacon.targetNumber = gateway;
			telemetryBeacon.startBeacon(gateway, reason);
			// startBeacon sends report #1 itself; wait for it to finish to report the result.
			while (telemetryBeacon.isSending) await new Promise((r) => setTimeout(r, 200));
			ok = telemetryBeacon.isActive && telemetryBeacon.updatesSentCount > 0;
		}
		this.status = ok
			? { type: "success", text: `SOS sent to ${gateway}. Beacon running.` }
			: { type: "error", text: telemetryBeacon.status?.text || "SOS could not be sent (check SMS permission)." };
		return ok;
	}

	cancelFall() {
		if (this.countdownTimer) clearInterval(this.countdownTimer);
		this.countdownTimer = null;
		if (this.fallCountdown !== null) {
			this.status = { type: "info", text: "Fall alert cancelled." };
		}
		this.fallCountdown = null;
		this.impactAt = null;
		this.stillSince = null;
	}

	private startFallCountdown() {
		this.fallCountdown = COUNTDOWN_S;
		this.countdownTimer = setInterval(() => {
			if (this.fallCountdown === null) return;
			if (this.fallCountdown > 1) {
				this.fallCountdown--;
				return;
			}
			if (this.countdownTimer) clearInterval(this.countdownTimer);
			this.countdownTimer = null;
			this.fallCountdown = null;
			this.triggerSos("fall");
		}, 1000);
	}

	private onSample(accel: number, gyro: number, t: number) {
		if (!this.autoSosOnFall || this.fallCountdown !== null || telemetryBeacon.isActive) return;

		if (accel > IMPACT_MS2) {
			this.impactAt = t;
			this.stillSince = null;
			return;
		}
		if (this.impactAt === null) return;
		if (t - this.impactAt > FALL_WINDOW_MS) {
			this.impactAt = null;
			this.stillSince = null;
			return;
		}
		if (t - this.impactAt < SETTLE_MS) return;

		const still = Math.abs(accel - GRAVITY) < STILL_ACCEL_TOLERANCE && gyro < STILL_GYRO_MAX;
		if (!still) {
			this.stillSince = null;
			return;
		}
		if (this.stillSince === null) this.stillSince = t;
		if (t - this.stillSince >= STILL_MS) {
			this.impactAt = null;
			this.stillSince = null;
			this.startFallCountdown();
		}
	}
}

export const emergencyService = new EmergencyService();
