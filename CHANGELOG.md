# Change log

Record each meaningful project change during the event, newest first. Update this file in the same commit as the change. Use a real timestamp with timezone, for example `YYYY-MM-DDTHH:MM:SS+05:30`.

## Event build log

## 2026-10-24T21:55:00+05:30 — Make the Android apps' server and phone numbers configurable

- Changed: Removed hardcoded phone numbers, server IPs and device IDs from `client/` and `gateway/`. Client: new Settings card (`SettingsCard.svelte`, `appSettings.svelte.ts`) for gateway phone number, Mac server WebSocket and telemetry backend URL, with a red "Not set" warning; the authorized number is mirrored to native SharedPreferences for `SmsReceiver.java`; telemetry device ID is now a random per-install ID. Gateway: server endpoint starts empty and the app shows "no server" until set; saving a new endpoint reconnects; manual sends without a number show an error instead of using a fallback. `gateway/README.md` rewritten to describe the current app. `client/package-lock.json` resynced with `package.json`.
- Why: Old test-device values were baked into the apps and could send SMS to fixed numbers.
- Validation: `svelte-check` (client): 0 errors, 0 warnings; both apps built with `./gradlew assembleDebug`; repo-wide `git grep` finds none of the old numbers, IPs or paths.
- Limitations: Settings UI not yet checked on a real device; end-to-end SMS/WebSocket not yet tested. The client still starts its telemetry beacon for any SMS containing "call", "alert", "emergency" or "kaaka", from any sender (unchanged behavior, flagged for review).

## 2026-10-24T21:36:00+05:30 — Remove hardcoded phone numbers, addresses and device IDs from the server

- Changed: `server/server.py` no longer contains phone numbers, Bluetooth addresses or adb serials. `--bt-mac`/`KAAKA_BT_MAC` is required; new optional `--client-number`/`KAAKA_CLIENT_NUMBER` and `--adb-serial`/`KAAKA_ADB_SERIAL`. Calls without caller ID stay "unknown" and never trigger an auto-reply SMS (previously they were relabeled with a fixed number that the gateway app could SMS). "Last caller" shows none until a real call and is kept across restarts in `server/last_call.json` (ignored by Git). Simulated calls/telemetry no longer use real numbers. `server/audio_bridge.py` reads the n8n webhook from `KAAKA_WEBHOOK_URL`/`KAAKA_WEBHOOK_FALLBACK_URL` (bridge stays off without it) and the Linux speaker/mic from `KAAKA_SPEAKER_SINK`/`KAAKA_MIC_SOURCE` or the PipeWire defaults. The dashboard shows the configured Bluetooth address and webhook from `/api/status`. Removed a machine-specific Python path from `package.json` and the TTS service (`KAAKA_TTS_PYTHON`). Device-specific wording replaced with "gateway phone"; README documents all settings.
- Why: Values from the original test devices were showing as real data (for example an old number as "last caller extracted").
- Validation: Python compile checks; `git grep` finds none of the old numbers, IPs, MAC or adb serials outside the Android apps (handled separately); restarted the server against the S23: HFP connected, `/api/status` returns `last_call_number: null`, configured `bt_mac`, empty `webhook_url`; dashboard served.
- Limitations: No real call placed after this change. Hardcoded values in the Android apps are being removed in a separate change.

## 2026-10-24T21:28:00+05:30 — Connect hands-free on the first attempt

- Changed: `mac/hfp-bridge` now creates the hands-free object and calls `connect()` one second later (skipping stale attempts), and logs each connection step.
- Why: When the phone's link was already up, the SDP query returned from cache within a millisecond and IOBluetooth silently dropped a `connect()` issued in the same run-loop pass, so the first attempt always timed out (about 28 s to connect).
- Validation: Three bridge runs against the Galaxy S23 connected in 3.4 s, 2.2 s and 2.0 s on attempt 1; server end-to-end run (no calls) connected about 2 s after start.
- Limitations: Answer/hangup/caller ID not re-tested with a real call after this change.

## 2026-10-24T21:40:00+05:30 — Run the call server on macOS via hfp-bridge

