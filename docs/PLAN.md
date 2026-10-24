# Kaaka plan

Kaaka is a community emergency help line that runs on a Mac and one Android phone (a Galaxy S23).
Anyone can call the Kaaka number; registered users can also share live location and sensor data.
It works alongside 112, not instead of it: it cannot dispatch police, fire or ambulance.

## System

| Part | Device | Role |
|---|---|---|
| Kaaka number | Galaxy S23 with **Kaaka Call** (`gateway/`) | Screens incoming calls, rejects them, sends the auto-reply SMS, receives "Kaaka Alert" reports, keeps an event log. Works with the app closed. |
| Control room | Mac running `server/server.py` (no Bluetooth) | Dashboard on `http://<mac-ip>:8080` showing calls, auto-reply results, alerts and live telemetry forwarded by the S23 over Wi-Fi. |
| Caller | Any phone | Calls the Kaaka number. No app needed. |
| Registered user | Android phone with **Kaaka Sensors** (`client/`) | When the Kaaka number replies, sends GPS + sensor reports to it every minute. |

## Flow

1. A person in trouble calls the Kaaka number. The call is rejected immediately, so it costs them nothing.
2. The S23 sends an SMS reply confirming the alert was received.
3. If the caller has Kaaka Sensors and the reply comes from their configured gateway number, their phone starts a beacon: "Kaaka Alert" SMS reports with GPS, motion, light and steps, every minute.
4. The S23 logs each call and alert and forwards them to the Mac dashboard (`POST /api/call-event`, `POST /api/telemetry`).
5. A responder sees the event on the dashboard and calls back or sends help.

The Mac's Bluetooth hands-free mode (`--bt-mac`, `mac/hfp-bridge`) is a separate alternative. Do not run it together with S23 call screening: both would hang up the same call.

## Status (2026-10-24)

| Item | State |
|---|---|
| Mac Bluetooth hands-free: call detection, caller ID, hang-up | Built and tested with real calls |
| Auto-reply SMS via the gateway app (Bluetooth mode) | Tested with a real call |
| No hardcoded numbers, addresses or device IDs | Done |
| Live sensor stream to the dashboard | Built; server path tested; on-device stream not yet confirmed |
| Client beacon only for the configured gateway number | Built; not yet tested on a device |
| S23 call screening, auto-reply, alert receiving, dashboard forwarding | Built and installed; real call test pending |
| Dashboard as server for the S23 (`gateway_app` mode) | Built and tested with sample events |

## Next steps

1. **Call test on the S23.** In Kaaka Call: enable call screening, allow SMS, set the dashboard server. Call from another phone, including a number not in the S23's contacts (Android may not screen calls from contacts).
2. **Telemetry test.** Install Kaaka Sensors on a second Android phone with the S23 as gateway number; start the beacon manually, then test the automatic trigger.
3. **Responder alerts.** Forward each call and alert by SMS to a list of responder numbers, so nothing depends on someone watching the dashboard.
4. **Location for callers without the app.** Add a "share my location" link to the reply SMS (needs the dashboard reachable from the internet).
5. **Reply wording.** Say what happens next and point to 112, e.g. "Kaaka received your call. Help is being arranged. If in immediate danger, call 112."
6. **Reliability.** Keep the S23 charged and exempt from battery optimisation; show a "last event / heartbeat from S23" on the dashboard; consider a backup phone.

## Out of scope on this hardware

- **AI voice conversation with the caller.** Android and macOS do not give apps access to cellular call audio (macOS `connectSCO` returns `kIOReturnUnsupported`). It needs call forwarding to a cloud telephony number or the original Linux PipeWire setup.
- **Bluetooth SMS access (MAP) on macOS.** Not available; the S23 sends and receives SMS itself.

## Repository workflow

- Work happens on short-lived branches and is merged into `main` through pull requests.
- Every meaningful change updates `CHANGELOG.md` (timestamp, change, reason, validation, limitations) and, where AI assistance was used, `AI_USAGE.md`.
- Commits are authored by the repository owner.
