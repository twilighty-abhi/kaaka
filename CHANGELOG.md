# Change log

Record each meaningful project change during the event, newest first. Update this file in the same commit as the change. Use a real timestamp with timezone, for example `YYYY-MM-DDTHH:MM:SS+05:30`.

## Event build log

## 2026-10-25T00:25:00+05:30 — Incidents, location sharing page, ACK and admin token on the server

- Changed: `server/incidents.py` keeps incidents grouped by caller (last 10 digits) with calls, alerts (Coords/Maps parsed), shared locations, acknowledgement and latest location, persisted in `server/events.jsonl` (ignored by Git) and reloaded on start. `server/server.py`: `/api/call-event` accepts an optional `token` (24 h); public `GET /l/<token>` serves `server/locate.html` and `POST /api/location` records a caller's browser GPS; `POST /api/ack` marks an incident acknowledged; `GET /api/incidents`; WebSocket broadcasts `LOCATION_SHARED` and `INCIDENT_ACK`. Optional `KAAKA_ADMIN_TOKEN` protects the dashboard, status, incidents, WebSocket and gateway POSTs (header `X-Kaaka-Token`, `?token=` or cookie; constant-time compare), leaving the location page public. `--public-url`/`KAAKA_PUBLIC_URL` for display. Dashboard: incidents panel with Maps links and "awaiting acknowledgement"; feed text inserted with `textContent`. README documents the full API.
- Why: Turn individual events into incidents a responder can act on, get location from callers without the app, close the loop with acknowledgements, and allow safe public exposure.
- Validation: `py_compile`; spare-port server: 17/17 HTTP checks (tokens, location ranges, 404/400 paths, alert coords, dedupe, ack), WebSocket messages received, incidents persisted across restart, admin token enforced (401 without, 200 with header/query/cookie; location page stays public); store unit checks (expiry, ack matching/reset, grouping, damaged lines).
- Limitations: Not checked in a real browser or over an https tunnel; with an admin token set the client app's live stream is refused (it sends no token).

## 2026-10-25T00:15:00+05:30 — Location links, responder ACK and dashboard token in the gateway app

- Changed: Gateway app (`gateway/`): new settings "public link URL" and "dashboard token" (warns when the URL is not https). Every call with a caller number gets a random 12-character token sent in `/api/call-event`; with a public URL set, the reply SMS adds "Share your location: <url>/l/<token>". With a dashboard token set, all dashboard POSTs send `X-Kaaka-Token`. A responder SMS starting with "ACK" (optionally "ACK <number>") acknowledges the latest or named incident: the caller is texted that a responder has seen the call, `/api/ack` is posted, the responder gets a confirmation; ACK messages are never treated as alerts. Responder notifications end with "Reply ACK <number> to confirm." Pure-Java helpers in `GatewayText.java` with unit tests. Rebuilt `gateway/Kaaka.apk`.
- Why: Callers without the app need a way to share location; responders need to confirm they have taken an incident, and the caller needs to know.
- Validation: `svelte-check` 0 errors/0 warnings; `./gradlew testDebugUnitTest assembleDebug` passed (GatewayTextTest 4/4: token format, ACK parsing, non-ACK ignored, link only with a URL).
- Limitations: Not installed or tested on the S23 yet. The location page needs an https public URL; reply plus link may be sent as a two-part SMS.

## 2026-10-25T00:05:00+05:30 — SOS button, fall detection and beacon duration in Kaaka Sensors

- Changed: Client app (`client/`): new SOS card (`SosCard.svelte`) that sends a report to the gateway number at once and starts the beacon; optional "Auto SOS on fall" (`emergencyService.svelte.ts`, off by default): impact above ~2.5 g followed by ~2 s of stillness starts a 15-second cancellable countdown, then SOS. Reports always carry `• Coords:`/`• Maps:` or `• Location: unavailable`, plus `• Trigger:` (sos/fall/gateway reply/manual); the first report waits at most 5 s for GPS. Beacon stops after a configurable duration (default 30 minutes) and shows trigger, count, last sent and time left. README updated, including foreground-only limits. Rebuilt `client/KaakaSensors.apk`.
- Why: A person in distress must be able to raise an alert without calling, and a fall should raise one even if they cannot.
- Validation: `npx svelte-check` 0 errors/0 warnings; web build, `cap sync`, `assembleDebug` succeeded; APK contains the new strings.
- Limitations: Not run on a device. Fall thresholds are untuned heuristics; detection and the beacon only run while the app is in the foreground.

