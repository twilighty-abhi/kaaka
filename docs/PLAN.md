# Kaaka plan

Kaaka is a community emergency help line that runs on a Mac and one Android phone (a Galaxy S23).
Anyone can call the Kaaka number; registered users can also share live location and sensor data.
It works alongside 112, not instead of it: it cannot dispatch police, fire or ambulance.

## System

| Part | Device | Role |
|---|---|---|
| Kaaka number | Galaxy S23 with **Kaaka Call** (`gateway/`) | Screens incoming calls, rejects them, sends the auto-reply SMS, receives "Kaaka Alert" reports, keeps an event log. Works with the app closed. |
| Control room | Mac running `server/server.py` (no Bluetooth) | Dashboard on `http://<mac-ip>:8080/admin` (landing page at `/`) showing calls, auto-reply results, alerts and live telemetry forwarded by the S23 over Wi-Fi. |
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
| Location link: live sharing page, URL learned from the dashboard, `scripts/public-url.sh`, admin token enforced for public URLs | Built; server and unit tests pass; not yet run through a real tunnel |
| Heartbeat and "S23 last seen" | Built; server tested; first real heartbeat pending (installed on the S23) |
| Battery-optimisation exemption | Built; device test pending |
| Incidents, location page, ACK endpoint, persistence, admin token | Built; full simulated incident passed end to end on the Mac |
| Kaaka Sensors SOS, fall detection, beacon duration, report format | Built; device test pending (needs a second Android phone) |
| Alert SMS receiving and forwarding on the S23 | Built; real alert pending |
| Nearest-responder routing: responder registry, distance/ETA, dispatch of the 1–2 nearest, gateway dispatch SMS, dashboard panel and map lines | Built; server tests and gateway unit tests pass; dispatch SMS on a device pending |
| Mac Bluetooth hands-free (alternative mode) | Tested with real calls earlier |

Android does not pass calls from saved contacts to call-screening apps (Telecom only asks the built-in dialer). Kaaka Call handles those through its phone-state fallback (`IncomingCallReceiver`), which needs the "calls from contacts" permissions in the app.

## Next steps

1. **Device test pass** using [TESTING.md](TESTING.md).
2. **Public https URL** (only if location links are wanted): run `scripts/public-url.sh`, restart the server with `KAAKA_PUBLIC_URL` and `KAAKA_ADMIN_TOKEN`, set the token in Kaaka Call; test a link from a real phone browser.
3. **Second Android phone** with Kaaka Sensors for the SOS/fall/beacon tests.
4. **Tune fall detection** thresholds from real tests.
5. **Backup:** a second gateway phone and power backup.
6. **Responder accept/decline** by SMS, so a dispatched responder who cannot go is replaced by the next nearest.

## Round 3 features (branch `feat/round3`)

| # | Feature | Where | Why |
|---|---|---|---|
| 1 | **Help by SMS**: an SMS to the Kaaka number containing HELP, SOS, KAAKA or "സഹായം" is handled like a call (auto-reply, responders, dashboard incident with the message text) | S23 + server | People who cannot speak or have no call credit can still ask for help |
| 2 | **Escalation**: if an incident is not acknowledged within N minutes (default 5, 0 = off), responders get one "UNACKNOWLEDGED" reminder | S23 | Nobody answering must not go unnoticed |
| 3 | **Rate limiting**: at most N auto-replies/responder texts per number per hour (default 3); extra contacts are still logged and shown | S23 | Protects SMS credit and responders from spam or repeated pocket calls |
| 4 | **Responder SMS commands**: `STATUS` (open incidents summary), `RESOLVE <number> [note]` | S23 + server | Responders can manage incidents from any phone |
| 5 | **Malayalam / bilingual reply** setting (English, Malayalam, both) | S23 | The help line serves Malayalam speakers (Malayalam text to be reviewed by a native speaker) |
| 6 | **Incident lifecycle**: open → acknowledged → resolved (with who/note); resolve from the dashboard or by SMS; a new contact reopens it | server + dashboard | Responders need to know what is still open |
| 7 | **Mac notifications** for new incidents, acknowledgements, help SMS and a silent/stale S23 | server | The operator notices even when the dashboard tab is hidden |
| 8 | **Map** of incident locations on the dashboard (OpenStreetMap; needs internet) and **CSV export** of incidents | dashboard | Overview and record keeping |
| 9 | **Safety timer** in Kaaka Sensors: if the user does not check in before the timer ends, a 30-second countdown then SOS | client | Lone travel or walking home at night |

Server contract changes: `/api/call-event` accepts `state: "sms"` with an optional `message`; new `POST /api/resolve {number, by, note, timestamp}`; `/api/incidents` adds `status` and `resolved`.

## Out of scope on this hardware

- **AI voice conversation with the caller.** Android and macOS do not give apps access to cellular call audio (macOS `connectSCO` returns `kIOReturnUnsupported`). It needs call forwarding to a cloud telephony number or the original Linux PipeWire setup.
- **Bluetooth SMS access (MAP) on macOS.** Not available; the S23 sends and receives SMS itself.

## Repository workflow

- Work happens on short-lived branches and is merged into `main` through pull requests.
- Every meaningful change updates `CHANGELOG.md` (timestamp, change, reason, validation, limitations) and, where AI assistance was used, `AI_USAGE.md`.
- Commits are authored by the repository owner.
