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

1. A person in trouble calls the Kaaka number. The S23 rejects the call (call screening for unknown numbers, the phone-state fallback for saved contacts), so it costs them nothing.
2. The S23 replies by SMS: "Kaaka received your call. Help is being arranged. If in immediate danger, call 112." If a public link URL is set, the reply adds a "Share your location" link (`/l/<token>`) that works in any phone browser.
3. Each responder number set in Kaaka Call gets an SMS about the call ("Reply ACK <number> to confirm").
4. If the caller has Kaaka Sensors and the reply comes from their configured gateway number, their phone starts a beacon: "Kaaka Alert" SMS reports with GPS, motion, light and steps. Kaaka Sensors also has an SOS button and optional auto-SOS on fall.
5. The S23 logs every call and alert, texts responders, and forwards everything to the Mac dashboard (`/api/call-event`, `/api/telemetry`, `/api/heartbeat`).
6. The dashboard groups events into incidents per caller (calls, alerts, shared locations, latest location with a Maps link) and shows "S23 last seen" with battery and setup state.
7. A responder replies "ACK" by SMS to the S23: the caller is told a responder has seen the call, and the incident is marked acknowledged on the dashboard.

The Mac's Bluetooth hands-free mode (`--bt-mac`, `mac/hfp-bridge`) is a separate alternative. Do not run it together with S23 call screening: both would hang up the same call.

## Status (2026-10-25)

| Item | State |
|---|---|
| S23 call from a saved contact (phone-state fallback) | **Verified with a real call** (2026-10-24 23:16 IST): ended, SMS sent, logged, dashboard received it |
| Mac dashboard in `gateway_app` mode | **Verified** with real S23 events |
| No hardcoded numbers, addresses or device IDs | Done |
| S23 call from an unknown number (call screening) | Built; real call pending |
| S23 locked / app closed | Built; test pending |
| Responder SMS alerts and ACK by SMS | Built; gateway unit tests pass; device test pending |
| 112 reply text, location link in reply | Built; device test pending (link needs an https public URL) |
| Heartbeat and "S23 last seen" | Built; server tested; first real heartbeat pending (installed on the S23) |
| Battery-optimisation exemption | Built; device test pending |
| Incidents, location page, ACK endpoint, persistence, admin token | Built; full simulated incident passed end to end on the Mac |
| Kaaka Sensors SOS, fall detection, beacon duration, report format | Built; device test pending (needs a second Android phone) |
| Alert SMS receiving and forwarding on the S23 | Built; real alert pending |
| Mac Bluetooth hands-free (alternative mode) | Tested with real calls earlier |

Android does not pass calls from saved contacts to call-screening apps (Telecom only asks the built-in dialer). Kaaka Call handles those through its phone-state fallback (`IncomingCallReceiver`), which needs the "calls from contacts" permissions in the app.

## Next steps

1. **Device test pass** using [TESTING.md](TESTING.md).
2. **Public https URL** (only if location links are wanted): a tunnel or small server in front of the dashboard, with `KAAKA_ADMIN_TOKEN` set before exposing it.
3. **Second Android phone** with Kaaka Sensors for the SOS/fall/beacon tests.
4. **Tune fall detection** thresholds from real tests.
5. **Backup:** a second gateway phone and power backup.

## Out of scope on this hardware

- **AI voice conversation with the caller.** Android and macOS do not give apps access to cellular call audio (macOS `connectSCO` returns `kIOReturnUnsupported`). It needs call forwarding to a cloud telephony number or the original Linux PipeWire setup.
- **Bluetooth SMS access (MAP) on macOS.** Not available; the S23 sends and receives SMS itself.

## Repository workflow

- Work happens on short-lived branches and is merged into `main` through pull requests.
- Every meaningful change updates `CHANGELOG.md` (timestamp, change, reason, validation, limitations) and, where AI assistance was used, `AI_USAGE.md`.
- Commits are authored by the repository owner.
