import { registerPlugin, Capacitor } from "@capacitor/core";

// User-configured connection settings, persisted in localStorage.
// Defaults are empty on purpose: nothing is sent until the user fills these in.
const STORAGE_KEY = "kaaka_settings";

const DefaultSms = registerPlugin<{ setAuthorizedNumber(options: { number: string }): Promise<void> }>("DefaultSms");

class AppSettings {
	/** Gateway phone number: SMS alert recipient and the authorized trigger sender. */
	gatewayNumber = $state("");
	/** Mac server WebSocket URL, e.g. ws://<mac-ip>:8765 */
	serverUrl = $state("");
	/** Telemetry backend URL, e.g. http://<mac-ip>:3001 */
	backendUrl = $state("");
	/** Random per-install id sent with backend telemetry. */
	deviceId = $state("");

	constructor() {
		this.load();
	}

	load() {
		try {
			const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
			this.gatewayNumber = saved.gatewayNumber || "";
			this.serverUrl = saved.serverUrl || "";
			this.backendUrl = saved.backendUrl || "";
			this.deviceId = saved.deviceId || "";
		} catch {
			// localStorage unavailable (SSR / private mode): keep empty defaults
		}
		if (!this.deviceId && typeof crypto !== "undefined" && "randomUUID" in crypto) {
			this.deviceId = `android-${crypto.randomUUID()}`;
			this.persist();
		}
		this.syncNative();
	}

	save(values: { gatewayNumber: string; serverUrl: string; backendUrl: string }) {
		this.gatewayNumber = values.gatewayNumber.trim();
		this.serverUrl = values.serverUrl.trim();
		this.backendUrl = values.backendUrl.trim().replace(/\/+$/, "");
		this.persist();
		this.syncNative();
	}

	private persist() {
		try {
			localStorage.setItem(
				STORAGE_KEY,
				JSON.stringify({
					gatewayNumber: this.gatewayNumber,
					serverUrl: this.serverUrl,
					backendUrl: this.backendUrl,
					deviceId: this.deviceId
				})
			);
		} catch {
			// ignore: settings stay in memory for this session
		}
	}

	// The native SmsReceiver checks the sender against this number, so mirror it to SharedPreferences.
	private syncNative() {
		if (!Capacitor.isNativePlatform()) return;
		DefaultSms.setAuthorizedNumber({ number: this.gatewayNumber }).catch((err) =>
			console.warn("[AppSettings] failed to sync authorized number to native:", err)
		);
	}
}

export const appSettings = new AppSettings();

/** Send a JSON message to the Mac server over WebSocket. Returns false if no server is configured. */
export function sendToServer(payload: object): boolean {
	if (!appSettings.serverUrl) return false;
	try {
		const ws = new WebSocket(appSettings.serverUrl);
		ws.onopen = () => {
			ws.send(JSON.stringify(payload));
			setTimeout(() => ws.close(), 1500);
		};
		ws.onerror = () => console.warn("[sendToServer] could not reach", appSettings.serverUrl);
	} catch (err) {
		console.warn("[sendToServer] invalid server URL:", appSettings.serverUrl, err);
	}
	return true;
}