## 2026-10-24T23:55:00+05:30 — Responder alerts, 112 reply text, heartbeat and battery exemption on the S23

- Changed: Gateway app (`gateway/`): new "responder numbers" setting; every call and every Kaaka alert is texted to each responder (never to the caller/sender), with counts in the local event log. Default reply is now "Kaaka received your call. Help is being arranged. If in immediate danger, call 112." (the old default is treated as unset). WorkManager heartbeat (`Heartbeat.java`, `HeartbeatWorker.java`) posts `/api/heartbeat` every 15 minutes and on settings save when a dashboard is set. New "battery optimisation" row requests the exemption; status reports `batteryExempt`. Shared `GatewayStore.sendSms`. Rebuilt `gateway/Kaaka.apk` (adds `androidx.work`).
- Why: Alerts must reach a person even when nobody watches the dashboard; callers must be told to use 112 in immediate danger; the phone must stay awake and report that it is alive.
- Validation: `svelte-check` 0 errors/0 warnings; web build, `cap sync`, `assembleDebug`; installed on the Galaxy S23: launched without crash, call-screening role and settings kept, heartbeat job registered.
- Limitations: Heartbeat delivery to the Mac, responder SMS, the battery prompt and the new reply on a real call are not yet tested on the device; Samsung may delay the 15-minute job without the battery exemption.

## 2026-10-24T23:40:00+05:30 — Gateway heartbeat and "last seen" on the dashboard

- Changed: `server/server.py` adds `POST /api/heartbeat` (`timestamp`, `battery`, `charging`, `screeningRole`, `smsGranted`, `contactCalls`; 400 on bad input), stores the last heartbeat, reports `last_heartbeat` and `gateway_stale` (no heartbeat for 20 minutes) in `/api/status`, broadcasts `GATEWAY_HEARTBEAT`, and warns in the console when a permission is missing or the battery is low. The dashboard shows "s23: last seen …" with battery and setup state, highlighted when stale or degraded. `docs/PLAN.md` records the verified contact-call test; README mentions the heartbeat.
- Why: An emergency line that silently stops working is worse than none; the operator must see when the S23 is offline or misconfigured.
- Validation: `py_compile`; server on spare ports: heartbeat 200 and broadcast received, bad JSON/types 400, stale logic (none / 19 min / 21 min), call-event and telemetry still 200.
- Limitations: Dashboard rendering not checked in a browser; real heartbeats from the S23 pending (gateway part in the next commit).

## 2026-10-24T23:17:00+05:30 — Handle calls from saved contacts on the S23 gateway

- Changed: New `IncomingCallReceiver` in the gateway app listens for the phone-state broadcast (READ_PHONE_STATE, READ_CALL_LOG for the number) and, for calls Android does not send to call screening, sends the auto-reply SMS, logs the event and reports it to the dashboard; with "reject calls" on and ANSWER_PHONE_CALLS granted it ends the ringing call (`TelecomManager.endCall`). Shared call handling moved to `CallHandler`; `GatewayStore.claimCall` prevents a call seen by both paths from being handled twice (60 s per number). New "calls from contacts" permission row in the UI; events from this path are labelled "(contact)".
- Why: Test calls from a number saved in the S23's contacts were never passed to Kaaka Call: Telecom's history showed `contact exists` and screening sent only to Samsung's own Phone app, so nothing was rejected, texted or reported.
- Validation: `svelte-check` 0 errors/0 warnings; `assembleDebug` succeeded; installed on the Galaxy S23; `dumpsys package` shows the PHONE_STATE receiver registered and the call-screening role still held.
- Real-call test (2026-10-24 23:16 IST): call from a saved contact to the Galaxy S23 was ended, the caller received the auto-reply SMS, the app logged it as `via phone_state`, `rejected`, `sms sent`, and the Mac dashboard received the call event.
- Limitations: `TelecomManager.endCall` is deprecated; it works on the S23 today but could stop working in a future Android release (the SMS and dashboard event would still happen).

## 2026-10-24T23:05:00+05:30 — Remove hackathon template files

- Changed: Deleted `RULES.md`, `AGENTS.md`, `SUBMISSION.md` and `.github/pull_request_template.md`; README footer now links the project records instead.
- Why: Requested by the repository owner; these were event template files not used by the project.
- Validation: `git grep` finds no remaining links to the deleted files outside historical log text.
- Limitations: None identified.