- Changed: Added `mac/hfp-bridge` (Swift, IOBluetooth Hands-Free client that emits JSON-line events and accepts answer/hangup/status/quit commands, with a reconnect watchdog and caller-ID via CLIP/CLCC) and `server/mac_telephony.py` (subprocess client). `server/server.py` and `server/audio_bridge.py` guard Linux-only imports and, on macOS, use hfp-bridge for call detection, answer and hangup; auto-answer defaults off on macOS. Added `server/requirements-mac.txt` and a macOS section in the README. Also imported `subprocess` in `server.py`, which the ADB telemetry thread needed (it failed silently before, including on Linux).
- Why: Run the server side on a MacBook (Apple Silicon) with a Galaxy S23 as the hands-free audio gateway.
- Validation: `swift build -c release` with no warnings; Python compile checks; server run against a stub bridge (CALL_DETECTED broadcast, hangup/answer commands, /api/status, missing-binary path); live run with the real bridge and S23 on 2026-10-24: HFP connected, real incoming call detected with caller number, 1-ring hangup sent and call ended. Fresh server run confirmed dashboard title, /api/status and console banner show Kaaka.
- Limitations: No call audio on macOS (SCO unsupported), so the AI voice loop is disabled there. Bluetooth MAP SMS is Linux-only; the gateway app sends the auto-reply SMS. First HFP connect attempt after start can time out (20 s) before the retry succeeds.

## 2026-10-24T21:30:00+05:30 — Import call and telemetry system as Kaaka

- Changed: Imported the existing call and telemetry code from a separate local folder and renamed it to Kaaka during import: `client/` (Capacitor sensor + default-SMS app, app ID `com.kaaka.sensors`), `gateway/` (Capacitor call/SMS gateway app, app ID `com.kaaka.callapp`), `server/` (Python PipeWire/oFono call server, audio bridge, dashboard, Node telemetry backend), `scripts/`, and the project README. Alerts use the "Kaaka Alert:" prefix.
- Why: Consolidate the project into this repository under its new name before porting the server to macOS.
- Validation: Compared against the source folder: the only differences are the name, app ID and Java package changes. Dependency/build folders, prebuilt APKs and runtime telemetry data were not imported.
- Limitations: Server side is Linux-only at this point (PipeWire, BlueZ, D-Bus). Android apps must be rebuilt to get Kaaka APKs. This code was written before this repository was created. History was rewritten on 2026-10-24 (about 22:00 IST) at the owner's request so the earlier project name does not appear; the rename is folded into this import.

## 2026-10-24T21:20:00+05:30 — Add hfptest Bluetooth hands-free feasibility tool

- Changed: Added `tools/hfptest` (Swift package, IOBluetooth) that lists paired devices with HFP Audio Gateway SDP status, connects to a phone as a Hands-Free unit, logs indicators/incoming calls, answers calls, requests SCO audio and records any Bluetooth input device to WAV.
- Why: Check whether a MacBook (Apple Silicon, macOS 27) can replace the Linux PipeWire hands-free setup used by the call server.
- Validation: Built with `swift build`; live tests against a Galaxy S23 on 2026-10-24: HFP connection PASS, incoming call detected PASS, answer from Mac worked, SCO audio FAIL (`kIOReturnUnsupported`, 0xE00002C7), no Bluetooth CoreAudio device appeared.
- Limitations: macOS does not provide HFP call audio (SCO) to apps; only call control works. `connect()` silently does nothing unless the baseband link is opened and SDP refreshed first (handled in the tool).

## Template setup — 10 October 2026

- Changed: Added the event README, rules, agent guide, change log, AI usage record, submission checklist, Git ignore rules, and pull request checklist.
- Why: Give participants a consistent starting point for event rules, basic coding patterns, documented changes, and regular commits.
- Validation: Checked local Markdown links, event detail consistency, required documents, and diff whitespace before publishing.
- Limitations: Documentation scaffolding only; no participant project, application, or working demo is included. GitHub publication and template status are verified separately after creation.
