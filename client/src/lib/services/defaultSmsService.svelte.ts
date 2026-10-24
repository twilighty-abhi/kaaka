import { registerPlugin, Capacitor, type PluginListenerHandle } from "@capacitor/core";
import { telemetryBeacon } from "./telemetryBeaconService.svelte.js";
import { appSettings } from "./appSettings.svelte.js";

export interface SmsTriggerEvent {
	sender: string;
	message: string;
	timestamp: number;
	timeFormatted: string;
}

export interface DefaultSmsPluginInterface {
	isDefaultSms(): Promise<{ isDefault: boolean }>;
	requestDefaultSms(): Promise<void>;
	getLastTrigger(): Promise<{ sender?: string; message?: string; timestamp?: number }>;
	addListener(
		eventName: "smsReceived",
		listenerFunc: (data: { sender: string; message: string; timestamp: number }) => void
	): Promise<PluginListenerHandle>;
}

const DefaultSms = registerPlugin<DefaultSmsPluginInterface>("DefaultSms");

/** True if sender matches the configured gateway number (last 10 digits). False when none is set. */
export function isGatewaySender(sender: string): boolean {
	const gateway = appSettings.gatewayNumber.replace(/[^0-9]/g, "").slice(-10);
	const digits = (sender || "").replace(/[^0-9]/g, "");
	return gateway.length > 0 && digits.endsWith(gateway);
}

class DefaultSmsManager {
	isDefault = $state(false);
	statusChecked = $state(false);
	triggerCount = $state(0);
	lastTrigger = $state.raw<SmsTriggerEvent | null>(null);
	triggerHistory = $state.raw<SmsTriggerEvent[]>([]);

	private listenerHandle: PluginListenerHandle | null = null;
	private pollInterval: ReturnType<typeof setInterval> | null = null;

	get isNative(): boolean {
		return Capacitor.isNativePlatform();
	}

	async initialize() {
		await this.checkStatus();

		if (this.isNative) {
			try {
				this.listenerHandle = await DefaultSms.addListener("smsReceived", (event) => {
					this.handleTrigger(event);
				});

				await DefaultSms.addListener("stopBeaconTriggered" as any, () => {
					telemetryBeacon.stopBeacon();
				});

				const last = await DefaultSms.getLastTrigger();
				if (last && last.sender) {
					const ageMs = Date.now() - (last.timestamp || 0);
					// Only handle if triggered recently (<90 seconds ago, e.g. launched app)
					if (ageMs < 90000) {
						this.handleTrigger({
							sender: last.sender,
							message: last.message || "",
							timestamp: last.timestamp || Date.now()
						});
					}
				}
			} catch (err) {
				console.warn("[DefaultSmsManager] failed to attach native listener:", err);
			}

			// Periodic check for default status changes
			if (!this.pollInterval) {
				this.pollInterval = setInterval(() => {
					this.checkStatus();
				}, 3000);
			}
		}
	}

	async checkStatus() {
		if (this.isNative) {
			try {
				const res = await DefaultSms.isDefaultSms();
				this.isDefault = !!res?.isDefault;
				this.statusChecked = true;
			} catch (err) {
				console.warn("[DefaultSmsManager] checkStatus failed:", err);
				this.statusChecked = true;
			}
		} else {
			// Web fallback / preview
			this.statusChecked = true;
		}
	}

	async requestDefault() {
		if (this.isNative) {
			try {
				await DefaultSms.requestDefaultSms();
				setTimeout(() => this.checkStatus(), 1500);
			} catch (err) {
				console.error("[DefaultSmsManager] requestDefault failed:", err);
			}
		} else {
			// Web preview toggle for testing
			this.isDefault = !this.isDefault;
		}
	}

	handleTrigger(event: { sender: string; message: string; timestamp?: number }) {
		const timestamp = event.timestamp || Date.now();
		if (this.lastTrigger && this.lastTrigger.timestamp === timestamp) {
			return; // Avoid double triggering on same SMS event
		}

		const formatted: SmsTriggerEvent = {
			sender: event.sender,
			message: event.message,
			timestamp,
			timeFormatted: new Date(timestamp).toLocaleTimeString()
		};

		this.triggerCount++;
		this.lastTrigger = formatted;
		this.triggerHistory = [formatted, ...this.triggerHistory.slice(0, 9)];

		// Start the emergency telemetry beacon ONLY for SMS from the configured gateway number,
		// and always send reports to that gateway number (never to the SMS sender).
		if (isGatewaySender(event.sender)) {
			telemetryBeacon.startBeacon(appSettings.gatewayNumber);
		}
	}

	simulateTestTrigger(sender: string, message = "TEST EMERGENCY ALERT: Fall detected!") {
		this.handleTrigger({
			sender,
			message,
			timestamp: Date.now()
		});
	}

	destroy() {
		if (this.pollInterval) {
			clearInterval(this.pollInterval);
			this.pollInterval = null;
		}
		if (this.listenerHandle) {
			this.listenerHandle.remove();
			this.listenerHandle = null;
		}
	}
}

export const defaultSmsManager = new DefaultSmsManager();