## 2026-10-24T21:49:00+05:30 — Poll phone SMS for telemetry every 30 s

- Changed: `server/server.py` ADB telemetry listener now reads the phone's SMS store every 30 s instead of every 1.5 s.
- Why: Owner's request; polling `content://sms` over USB every 1.5 s was more frequent than needed.
- Validation: Python compile check. Not yet verified against the running server, which must be restarted to pick this up.
- Limitations: SMS-delivered telemetry can take up to 30 s to reach the dashboard; the client app's direct WebSocket copy is unaffected. If the client app runs on the same phone the server reads, a report can appear twice (WebSocket, then the SMS copy).

## 2026-10-24T22:45:00+05:30 — Add project plan

- Changed: Added `docs/PLAN.md` (system roles for the Mac + S23 setup, emergency flow, current status, next steps, out-of-scope items, repository workflow) and linked it from the README.
- Why: Record the agreed plan in the repository.
- Validation: Checked status entries against this changelog; links resolve.
- Limitations: Status reflects 2026-10-24; real call and telemetry tests on the S23 are still pending.

## 2026-10-24T22:30:00+05:30 — Gateway app handles calls and alerts on the S23 by itself

- Changed: Kaaka Call (`gateway/`) now has a `CallScreeningService` (`KaakaCallScreeningService.java`) that reads the incoming caller number, rejects the call (setting, on by default; call log and notification kept) and sends the auto-reply SMS natively; hidden numbers get no SMS. `AlertSmsReceiver.java` logs incoming "Kaaka Alert"/"Live Sensors" SMS without being the default SMS app. Events (last 50) and settings live in native storage (`GatewayStore.java`) so everything works with the app closed; `GatewayPlugin.java` exposes them to the rewritten UI, which requests the call-screening role and SMS permissions and shows recent events. Optional dashboard forwarding posts calls to `/api/call-event` and alerts to `/api/telemetry`. Removed the WebSocket `CALL_DETECTED` auto-send path and the `ws://` setting. Rebuilt `gateway/Kaaka.apk`; updated `gateway/README.md`.
- Why: Make the S23 the self-contained "112 alternative" gateway, with the Mac only as an optional dashboard, and stop the app needing to stay open.
- Validation: `svelte-check` 0 errors/0 warnings; web build, `cap sync`, `assembleDebug` succeeded; installed on the Galaxy S23 and launched without crashes; `dumpsys package` shows the screening service and SMS receiver registered.
- Limitations: No real call or SMS tested yet; the call-screening role and RECEIVE_SMS still need the user's approval on the phone. Android may not ask screening apps about calls from saved contacts (to be checked on the S23). Rejection outcome (busy vs voicemail) depends on the carrier.

## 2026-10-24T22:25:00+05:30 — Server as an optional dashboard for the S23 gateway (Mac + S23 setup)

- Changed: `--bt-mac`/`KAAKA_BT_MAC` is optional in `server/server.py`; without it no Bluetooth/telephony listeners start and `/api/status` reports `gateway_mode: gateway_app`. New `POST /api/call-event` (`number`, `state` rejected|allowed, `sms` sent|failed|skipped, `timestamp`) records calls handled by the gateway app, updates the last caller, and broadcasts a `CALL_EVENT` WebSocket message; it never answers, hangs up or sends SMS. Dashboard shows these events with the auto-reply result and labels Bluetooth as off in this mode. README has a "Unified setup: Mac + S23" section; the Mac Bluetooth mode is documented as an alternative that must not be combined with S23 call screening.
- Why: The S23 now handles calls itself; the Mac only needs to show what happened.
- Validation: `py_compile`; server run without `--bt-mac` on spare ports: no hfp-bridge started; call-event 200 and `CALL_EVENT` received over WebSocket; bad JSON and invalid state return 400; hidden number accepted with "no auto-reply"; `/api/telemetry` still 200; `/api/status` mode correct.
- Limitations: Dashboard rendering and real posts from the S23 not yet tested; Bluetooth mode not re-run after this change.

## 2026-10-24T22:20:00+05:30 — Start the client beacon only for the configured gateway number

