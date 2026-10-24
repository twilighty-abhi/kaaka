import { appSettings } from "./appSettings.svelte.js";
import { sensorManager } from "./sensorManager.svelte.js";
import { telemetryBeacon } from "./telemetryBeaconService.svelte.js";

const FALL_KEY = "kaaka_auto_sos_on_fall";
const SAFETY_DEADLINE_KEY = "kaaka_safety_deadline";
const SAFETY_MINUTES_KEY = "kaaka_safety_minutes";

// Fall heuristic (simple on purpose, tune on real devices):
// an impact above IMPACT_MS2 followed by STILL_MS of near-stillness within FALL_WINDOW_MS.
const GRAVITY = 9.81;
const IMPACT_MS2 = 2.5 * GRAVITY; // ~24.5 m/s²
const SETTLE_MS = 300; // ignore the bounce right after the impact
const STILL_MS = 2000;
const STILL_ACCEL_TOLERANCE = 1.5; // |magnitude - g| below this counts as still
const STILL_GYRO_MAX = 0.6; // rad/s
const FALL_WINDOW_MS = 6000;

/** Why a countdown to SOS is running. Only one countdown runs at a time. */
export type CountdownReason = "fall" | "safety timer";
const COUNTDOWN_S: Record<CountdownReason, number> = { fall: 15, "safety timer": 30 };

/** A safety timer that expired longer ago than this (app closed meanwhile) no longer sends SOS by itself. */
const STALE_EXPIRY_MS = 12 * 60 * 60_000;
const DEFAULT_SAFETY_MINUTES = 30;

function loadFlag(key: string): boolean {
	try {
		return localStorage.getItem(key) === "1";
	} catch {
		return false;
	}
}

function loadNumber(key: string): number | null {
	try {
		const n = Number(localStorage.getItem(key));
		return n > 0 ? n : null;
	} catch {
		return null;
	}
}

