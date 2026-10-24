import { Capacitor, registerPlugin } from "@capacitor/core";

interface DirectSmsPlugin {
	sendSms(options: { number: string; message: string }): Promise<{ success: boolean }>;
}

const DirectSms = registerPlugin<DirectSmsPlugin>("DirectSms");

export interface SendSmsResult {
	success: boolean;
	message: string;
}

export async function sendSms(phoneNumber: string, messageText: string): Promise<SendSmsResult> {
	const sanitizedNumber = phoneNumber.trim().replace(/[^0-9+*#]/g, "");
	const content = messageText.trim();

	if (!sanitizedNumber) {
		return { success: false, message: "Please enter a valid recipient phone number" };
	}
	if (!content) {
		return { success: false, message: "SMS message content cannot be empty" };
	}

	if (Capacitor.isNativePlatform()) {
		try {
			await DirectSms.sendSms({
				number: sanitizedNumber,
				message: content
			});
			return { success: true, message: `SMS sent successfully to ${sanitizedNumber}` };
		} catch (err: unknown) {
			const errorMsg = err instanceof Error ? err.message : String(err);
			return { success: false, message: errorMsg || "Failed to send SMS" };
		}
	} else {
		// Browser fallback: open SMS URI scheme
		try {
			const smsUri = `sms:${sanitizedNumber}?body=${encodeURIComponent(content)}`;
			window.location.href = smsUri;
			return { success: true, message: `SMS draft opened for ${sanitizedNumber}` };
		} catch {
			return { success: false, message: "Unable to open SMS client in this browser" };
		}
	}
}