- Changed: The Kaaka Sensors app starts its emergency beacon only when an SMS arrives from the configured gateway phone number (digits compared on the last 10), enforced in both `SmsReceiver.java` and `defaultSmsService.svelte.ts`; reports always go to the configured gateway number, never to the SMS sender. Keyword triggers ("call", "alert", "emergency", "kaaka") removed. Settings wording marks the computer dashboard and live stream as optional. `client/README.md` rewritten for the unified Mac + S23 flow. Rebuilt `client/KaakaSensors.apk`.
- Why: Any SMS containing those words, from any number, made the app send its sensor data and GPS location to that sender every minute.
- Validation: `npx svelte-check`: 0 errors, 0 warnings; web build, `cap sync` and `./gradlew assembleDebug` succeeded; unpacked APK contains the new rule and no keyword trigger.
- Limitations: Not tested on a device; the S23 still has the previous client build installed.

## 2026-10-24T22:07:00+05:30 — Allow the client app to reach the Mac server over plain HTTP/WebSocket

- Changed: `client/capacitor.config.ts` serves the app over `http` with cleartext allowed, and `client/android/app/src/main/AndroidManifest.xml` sets `usesCleartextTraffic="true"`.
- Why: The client app talks to the Mac server at `ws://<mac-ip>:8765` and `http://<mac-ip>:8080` on the local network; an https page blocks these as mixed content and Android blocks cleartext by default.
- Validation: Included in the client APK built and installed on the Galaxy S23 in the previous commit. These edits appeared in the working tree at 21:57 IST after the Android rebuild task and were reviewed before committing.
- Limitations: Traffic between the phone and the Mac is unencrypted on the local network.

## 2026-10-24T22:05:00+05:30 — Stream live sensor readings to the dashboard

- Changed: `server/server.py` accepts the client app's sensor JSON on `POST /api/telemetry` (port 8080), formats it as a "Kaaka Live" report and broadcasts it to the dashboard without a console banner or disk write per reading; added a CORS preflight (`OPTIONS`) handler. Client app: backend sync is on by default and runs whenever Settings → Telemetry backend is set (the UI had no switch for it, so it never ran); placeholder now `http://<mac-ip>:8080`. Rebuilt `client/KaakaSensors.apk`.
- Why: The dashboard's live telemetry never updated: the client only sent readings to an unset backend URL (pointing at the separate Node service on :3001), sync could not be switched on, and the server had no preflight handler.
- Validation: Preflight returns 204; a sample sensor POST returned success and a WebSocket client received the formatted "Live sensor stream" report; client rebuilt with Gradle and installed on the Galaxy S23 (`adb install -r` Success).
- Limitations: Live stream readings carry no GPS coordinates (the full alert report still does). On-device streaming not yet confirmed at the time of this entry.

## 2026-10-24T21:47:00+05:30 — Count only phones as gateway connections

- Changed: `server/server.py` treats WebSocket clients from this machine (loopback or the server's own IP, e.g. the dashboard in a local browser) as non-phones in the call log, `/api/status` and pending-call replay, and warns on macOS when a call arrives with no gateway app connected.
- Why: During testing the log said "Gateway App Link: Connected" while only the Mac's own dashboard was connected, hiding why no SMS was sent.
- Validation: End-to-end test on 2026-10-24 21:44 IST before this change: gateway app on the Galaxy S23 connected over Wi-Fi, incoming call detected with caller number, 1-ring hangup, app confirmed "Auto-sent SMS" and the caller received it. After the change: server restarted, HFP reconnected, `/api/status` no longer lists the local dashboard as a gateway.
- Limitations: The gateway app only keeps its server connection while it is in the foreground; with the screen off or the app in the background no auto-reply SMS is sent. One test call arrived without a caller number, so no SMS was sent for it (by design).

## 2026-10-24T21:57:00+05:30 — Add rebuilt Kaaka debug APKs

- Changed: Added `gateway/Kaaka.apk` (`com.kaaka.callapp`, label "Kaaka Call") and `client/KaakaSensors.apk` (`com.kaaka.sensors`, label "KaakaSensors"), debug builds of the previous commit.
- Why: Installable apps for the gateway phone and the client phone.
- Validation: `aapt dump badging` confirms app IDs and labels; unpacked APKs contain none of the old numbers, IPs or names; `gateway/Kaaka.apk` installed on the Galaxy S23 with `adb install -r` (Success).
- Limitations: Debug-signed builds. The client app requests the default-SMS role and is meant for a separate phone, not the gateway phone.

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