function store(key: string, value: string | null) {
	try {
		if (value === null) localStorage.removeItem(key);
		else localStorage.setItem(key, value);
	} catch {
		// keep in memory only
	}
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

class EmergencyService {
	/** Auto SOS when a fall is detected (default off). Only works while the app is open. */
	autoSosOnFall = $state(loadFlag(FALL_KEY));
	/** The running countdown to SOS (fall or safety timer), or null. */
	countdown = $state<{ reason: CountdownReason; seconds: number } | null>(null);
	/** Safety timer deadline (ms epoch) while it runs, or null. Persisted so it survives the app being closed. */
	safetyDeadline = $state<number | null>(loadNumber(SAFETY_DEADLINE_KEY));
	/** Last chosen safety timer length. */
	safetyMinutes = $state(loadNumber(SAFETY_MINUTES_KEY) ?? DEFAULT_SAFETY_MINUTES);
	status = $state<{ type: "success" | "error" | "info"; text: string } | null>(null);

	private impactAt: number | null = null;
	private stillSince: number | null = null;
	private countdownTimer: ReturnType<typeof setInterval> | null = null;
	private safetyTimer: ReturnType<typeof setInterval> | null = null;
	private sosInFlight: Promise<boolean> | null = null;

	constructor() {
		sensorManager.onSample = (accel, gyro, t) => this.onSample(accel, gyro, t);
		// A user stopping the beacon means they are fine: clear every pending timer.
		telemetryBeacon.onStoppedByUser = () => this.clearAllTimers();
		this.restoreSafetyTimer();
		if (typeof document !== "undefined") {
			// Timers are throttled in the background; re-check the deadline as soon as the app is visible again.
			document.addEventListener("visibilitychange", () => {
				if (document.visibilityState === "visible") this.checkSafetyDeadline();
			});
		}
	}

	setAutoSosOnFall(enabled: boolean) {
		this.autoSosOnFall = enabled;
		store(FALL_KEY, enabled ? "1" : "0");
		if (!enabled && this.countdown?.reason === "fall") this.cancelCountdown();
	}

	/**
	 * Sends one Kaaka Alert report to the gateway number now and starts the beacon
	 * (or sends an extra report if it already runs). Calls made while one is in flight share it.
	 */
	triggerSos(reason: "sos" | "fall" | "safety timer" = "sos"): Promise<boolean> {
		if (!this.sosInFlight) {
			this.sosInFlight = this.sendSos(reason).finally(() => (this.sosInFlight = null));
		}
		return this.sosInFlight;
	}

	private async sendSos(reason: "sos" | "fall" | "safety timer"): Promise<boolean> {
		const gateway = appSettings.gatewayNumber.trim();
		if (!gateway) {
			this.status = { type: "error", text: "Gateway number not set. Add it in Settings first." };
			return false;
		}
		let ok: boolean;
		if (telemetryBeacon.isActive) {
			// Never start a second beacon; wait for a report that is being sent, then send one more.
			while (telemetryBeacon.isSending) await sleep(200);
			ok = await telemetryBeacon.sendImmediateUpdate();
		} else {
			telemetryBeacon.targetNumber = gateway;
			telemetryBeacon.startBeacon(gateway, reason);
			// startBeacon sends report #1 itself; wait for it to finish to report the result.
			await sleep(0);
			while (telemetryBeacon.isSending) await sleep(200);
			ok = telemetryBeacon.isActive && telemetryBeacon.updatesSentCount > 0;
		}
		this.status = ok
			? { type: "success", text: `SOS sent to ${gateway}. Beacon running.` }
			: { type: "error", text: telemetryBeacon.status?.text || "SOS could not be sent (check SMS permission)." };
		return ok;
	}

	/** Cancels the running countdown ("I'm OK"). */
	cancelCountdown() {
		const reason = this.countdown?.reason;
		this.stopCountdownTimer();
		this.impactAt = null;
		this.stillSince = null;
		if (reason === "fall") this.status = { type: "info", text: "Fall alert cancelled." };
		if (reason === "safety timer") this.status = { type: "info", text: "Safety alert cancelled. Glad you're safe." };
	}

	/** Starts a countdown to SOS unless one is already running (countdowns never stack). */
	private startCountdown(reason: CountdownReason) {
		if (this.countdown !== null) return;
		this.countdown = { reason, seconds: COUNTDOWN_S[reason] };
		this.countdownTimer = setInterval(() => {
			if (this.countdown === null) return;
			if (this.countdown.seconds > 1) {
				this.countdown = { reason, seconds: this.countdown.seconds - 1 };
				return;
			}
			this.stopCountdownTimer();
			this.triggerSos(reason);
		}, 1000);
	}

	private stopCountdownTimer() {
		if (this.countdownTimer) clearInterval(this.countdownTimer);
		this.countdownTimer = null;
		this.countdown = null;
	}

	// ---- Safety timer (check-in) ----

	/** Starts the safety timer: if the user does not check in before it ends, a 30 s countdown then SOS. */
	startSafetyTimer(minutes: number): boolean {
		const m = Math.round(minutes);
		if (!(m > 0)) {
			this.status = { type: "error", text: "Choose a safety timer length in minutes." };
			return false;
		}
		if (!appSettings.gatewayNumber.trim()) {
			this.status = { type: "error", text: "Gateway number not set. Add it in Settings first." };
			return false;
		}
		this.safetyMinutes = m;
		store(SAFETY_MINUTES_KEY, String(m));
		this.setSafetyDeadline(Date.now() + m * 60_000);
		this.status = { type: "info", text: `Safety timer started for ${m} min. Check in before it ends.` };
		return true;
	}

	/** "I'm safe": stops the safety timer (and its countdown if it already began). */
	checkIn() {
		const wasRunning = this.safetyDeadline !== null || this.countdown?.reason === "safety timer";
		this.setSafetyDeadline(null);
		if (this.countdown?.reason === "safety timer") this.stopCountdownTimer();
		if (wasRunning) this.status = { type: "success", text: "Checked in. Safety timer stopped." };
	}

	extendSafetyTimer(minutes = 15) {
		if (this.safetyDeadline === null) return;
		this.setSafetyDeadline(this.safetyDeadline + minutes * 60_000);
		this.status = { type: "info", text: `Safety timer extended by ${minutes} min.` };
	}

	private setSafetyDeadline(deadline: number | null) {
		this.safetyDeadline = deadline;
		store(SAFETY_DEADLINE_KEY, deadline === null ? null : String(deadline));
		if (this.safetyTimer) clearInterval(this.safetyTimer);
		this.safetyTimer = deadline === null ? null : setInterval(() => this.checkSafetyDeadline(), 1000);
	}

	private checkSafetyDeadline() {
		if (this.safetyDeadline === null || Date.now() < this.safetyDeadline) return;
		this.setSafetyDeadline(null);
		this.status = { type: "error", text: "Safety timer ended without a check-in." };
		this.startCountdown("safety timer");
	}

	/** On app start: resume a running timer, or handle one that ended while the app was closed. */
	private restoreSafetyTimer() {
		const deadline = this.safetyDeadline;
		if (deadline === null) return;
		const overdue = Date.now() - deadline;
		if (overdue < 0) {
			this.setSafetyDeadline(deadline);
			return;
		}
		this.setSafetyDeadline(null);
		const at = new Date(deadline).toLocaleTimeString();
		if (overdue > STALE_EXPIRY_MS) {
			this.status = {
				type: "info",
				text: `A safety timer ended at ${at} while the app was closed, over 12 h ago. No SOS was sent.`
			};
			return;
		}
		this.status = {
			type: "error",
			text: `Safety timer ended at ${at} while the app was closed. Sending SOS unless you cancel.`
		};
		this.startCountdown("safety timer");
	}

	/** Stops every pending timer: countdown, safety timer and fall tracking. */
	private clearAllTimers() {
		this.stopCountdownTimer();
		this.setSafetyDeadline(null);
		this.impactAt = null;
		this.stillSince = null;
	}

	// ---- Fall detection ----

	private onSample(accel: number, gyro: number, t: number) {
		if (!this.autoSosOnFall || this.countdown !== null || telemetryBeacon.isActive) return;

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
			this.startCountdown("fall");
		}
	}
}

export const emergencyService = new EmergencyService();
