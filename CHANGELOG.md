# Change log

Record each meaningful project change during the event, newest first. Update this file in the same commit as the change. Use a real timestamp with timezone, for example `YYYY-MM-DDTHH:MM:SS+05:30`.

## Event build log

## 2026-10-25T03:32:47+05:30 — Rebuild both apps with SAFE, location links and nearest-responder dispatch

- Changed: `gateway/Kaaka.apk` and `client/KaakaSensors.apk` rebuilt from the integrated branch (feat/im-safe + feat/location-link + feat/nearest-responder on top of the beacon-interval/trail work). Merge conflicts were all additive and resolved by keeping both sides.
- Why: One APK rebuild for the three feature PRs, so the binaries do not conflict between them.
- Validation: Gateway `svelte-check` 0 errors, `GatewayTextTest` 18/18, `assembleDebug`; client `svelte-check` 0 errors, `assembleDebug`; server `py_compile`; combined spare-port smoke test: responder registered → call with token → alert dispatches the nearest responder (3.15 km, ~8 min) → location share 200 then 429 within 10 s → caller SAFE resolves with `closed_by_caller: true`.
- Limitations: Not yet installed or tested on the phones.

## 2026-10-25T03:29:08+05:30 — Nearest-responder routing: validation summary

- Changed: `AI_USAGE.md` row for this feature.
- Why: Record the assistance and the checks run.
- Validation: With `KAAKA_ADMIN_TOKEN` set: `GET/POST/PATCH/DELETE /api/responders` and `POST /api/telemetry` return 401 without the token and 200 with header or `?token=`. All server, gateway and dashboard checks listed in the entries above.
- Limitations: The dispatch SMS has not been sent from a real phone yet; the rebuilt gateway APK is not committed in this change.

## 2026-10-25T03:28:25+05:30 — Document nearest-responder routing

- Changed: README (Mac + S23 section): how responders are registered, how distance/ETA are computed (straight line, 25 km/h assumption), the dispatch rule and the dispatch SMS; API table gains the four `/api/responders` endpoints and the `dispatch` field in the `/api/telemetry` response. `docs/PLAN.md`: status row for the feature and a next step for responder accept/decline.
- Why: Keep the setup and API documentation complete.
- Validation: Re-read the rendered Markdown table rows for alignment.
- Limitations: None identified.

## 2026-10-25T03:27:35+05:30 — Dashboard: responders panel, nearest-responder lines and dispatch status

- Changed: `server/dashboard.html` gets a Responders panel (list with available/unavailable toggle and remove; add form with name, number and "lat, lon" or a click on the map via "pick on map"). The map shows responders as blue dots (dimmed when unavailable) and, for each open incident with a location, a dashed line to its nearest responder labelled "1.2 km · ~3 min". Incident cards show "Nearest: <name> (km, ETA) · dispatched: <names>" (or "not dispatched yet" / "no available responder registered"). `RESPONDER_DISPATCHED` appears in the activity feed with a beep. Responder names and numbers are inserted with `textContent`.
- Why: Let the operator see who is closest and who was asked to go, and keep the responder list up to date without editing files.
- Validation: Script parses; spare-port server seeded with three responders and two located incidents, rendered with headless Chrome: panel, dots, dashed lines with ETA labels and the "nearest … dispatched" card lines all visible.
- Limitations: Lines use straight-line distance; the map fits incidents and their nearest responders, so far-away responders may be off-screen until zoomed out.

## 2026-10-25T03:25:32+05:30 — Gateway: text the dispatched responders

- Changed: After forwarding a Kaaka Alert to the dashboard, `AlertSmsReceiver` reads the `dispatch` list in the reply and texts each responder with `GatewayText.dispatchMessage` (distance, ETA, Maps link, "Reply ACK <caller>"), then logs a local `dispatch` event (names texted, failures). The event list shows "dispatch for <caller>: <names>". Later reports of an already-dispatched incident get an empty list from the dashboard, so nobody is texted twice.
- Why: Close the loop from "nearest responder known" to "nearest responder told".
- Validation: `svelte-check` 0 errors; web build, `cap sync`, `./gradlew testDebugUnitTest assembleDebug` (GatewayTextTest 12/12).
- Limitations: Not run on a device; the dashboard must be reachable at alert time, otherwise no dispatch SMS goes out (the alert itself still reaches responders through the normal notification).

## 2026-10-25T03:25:32+05:30 — Gateway: read the dashboard's reply to a post

- Changed: `GatewayStore.postToDashboardForResponse` posts JSON and returns the response body (null without a dashboard, on error or when unreachable; body capped at 64 KB); `postToDashboard` now wraps it, so existing callers are unchanged.
- Why: The dashboard answers an alert with the responders it dispatched; the app needs that answer.
- Validation: `./gradlew assembleDebug` builds; existing behaviour of the void variant unchanged by construction.
- Limitations: None identified.

## 2026-10-25T03:24:25+05:30 — Gateway: dispatch SMS wording

- Changed: `GatewayText.dispatchMessage` formats the text sent to a dispatched responder ("Kaaka dispatch: you are the nearest responder (1.2 km, ~3 min) to <caller>. Location: <maps> Reply ACK <caller> to confirm."); "Kaaka dispatch:" is added to the app's own-message list so such a text arriving at another gateway is never read as a help request.
- Why: Responders picked by the dashboard must be told clearly and consistently.
- Validation: `./gradlew testDebugUnitTest`: GatewayTextTest 12/12 (new test covers the format, empty caller/maps fallbacks and the own-message exclusion).
- Limitations: Wording is English only.

## 2026-10-25T03:22:52+05:30 — Dispatch the nearest responders when an incident gets a location

- Changed: The first time an open incident has a location (an alert with coordinates via `/api/telemetry`, or a share via `/api/location`), the server picks the 1–2 nearest available responders, records a `dispatch` event in `events.jsonl` (`dispatched` on the incident), broadcasts `RESPONDER_DISPATCHED`, notifies, and returns `dispatch: [{name, number, distance_km, eta_min, maps_url}]` in the `/api/telemetry` response so the gateway app can text them. Later reports of the same open incident do not dispatch again; resolving clears the dispatch so a reopened incident gets a fresh one.
- Why: Turn alerts into dispatch: the people closest to the caller are asked to go.
- Validation: Spare-port run with three responders: first alert dispatched Near (0.11 km, ~1 min) and Mid (2.24 km, ~5 min), `RESPONDER_DISPATCHED` received over WebSocket, second alert returned no dispatch, resolve cleared it, third alert re-dispatched; a location share for another caller dispatched Mid then Near; both incidents and all responders persisted across a restart.
- Limitations: Dispatch is advisory (SMS), there is no accept/decline step yet.

## 2026-10-25T03:21:22+05:30 — Distance and ETA to the nearest responders

- Changed: `server/responders.py` adds `haversine_km`, `eta_minutes` (assumes 25 km/h average city travel; a planning estimate, not a promise) and `ResponderRegistry.nearest`. `GET /api/incidents` adds `nearest_responders` per incident: the 3 nearest available responders to its latest location with `distance_km` and `eta_min`.
- Why: Show who can reach a caller soonest.
- Validation: Pure-function checks: Jain University Kochi → Bharata Mata College straight-line 4.14 km; zero distance for the same point; ETA 1 min minimum, 25 km → 60 min; ordering Near/Mid/Far with an unavailable responder excluded; registry reloads from disk. `py_compile`.
- Limitations: Straight-line distance, not road distance.

## 2026-10-25T03:20:45+05:30 — Responder registry on the server

- Changed: New `server/responders.py` (`ResponderRegistry`, persisted in `server/responders.json`, ignored by Git) and endpoints `GET/POST /api/responders`, `PATCH/DELETE /api/responders/<id>` with fields name, number, lat, lon, available; values are validated (name ≤ 80 chars, number ≥ 6 digits, lat/lon ranges, available boolean) and the same admin-token rule applies as to other APIs. CORS preflight now lists PATCH and DELETE.
- Why: Nearest-responder routing needs to know who the responders are and where they usually are.
- Validation: `py_compile`; spare-port run: add 200, invalid number 400, patch available 200, patch bad lat 400, delete 200, delete again 404, list empty.
- Limitations: Positions are static home locations, not live responder GPS.
## 2026-10-25T03:24:22+05:30 — Document location links for callers without the app

- Changed: README: new "Location links for callers without the app" section (flow, https requirement, `scripts/public-url.sh`, admin-token requirement, automatic URL from the heartbeat); settings and API tables updated (heartbeat reply, 429 on location updates). `docs/PLAN.md` status and next steps updated.
- Why: Setup has several moving parts and a safety rule; they need to be written down.
- Validation: Links and anchors checked by reading; no code change.
- Limitations: None identified.

## 2026-10-25T03:23:44+05:30 — Helper to give the dashboard a public https URL

- Changed: `scripts/public-url.sh` checks for cloudflared (prints the brew install command if missing) and for a running dashboard, opens a Cloudflare quick tunnel to the dashboard port, extracts the `https://*.trycloudflare.com` URL and prints the exact next steps (restart with `KAAKA_PUBLIC_URL` and `KAAKA_ADMIN_TOKEN`, set the token in Kaaka Call; the phone learns the URL from the heartbeat).
- Why: The location link needs an https address reachable from callers' phones; this is the quickest way to get one for a demo or pilot.
- Validation: `bash -n`; missing-cloudflared and no-dashboard paths exit with clear messages. No tunnel was opened.
- Limitations: Quick-tunnel URLs change on every run; for a permanent address use a named tunnel or a hosted server.

## 2026-10-25T03:23:02+05:30 — Show the automatic public URL in the gateway settings

- Changed: `getSettings` returns `autoPublicUrl`; under the public link field the UI shows "auto: <url> (from the dashboard)" when the field is empty and a URL was reported (flagged when not https), or a hint to leave the field empty.
- Why: The operator should see which URL callers will get without digging into logs.
- Validation: `npx svelte-check` 0 errors; `npm run build`; `npx cap sync android`; `assembleDebug`.
- Limitations: Not checked on a device.

## 2026-10-25T03:23:02+05:30 — Gateway learns the public URL from the dashboard heartbeat

- Changed: `GatewayStore.postToDashboardForReply` returns the JSON reply (the existing `postToDashboard` wraps it). `Heartbeat` stores the reply's `public_url` as the automatic URL (`autoPublicUrl`), logging changes. `CallHandler` builds the reply's location link from `effectivePublicUrl` (manual setting, else automatic).
- Why: No one should have to copy a tunnel URL into the phone: the dashboard already knows it.
- Validation: `./gradlew assembleDebug` builds; unit tests 15/15. Not yet exercised against a running dashboard from the app.
- Limitations: The automatic URL only updates when a heartbeat gets through (every 15 min or on settings save).

## 2026-10-25T03:23:02+05:30 — Decide the location-link URL in pure code, with tests

- Changed: `GatewayText.effectivePublicUrl(manual, auto)` (manual setting wins, else the dashboard-reported URL, else none; trailing slashes dropped) and `isInsecurePublicUrl`. Four new unit tests in `GatewayTextTest`.
- Why: The gateway will soon learn the public URL from the dashboard; the choice between manual and automatic URL must be simple and tested.
- Validation: `./gradlew testDebugUnitTest`: GatewayTextTest 15/15 (manual wins, auto when manual empty, none when both empty, non-https auto used but flagged).
- Limitations: None identified.

## 2026-10-25T03:20:28+05:30 — Location page keeps sharing while open

- Changed: `server/locate.html`: after the first successful share it watches the position and sends an update at most every 15 s, shows "Sharing live location · N updates" and a "Stop sharing" button; 429 replies (sent too soon) are skipped silently. The https warning stays. Plain HTML/JS, no external scripts.
- Why: A moving caller's position should keep flowing without them pressing the button again.
- Validation: Script syntax parsed with Node; page still served (200) in the earlier spare-port test. Not opened in a real phone browser.
- Limitations: Browser geolocation needs an https origin; the page says so when it is not.

## 2026-10-25T03:19:48+05:30 — Heartbeat returns the public URL; location updates rate-limited

- Changed: `POST /api/heartbeat` now replies `{"success": true, "public_url": "..."}` (empty when no public URL is configured). `POST /api/location` accepts at most one update per link token every 10 s and answers 429 otherwise.
- Why: Lets the gateway app learn the public URL automatically, and keeps live location sharing from flooding the server.
- Validation: `py_compile`; spare-port run with `KAAKA_ADMIN_TOKEN` and a public URL: heartbeat reply carries the URL, call-event with token 200, `/l/<token>` 200, first location 200 and a second within 10 s 429, incident lists one location.
- Limitations: The rate limit is in memory and resets when the server restarts.

## 2026-10-25T03:13:45+05:30 — Require an admin token for a public dashboard URL

- Changed: `server/server.py` exits with a clear error when a public URL (`--public-url` / `KAAKA_PUBLIC_URL`) is set without `KAAKA_ADMIN_TOKEN`, unless `--allow-unprotected-public` is given.
- Why: A public URL exposes the dashboard and gateway endpoints to the internet; without the token anyone could read callers' numbers and locations.
- Validation: `py_compile`; starting with `KAAKA_PUBLIC_URL` and no token prints the error and exits.
- Limitations: None identified.
## 2026-10-25T03:24:45+05:30 — Document "I'm safe" / SAFE

- Changed: README (Mac + S23 section), `gateway/README.md`, `client/README.md` and `docs/TESTING.md` describe the SAFE text, the "I'm safe" button, the dashboard badge and two device checks.
- Why: Keep docs and the test checklist in step with the feature.
- Validation: Re-read against the implemented behaviour.
- Limitations: None identified.

## 2026-10-25T03:24:11+05:30 — Dashboard shows incidents closed by the caller

- Changed: `/api/incidents` adds `closed_by_caller` (true when the incident was resolved with `by: "caller"`). The dashboard shows a green "safe" badge and "closed by caller · reported safe at …"; the feed and the macOS notification say "Caller reported safe". A later call, help SMS or alert reopens the incident as before.
- Why: Responders should see at a glance that the caller ended the alert themselves.
- Validation: `py_compile`; spare-port run: call → open; resolve by caller → resolved with `closed_by_caller: true`; new call → open again; responder resolve → resolved with `closed_by_caller: false`; console shows "Caller … reported safe — incident closed".
- Limitations: Dashboard rendering not checked in a browser.

## 2026-10-25T03:24:11+05:30 — "I'm safe" button in Kaaka Sensors

- Changed: While the beacon runs or a countdown is active, the SOS card shows "I'm safe — close my alert". It stops the beacon, cancels any countdown and the safety timer, texts SAFE to the gateway number and shows the real send result (`emergencyService.reportSafe`).
- Why: One tap for the caller to end the alert once help has arrived or the alarm was false.
- Validation: `npx svelte-check` 0 errors / 0 warnings; web build, `cap sync`, `./gradlew assembleDebug` succeeded.
- Limitations: Not run on a device; APK not committed.

## 2026-10-25T03:23:02+05:30 — Show "safe" events in the gateway app

- Changed: Kaaka Call's recent-events list shows `safe <number> · incident closed · caller sms <result>` plus the responder count.
- Why: The gateway operator should see when a caller closed their own incident.
- Validation: `svelte-check` (gateway) 0 errors / 0 warnings.
- Limitations: UI only.

## 2026-10-25T03:22:13+05:30 — SAFE by SMS closes the caller's incident on the S23

- Changed: `AlertSmsReceiver` handles a SAFE text from a number with an open incident (checked before help keywords, after responder commands): replies "Kaaka: glad you are safe. Your alert is closed. If you need help again, call or text this number.", texts each responder "Kaaka: <caller> reported safe at HH:mm. Incident closed.", logs a `safe` event and posts `/api/resolve {number, by: "caller", note: "Caller reported safe"}`. A SAFE from a number without an open incident is ignored. Kaaka's own safe notices are excluded from help/safe matching so two gateways never answer each other.
- Why: Let the person who asked for help close the loop themselves.
- Validation: `./gradlew testDebugUnitTest assembleDebug`: GatewayTextTest 13/13 (own-message exclusions added); debug APK builds.
- Limitations: Not exercised with a real SMS; APK not committed.

## 2026-10-25T03:21:04+05:30 — Recognise "SAFE" texts from callers (gateway rules)

- Changed: `GatewayText.isSafeReport` matches SAFE, I'm safe, im safe, I am safe (any case, trailing punctuation allowed) and the Malayalam word സുരക്ഷിതം; Kaaka's own messages never match. `hasOpenIncident` says whether a number has a call, help SMS or alert in the last 24 h with no later resolve or safe (an ACK alone keeps it open); `handledSince` treats a logged "safe" like a resolve so the escalation reminder stays quiet. `GatewayStore.eventList` now reads the caller of alert events from their `sender` field.
- Why: First step of "I'm safe" closing an incident: pure rules, unit-tested before any SMS handling.
- Validation: `./gradlew testDebugUnitTest`: GatewayTextTest 13/13 (2 new tests: safe-text matching incl. negatives, open/closed/reopen logic).
- Limitations: Rules only; no SMS handling yet.

## 2026-10-25T02:13:16+05:30 — Beacon update interval and location trail on the dashboard

- Changed: Kaaka Sensors gets an "Update every 15 / 30 / 60 s" beacon setting (saved; default 60 s) on the SOS card. The dashboard map draws each incident's reported positions as a trail (oldest to newest) and fits the view to it. Rebuilt `client/KaakaSensors.apk`.
- Why: Show a moving caller (e.g. in a vehicle): more frequent reports and a visible path.
- Validation: `svelte-check` 0 errors; `assembleDebug`.
- Limitations: The interval only applies while the app's beacon runs (foreground).

## 2026-10-25T01:58:19+05:30 — Dashboard: no beep for the live sensor stream

- Changed: `server/dashboard.html` beeps only for alerts, calls and other events, not for "Live sensor stream" telemetry.
- Why: With a phone streaming sensor readings (about once a second), an open dashboard tab beeped continuously.
- Validation: Reviewed the handler; stream messages carry source "Live sensor stream".
- Limitations: Reload open dashboard tabs to pick up the change.

## 2026-10-25T01:52:02+05:30 — Scripted demo on two emulators; remove leftover sample coordinates

- Changed: New `scripts/demo-emulated.sh` resets two configured emulators and the dashboard, runs the SMS relay and a GPS feed, and performs the scenario (incoming call, reply-triggered location alert, SOS, help SMS, caller stops beacon, dashboard resolve) while `scripts/record-demo.sh` records a captioned side-by-side video. `record-demo.sh` gains an optional caption strip (`CAPTIONS`) and label tag (`DEMO_TAG`). Removed the hardcoded sample coordinates 9.064458, 76.557012 from the dashboard's GPS tile, Maps link and simulated alert and from the server's simulated alerts ("Location: unavailable" instead).
- Why: A presentable demo of the full flow; the coordinates were leftover real-looking data.
- Validation: Recorded `demo/kaaka-demo-20261025-014600.mp4` (2164×1470, 165 s): one incident with 1 call, 1 help SMS, 3 location alerts (9.931200, 76.267300), resolved with note; gateway heartbeat shown.
- Limitations: The phones in the video are emulators and the phone network (call, SMS delivery) and GPS are simulated; headless emulator rendering can show a brief partial frame.

## 2026-10-25T01:37:01+05:30 — Send the first location report natively when the Kaaka number replies

- Changed: Kaaka Sensors' SMS receiver now sends the first "Kaaka Alert" itself (`NativeAlert.java`): a recent last-known fix or a fresh fix (up to 8 s, via `goAsync`), else "Location: unavailable", in the same report format. Added `READ_PHONE_STATE` (newer Android checks the carrier group ID when apps send SMS: sends failed with `getGroupIdLevel1`) and `ACCESS_BACKGROUND_LOCATION` with a "Location all the time" row in the setup card. Trigger events to the web layer are retained until it subscribes. New `scripts/emulator-network.py` relays SMS between two emulators for demos/tests. Rebuilt `client/KaakaSensors.apk`.
- Why: The reply-triggered beacon never reported: Android 14+ blocks the receiver from opening the app ("Background activity launch blocked"), the web beacon therefore never ran, SMS sending lacked READ_PHONE_STATE, and location was "while using the app" only, so background location requests were rejected.
- Validation: Two Android 17 emulators (gateway Kaaka Call, caller Kaaka Sensors) with the Mac dashboard: incoming call → rejected → reply → native alert "with location" → gateway → dashboard incident with latest location 9.931200, 76.267300 and Maps link.
- Limitations: On real phones the user must grant "Allow all the time" location and READ_PHONE_STATE; not yet re-tested on the Xiaomi.

## 2026-10-25T01:22:15+05:30 — Demo video recorder

- Changed: New `scripts/record-demo.sh <gateway-serial> <caller-serial> [seconds] [dashboard-url]` records both phones (`adb screenrecord`) and the dashboard (headless Chrome screenshots every 2 s) at the same time, normalizes the clips (a clip with no frames becomes a still), labels them (labels rendered with Chrome because this ffmpeg build has no `drawtext`) and stitches them side by side into `demo/kaaka-demo-<timestamp>.mp4`. Tries to keep screens awake while recording (MIUI blocks this over adb). `demo/` is ignored by Git.
- Why: Record a demo of the whole flow across both phones and the Mac.
- Validation: 15 s test run with the S23 and the Xiaomi: 2190×1360, 15.0 s, three labelled panels (checked a frame).
- Limitations: Phone recording is limited to 180 s per run; the dashboard panel updates every 2 s.

## 2026-10-25T01:13:30+05:30 — Report the real SMS send result in Kaaka Sensors

- Changed: `DirectSmsPlugin` sends through the phone's default SMS SIM (`createForSubscriptionId`) and resolves only after the sent-PendingIntent results for all parts arrive; failures are rejected with a readable reason (no service, radio off, network rejected, limit), and a 30 s timeout reports an unconfirmed send. Rebuilt `client/KaakaSensors.apk`.
- Why: Device test: the SOS card showed "SOS sent … sent #2" while the Xiaomi's sent box and the S23's inbox had no message — the plugin resolved immediately with no sent callback, so silent failures looked like success.
- Validation: `assembleDebug`; installed on the Xiaomi. SOS could not be pressed over adb (MIUI blocks input injection), so the send result is to be checked by hand.
- Limitations: Delivery reports (receipt by the S23) are not tracked, only the send result.

## 2026-10-25T01:09:31+05:30 — Setup checklist in Kaaka Sensors (all permissions in one place)

- Changed: New `KaakaSetupPlugin` (status of SMS send/receive, location, notifications, physical activity, battery exemption; `requestAll`; battery-exemption request; opens the MIUI permission editor or the app settings page) and a "Finish setup" card at the top of the main screen with "Allow all", "Exempt" and "Open phone settings". Missing permissions are requested once per app start, never in a loop. Added `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`. The separate receive-SMS row in Settings is replaced by this card. Rebuilt `client/KaakaSensors.apk`.
- Why: Device test on the Xiaomi: RECEIVE_SMS, POST_NOTIFICATIONS (never requested at runtime on Android 13+) and ACTIVITY_RECOGNITION were missing and MIUI blocked lock-screen display and background starts, so the Kaaka reply could not start the beacon and no alarm could show. MIUI also blocks `pm grant` over adb, so the app must ask itself.
- Validation: `svelte-check` 0 errors; `assembleDebug`; installed on the Xiaomi; one permission request on start, no repeat.
- Limitations: The user must accept the prompts and enable MIUI's Autostart / lock screen / background pop-ups on the device.

## 2026-10-25T01:05:08+05:30 — Let Kaaka Sensors start the beacon from the Kaaka reply without being the default SMS app

- Changed: `DefaultSmsPlugin` declares the RECEIVE_SMS permission and adds `checkReceiveSms` / `requestReceiveSms`; the Settings card shows "Start beacon when the Kaaka number replies" with an Allow button and MIUI guidance (Autostart, show on lock screen, background pop-ups). `SmsReceiver` no longer posts its own notification for ordinary SMS when it is not the default SMS app (the phone's SMS app already does). Rebuilt `client/KaakaSensors.apk`.
- Why: Device test: the S23 rejected the Xiaomi's calls and its reply reached the Xiaomi, but Kaaka Sensors never reacted — RECEIVE_SMS was not granted (only SEND_SMS), because the app only obtained SMS access as the default SMS app. MIUI also denied "show when locked".
- Validation: `svelte-check` 0 errors; `assembleDebug`; installed on the Xiaomi; no role-request loop.
- Limitations: Automatic trigger to be re-tested after granting the permission on the device.

## 2026-10-25T00:51:15+05:30 — Do not ignore a second call from the same number

- Changed: `GatewayStore.CALL_DEDUPE_MS` 60 s → 10 s. Rebuilt `gateway/Kaaka.apk`.
- Why: Device test: a call at 00:30:40 was rejected, but a second call from the same number 30 s later (the "S23 locked" test) rang until missed with no reply, because the dedupe meant for the two detection paths seeing one call ignored any call from that number for a minute. Both paths fire within about a second.
- Also found: the dashboard received nothing since 00:16 because the S23 had dropped off Wi-Fi and was on mobile data (logs: "Dashboard … unreachable … from 192.0.0.2"); fixed by reconnecting the S23 to the same Wi-Fi as the Mac (no code change).
- Validation: `./gradlew testDebugUnitTest assembleDebug` (GatewayTextTest 11/11); installed on the S23, call-screening role kept; S23 → Mac:8080 reachable.
- Limitations: Second-call behaviour to be re-tested by hand.

## 2026-10-25T00:46:25+05:30 — Fix Kaaka Sensors default-SMS request loop (root cause of the frozen UI)

- Changed: `client/.../MainActivity.java` no longer requests the default-SMS role in `onResume`; the role is requested only from the receiver screen's button (`DefaultSmsPlugin.requestDefaultSms`). Removed the unused helper and imports. Rebuilt `client/KaakaSensors.apk`.
- Why: After the user declined the role permanently, Android denied each request instantly, the activity resumed and requested again: logcat showed 170 `REQUEST_ROLE` starts in 8 s. The repeated pause/resume and status-bar inset changes swallowed touches and kept the WebView redrawing.
- Validation: On the Xiaomi (Android 13) after reinstall: 0 role-request starts in 8 s, 13 frames rendered in 8 s with 0 janky (was ~36 frames/s, 35–50% janky), app CPU ~16%.
- Limitations: Users who want the automatic beacon trigger must open the receiver screen and tap the default-SMS button.

## 2026-10-25T00:43:59+05:30 — Reduce Kaaka Sensors rendering load

- Changed: Removed `backdrop-blur` from all client cards, sticky header and fixed footer, the always-pulsing blurred glow, and the per-update bar transitions; location state is now updated with the other on-screen values (at most every 200 ms) instead of on every sample. Rebuilt `client/KaakaSensors.apk`.
- Why: Scrolling stuttered on the Xiaomi: backdrop blur is redrawn on every scroll frame and content change in Android WebView, and reactive location updates re-rendered components ~16 times per second.
- Validation: `svelte-check` 0 errors; on the Xiaomi (idle main screen, 5 s windows): app CPU 53% → 34–38%, WebView renderer 18% → 7%, janky frames 49% → 32–39%.
- Limitations: The WebView still renders ~36 frames/s while idle; feel to be confirmed by hand.

## 2026-10-25T00:39:05+05:30 — Fix Kaaka Sensors freezing on the second phone

- Changed: `client/capacitor.config.ts` sets `loggingBehavior: 'none'`; `sensorManager.svelte.ts` passes every native sample to fall detection but updates the on-screen state at most every 200 ms. Rebuilt `client/KaakaSensors.apk`.
- Why: On a Xiaomi (Android 13) the app stopped responding to touches: Capacitor's debug bridge logged every sensor event (~16/s, full JSON) on the UI thread and every card and sparkline re-rendered per sample.
- Validation: `svelte-check` 0 errors/0 warnings; installed on the Xiaomi; Capacitor console lines in 6 s dropped from ~90 to 0.
- Limitations: Responsiveness to be confirmed by hand on the device.

## 2026-10-25T00:16:53+05:30 — Round 3 integration check and test checklist

- Changed: `docs/TESTING.md` adds round-3 device checks (help SMS, escalation, rate limit, STATUS/RESOLVE, dashboard resolve, Malayalam reply, silent-S23 alert, map/CSV, safety timer). Live dashboard restarted on round-3 code with notifications on.
- Why: Repeatable device test pass for the new features.
- Validation: Gateway payload fields checked against the server; spare-port simulation with the gateway's exact payloads: help SMS (message with quotes/commas) → open, RESOLVE by responder → resolved, new call → reopened, CSV row correct. Runtime files restored afterwards. Live server answers `/api/incidents.csv`.
- Limitations: Device tests pending.

## 2026-10-25T00:15:22+05:30 — Incident lifecycle, help SMS, Mac notifications, map and CSV on the server

- Changed: `/api/call-event` accepts `state: "sms"` with `message` (≤ 500). New `POST /api/resolve {number, by, note, timestamp}` (404 for unknown incident); incidents have `status` open/acknowledged/resolved, `resolved` and `help_sms`; a later call, help SMS or alert reopens them. `GET /api/incidents.csv`. Background stale check broadcasts `GATEWAY_STALE` on transitions (`KAAKA_STALE_SECONDS`, default 1200, start-up grace period). Native macOS notifications via `osascript` (caller text passed as an argument, never as script) for new/reopened incidents, ACK, resolve and S23 silent/recovered; off with `--no-notify`/`KAAKA_NOTIFY=0`. Dashboard: status badges, resolve button with note, hide resolved, CSV download, Leaflet 1.9.4 (cdnjs) + OpenStreetMap map of latest locations with offline fallback. README updated.
- Why: Responders must see what is still open; the operator must notice new incidents and a silent S23 without watching the tab; overview and records.
- Validation: `py_compile`; spare-port tests 19/19 (help SMS, validation, ack/resolve/reopen, CSV escaping, broadcasts, stale transitions), persistence across restart, admin token on resolve/CSV/dashboard; `osascript` smoke test including injection-style text shown literally.
- Limitations: Dashboard map and buttons not yet checked in a browser; Leaflet loaded without integrity hashes; notifications not observed on the live server.

## 2026-10-25T00:15:22+05:30 — Help by SMS, escalation, rate limiting, responder commands and Malayalam reply on the S23

- Changed: Gateway app: an SMS containing HELP, SOS or KAAKA (whole word) or "സഹായം" is handled like a call (auto-reply, responders, dashboard event `state: "sms"` with the message); Kaaka's own messages never count. Unacknowledged incidents trigger one "Kaaka UNACKNOWLEDGED" reminder to responders after N minutes (default 5, WorkManager `EscalationWorker`). At most N replies per number per hour (default 3); extra contacts are logged and posted with `sms: "skipped"`. Responder commands `STATUS` and `RESOLVE [number] [note]` (posts `/api/resolve`). Reply language English / Malayalam / both (custom text overrides; Malayalam text needs native-speaker review). Event log keeps 200 events. Rebuilt `gateway/Kaaka.apk`.
- Why: People who cannot speak or have no credit can text; unanswered incidents must escalate; SMS credit needs protection; responders manage incidents from any phone; Malayalam-speaking callers.
- Validation: `svelte-check` 0 errors/0 warnings; `./gradlew testDebugUnitTest assembleDebug`: GatewayTextTest 11/11 (keywords, own-message exclusion, STATUS/RESOLVE/ACK parsing, reply languages, rate-limit window, open incidents, escalation check).
- Limitations: Not installed or tested on the S23; escalation timing on a sleeping phone and Malayalam SMS length untested.

## 2026-10-25T00:15:22+05:30 — Correct changelog timestamps

- Changed: Changelog headings and AI usage rows now use the time of the commit that added each entry (from `git log`); several earlier headings had estimated times up to about 50 minutes ahead of the real clock. Entries re-created during the 2026-10-24 history rewrite carry the rewrite time.
- Why: The record must not contain invented times.
- Validation: Each heading matched to its introducing commit with `git log -S`.
- Limitations: Times reflect commit time, not when work started.

## 2026-10-25T00:12:15+05:30 — Safety timer in Kaaka Sensors

- Changed: Client app: new Safety timer card (15/30/60/120 min or custom 1–720) with "I'm safe" check-in and "Extend +15 min"; on expiry a 30-second cancellable countdown then SOS with `• Trigger: safety timer`. The deadline is stored locally so an expiry while the app was closed triggers the countdown on reopen (ignored after 12 h). `emergencyService.svelte.ts` rewritten around one shared countdown (fall and timer never stack), de-duplicated SOS presses, and a user stop that clears all timers. README documents foreground limits. Rebuilt `client/KaakaSensors.apk`.
- Why: Lone travel / walking home — help should be raised when the user cannot.
- Validation: `npx svelte-check` 0 errors/0 warnings; web build, `cap sync`, `assembleDebug` succeeded; APK contains the new strings.
- Limitations: No device run; no local-notification plugin, so the timer fires only while the app is open or on reopen. No unit test runner in the client.

## 2026-10-24T23:29:53+05:30 — Prototype integration check, plan status and test checklist

- Changed: `docs/PLAN.md` updated with the complete flow (call screening and contact fallback, 112 reply, location link, responder SMS and ACK, Kaaka Sensors SOS/fall, incidents, heartbeat) and the current status; new `docs/TESTING.md` device test checklist; README links it. Mac dashboard restarted on the new code.
- Why: Record where the prototype stands and give a repeatable on-device test pass.
- Validation: Checked gateway payload fields against the server contracts; simulated a full incident on spare ports with the gateway's exact payloads (heartbeat, call with token, location page and share, Kaaka Alert in the client's report format, ACK): all 200, all five WebSocket message types received, one incident with call, alert (coords parsed), location and acknowledgement, heartbeat fresh. Test data removed and runtime files restored. Live dashboard serves the incidents panel.
- Limitations: Real-device tests are still pending (see `docs/TESTING.md`).

## 2026-10-24T23:28:13+05:30 — Incidents, location sharing page, ACK and admin token on the server

- Changed: `server/incidents.py` keeps incidents grouped by caller (last 10 digits) with calls, alerts (Coords/Maps parsed), shared locations, acknowledgement and latest location, persisted in `server/events.jsonl` (ignored by Git) and reloaded on start. `server/server.py`: `/api/call-event` accepts an optional `token` (24 h); public `GET /l/<token>` serves `server/locate.html` and `POST /api/location` records a caller's browser GPS; `POST /api/ack` marks an incident acknowledged; `GET /api/incidents`; WebSocket broadcasts `LOCATION_SHARED` and `INCIDENT_ACK`. Optional `KAAKA_ADMIN_TOKEN` protects the dashboard, status, incidents, WebSocket and gateway POSTs (header `X-Kaaka-Token`, `?token=` or cookie; constant-time compare), leaving the location page public. `--public-url`/`KAAKA_PUBLIC_URL` for display. Dashboard: incidents panel with Maps links and "awaiting acknowledgement"; feed text inserted with `textContent`. README documents the full API.
- Why: Turn individual events into incidents a responder can act on, get location from callers without the app, close the loop with acknowledgements, and allow safe public exposure.
- Validation: `py_compile`; spare-port server: 17/17 HTTP checks (tokens, location ranges, 404/400 paths, alert coords, dedupe, ack), WebSocket messages received, incidents persisted across restart, admin token enforced (401 without, 200 with header/query/cookie; location page stays public); store unit checks (expiry, ack matching/reset, grouping, damaged lines).
- Limitations: Not checked in a real browser or over an https tunnel; with an admin token set the client app's live stream is refused (it sends no token).

## 2026-10-24T23:26:17+05:30 — Location links, responder ACK and dashboard token in the gateway app

- Changed: Gateway app (`gateway/`): new settings "public link URL" and "dashboard token" (warns when the URL is not https). Every call with a caller number gets a random 12-character token sent in `/api/call-event`; with a public URL set, the reply SMS adds "Share your location: <url>/l/<token>". With a dashboard token set, all dashboard POSTs send `X-Kaaka-Token`. A responder SMS starting with "ACK" (optionally "ACK <number>") acknowledges the latest or named incident: the caller is texted that a responder has seen the call, `/api/ack` is posted, the responder gets a confirmation; ACK messages are never treated as alerts. Responder notifications end with "Reply ACK <number> to confirm." Pure-Java helpers in `GatewayText.java` with unit tests. Rebuilt `gateway/Kaaka.apk`.
- Why: Callers without the app need a way to share location; responders need to confirm they have taken an incident, and the caller needs to know.
- Validation: `svelte-check` 0 errors/0 warnings; `./gradlew testDebugUnitTest assembleDebug` passed (GatewayTextTest 4/4: token format, ACK parsing, non-ACK ignored, link only with a URL).
- Limitations: Not installed or tested on the S23 yet. The location page needs an https public URL; reply plus link may be sent as a two-part SMS.

## 2026-10-24T23:24:54+05:30 — SOS button, fall detection and beacon duration in Kaaka Sensors

- Changed: Client app (`client/`): new SOS card (`SosCard.svelte`) that sends a report to the gateway number at once and starts the beacon; optional "Auto SOS on fall" (`emergencyService.svelte.ts`, off by default): impact above ~2.5 g followed by ~2 s of stillness starts a 15-second cancellable countdown, then SOS. Reports always carry `• Coords:`/`• Maps:` or `• Location: unavailable`, plus `• Trigger:` (sos/fall/gateway reply/manual); the first report waits at most 5 s for GPS. Beacon stops after a configurable duration (default 30 minutes) and shows trigger, count, last sent and time left. README updated, including foreground-only limits. Rebuilt `client/KaakaSensors.apk`.
- Why: A person in distress must be able to raise an alert without calling, and a fall should raise one even if they cannot.
- Validation: `npx svelte-check` 0 errors/0 warnings; web build, `cap sync`, `assembleDebug` succeeded; APK contains the new strings.
- Limitations: Not run on a device. Fall thresholds are untuned heuristics; detection and the beacon only run while the app is in the foreground.

## 2026-10-24T23:23:34+05:30 — Responder alerts, 112 reply text, heartbeat and battery exemption on the S23

- Changed: Gateway app (`gateway/`): new "responder numbers" setting; every call and every Kaaka alert is texted to each responder (never to the caller/sender), with counts in the local event log. Default reply is now "Kaaka received your call. Help is being arranged. If in immediate danger, call 112." (the old default is treated as unset). WorkManager heartbeat (`Heartbeat.java`, `HeartbeatWorker.java`) posts `/api/heartbeat` every 15 minutes and on settings save when a dashboard is set. New "battery optimisation" row requests the exemption; status reports `batteryExempt`. Shared `GatewayStore.sendSms`. Rebuilt `gateway/Kaaka.apk` (adds `androidx.work`).
- Why: Alerts must reach a person even when nobody watches the dashboard; callers must be told to use 112 in immediate danger; the phone must stay awake and report that it is alive.
- Validation: `svelte-check` 0 errors/0 warnings; web build, `cap sync`, `assembleDebug`; installed on the Galaxy S23: launched without crash, call-screening role and settings kept, heartbeat job registered.
- Limitations: Heartbeat delivery to the Mac, responder SMS, the battery prompt and the new reply on a real call are not yet tested on the device; Samsung may delay the 15-minute job without the battery exemption.

## 2026-10-24T23:21:30+05:30 — Gateway heartbeat and "last seen" on the dashboard

- Changed: `server/server.py` adds `POST /api/heartbeat` (`timestamp`, `battery`, `charging`, `screeningRole`, `smsGranted`, `contactCalls`; 400 on bad input), stores the last heartbeat, reports `last_heartbeat` and `gateway_stale` (no heartbeat for 20 minutes) in `/api/status`, broadcasts `GATEWAY_HEARTBEAT`, and warns in the console when a permission is missing or the battery is low. The dashboard shows "s23: last seen …" with battery and setup state, highlighted when stale or degraded. `docs/PLAN.md` records the verified contact-call test; README mentions the heartbeat.
- Why: An emergency line that silently stops working is worse than none; the operator must see when the S23 is offline or misconfigured.
- Validation: `py_compile`; server on spare ports: heartbeat 200 and broadcast received, bad JSON/types 400, stale logic (none / 19 min / 21 min), call-event and telemetry still 200.
- Limitations: Dashboard rendering not checked in a browser; real heartbeats from the S23 pending (gateway part in the next commit).

## 2026-10-24T23:15:43+05:30 — Handle calls from saved contacts on the S23 gateway

- Changed: New `IncomingCallReceiver` in the gateway app listens for the phone-state broadcast (READ_PHONE_STATE, READ_CALL_LOG for the number) and, for calls Android does not send to call screening, sends the auto-reply SMS, logs the event and reports it to the dashboard; with "reject calls" on and ANSWER_PHONE_CALLS granted it ends the ringing call (`TelecomManager.endCall`). Shared call handling moved to `CallHandler`; `GatewayStore.claimCall` prevents a call seen by both paths from being handled twice (60 s per number). New "calls from contacts" permission row in the UI; events from this path are labelled "(contact)".
- Why: Test calls from a number saved in the S23's contacts were never passed to Kaaka Call: Telecom's history showed `contact exists` and screening sent only to Samsung's own Phone app, so nothing was rejected, texted or reported.
- Validation: `svelte-check` 0 errors/0 warnings; `assembleDebug` succeeded; installed on the Galaxy S23; `dumpsys package` shows the PHONE_STATE receiver registered and the call-screening role still held.
- Real-call test (2026-10-24 23:16 IST): call from a saved contact to the Galaxy S23 was ended, the caller received the auto-reply SMS, the app logged it as `via phone_state`, `rejected`, `sms sent`, and the Mac dashboard received the call event.
- Limitations: `TelecomManager.endCall` is deprecated; it works on the S23 today but could stop working in a future Android release (the SMS and dashboard event would still happen).

## 2026-10-24T22:45:48+05:30 — Remove hackathon template files

- Changed: Deleted `RULES.md`, `AGENTS.md`, `SUBMISSION.md` and `.github/pull_request_template.md`; README footer now links the project records instead.
- Why: Requested by the repository owner; these were event template files not used by the project.
- Validation: `git grep` finds no remaining links to the deleted files outside historical log text.
- Limitations: None identified.

## 2026-10-24T21:49:39+05:30 — Poll phone SMS for telemetry every 30 s

- Changed: `server/server.py` ADB telemetry listener now reads the phone's SMS store every 30 s instead of every 1.5 s.
- Why: Owner's request; polling `content://sms` over USB every 1.5 s was more frequent than needed.
- Validation: Python compile check. Not yet verified against the running server, which must be restarted to pick this up.
- Limitations: SMS-delivered telemetry can take up to 30 s to reach the dashboard; the client app's direct WebSocket copy is unaffected. If the client app runs on the same phone the server reads, a report can appear twice (WebSocket, then the SMS copy).

## 2026-10-24T22:21:41+05:30 — Add project plan

- Changed: Added `docs/PLAN.md` (system roles for the Mac + S23 setup, emergency flow, current status, next steps, out-of-scope items, repository workflow) and linked it from the README.
- Why: Record the agreed plan in the repository.
- Validation: Checked status entries against this changelog; links resolve.
- Limitations: Status reflects 2026-10-24; real call and telemetry tests on the S23 are still pending.

## 2026-10-24T22:13:15+05:30 — Gateway app handles calls and alerts on the S23 by itself

- Changed: Kaaka Call (`gateway/`) now has a `CallScreeningService` (`KaakaCallScreeningService.java`) that reads the incoming caller number, rejects the call (setting, on by default; call log and notification kept) and sends the auto-reply SMS natively; hidden numbers get no SMS. `AlertSmsReceiver.java` logs incoming "Kaaka Alert"/"Live Sensors" SMS without being the default SMS app. Events (last 50) and settings live in native storage (`GatewayStore.java`) so everything works with the app closed; `GatewayPlugin.java` exposes them to the rewritten UI, which requests the call-screening role and SMS permissions and shows recent events. Optional dashboard forwarding posts calls to `/api/call-event` and alerts to `/api/telemetry`. Removed the WebSocket `CALL_DETECTED` auto-send path and the `ws://` setting. Rebuilt `gateway/Kaaka.apk`; updated `gateway/README.md`.
- Why: Make the S23 the self-contained "112 alternative" gateway, with the Mac only as an optional dashboard, and stop the app needing to stay open.
- Validation: `svelte-check` 0 errors/0 warnings; web build, `cap sync`, `assembleDebug` succeeded; installed on the Galaxy S23 and launched without crashes; `dumpsys package` shows the screening service and SMS receiver registered.
- Limitations: No real call or SMS tested yet; the call-screening role and RECEIVE_SMS still need the user's approval on the phone. Android may not ask screening apps about calls from saved contacts (to be checked on the S23). Rejection outcome (busy vs voicemail) depends on the carrier.

## 2026-10-24T22:12:12+05:30 — Server as an optional dashboard for the S23 gateway (Mac + S23 setup)

- Changed: `--bt-mac`/`KAAKA_BT_MAC` is optional in `server/server.py`; without it no Bluetooth/telephony listeners start and `/api/status` reports `gateway_mode: gateway_app`. New `POST /api/call-event` (`number`, `state` rejected|allowed, `sms` sent|failed|skipped, `timestamp`) records calls handled by the gateway app, updates the last caller, and broadcasts a `CALL_EVENT` WebSocket message; it never answers, hangs up or sends SMS. Dashboard shows these events with the auto-reply result and labels Bluetooth as off in this mode. README has a "Unified setup: Mac + S23" section; the Mac Bluetooth mode is documented as an alternative that must not be combined with S23 call screening.
- Why: The S23 now handles calls itself; the Mac only needs to show what happened.
- Validation: `py_compile`; server run without `--bt-mac` on spare ports: no hfp-bridge started; call-event 200 and `CALL_EVENT` received over WebSocket; bad JSON and invalid state return 400; hidden number accepted with "no auto-reply"; `/api/telemetry` still 200; `/api/status` mode correct.
- Limitations: Dashboard rendering and real posts from the S23 not yet tested; Bluetooth mode not re-run after this change.

## 2026-10-24T22:11:46+05:30 — Start the client beacon only for the configured gateway number

- Changed: The Kaaka Sensors app starts its emergency beacon only when an SMS arrives from the configured gateway phone number (digits compared on the last 10), enforced in both `SmsReceiver.java` and `defaultSmsService.svelte.ts`; reports always go to the configured gateway number, never to the SMS sender. Keyword triggers ("call", "alert", "emergency", "kaaka") removed. Settings wording marks the computer dashboard and live stream as optional. `client/README.md` rewritten for the unified Mac + S23 flow. Rebuilt `client/KaakaSensors.apk`.
- Why: Any SMS containing those words, from any number, made the app send its sensor data and GPS location to that sender every minute.
- Validation: `npx svelte-check`: 0 errors, 0 warnings; web build, `cap sync` and `./gradlew assembleDebug` succeeded; unpacked APK contains the new rule and no keyword trigger.
- Limitations: Not tested on a device; the S23 still has the previous client build installed.

## 2026-10-24T22:01:40+05:30 — Allow the client app to reach the Mac server over plain HTTP/WebSocket

- Changed: `client/capacitor.config.ts` serves the app over `http` with cleartext allowed, and `client/android/app/src/main/AndroidManifest.xml` sets `usesCleartextTraffic="true"`.
- Why: The client app talks to the Mac server at `ws://<mac-ip>:8765` and `http://<mac-ip>:8080` on the local network; an https page blocks these as mixed content and Android blocks cleartext by default.
- Validation: Included in the client APK built and installed on the Galaxy S23 in the previous commit. These edits appeared in the working tree at 21:57 IST after the Android rebuild task and were reviewed before committing.
- Limitations: Traffic between the phone and the Mac is unencrypted on the local network.

## 2026-10-24T22:01:16+05:30 — Stream live sensor readings to the dashboard

- Changed: `server/server.py` accepts the client app's sensor JSON on `POST /api/telemetry` (port 8080), formats it as a "Kaaka Live" report and broadcasts it to the dashboard without a console banner or disk write per reading; added a CORS preflight (`OPTIONS`) handler. Client app: backend sync is on by default and runs whenever Settings → Telemetry backend is set (the UI had no switch for it, so it never ran); placeholder now `http://<mac-ip>:8080`. Rebuilt `client/KaakaSensors.apk`.
- Why: The dashboard's live telemetry never updated: the client only sent readings to an unset backend URL (pointing at the separate Node service on :3001), sync could not be switched on, and the server had no preflight handler.
- Validation: Preflight returns 204; a sample sensor POST returned success and a WebSocket client received the formatted "Live sensor stream" report; client rebuilt with Gradle and installed on the Galaxy S23 (`adb install -r` Success).
- Limitations: Live stream readings carry no GPS coordinates (the full alert report still does). On-device streaming not yet confirmed at the time of this entry.

## 2026-10-24T21:47:25+05:30 — Count only phones as gateway connections

- Changed: `server/server.py` treats WebSocket clients from this machine (loopback or the server's own IP, e.g. the dashboard in a local browser) as non-phones in the call log, `/api/status` and pending-call replay, and warns on macOS when a call arrives with no gateway app connected.
- Why: During testing the log said "Gateway App Link: Connected" while only the Mac's own dashboard was connected, hiding why no SMS was sent.
- Validation: End-to-end test on 2026-10-24 21:44 IST before this change: gateway app on the Galaxy S23 connected over Wi-Fi, incoming call detected with caller number, 1-ring hangup, app confirmed "Auto-sent SMS" and the caller received it. After the change: server restarted, HFP reconnected, `/api/status` no longer lists the local dashboard as a gateway.
- Limitations: The gateway app only keeps its server connection while it is in the foreground; with the screen off or the app in the background no auto-reply SMS is sent. One test call arrived without a caller number, so no SMS was sent for it (by design).

## 2026-10-24T21:41:04+05:30 — Add rebuilt Kaaka debug APKs

- Changed: Added `gateway/Kaaka.apk` (`com.kaaka.callapp`, label "Kaaka Call") and `client/KaakaSensors.apk` (`com.kaaka.sensors`, label "KaakaSensors"), debug builds of the previous commit.
- Why: Installable apps for the gateway phone and the client phone.
- Validation: `aapt dump badging` confirms app IDs and labels; unpacked APKs contain none of the old numbers, IPs or names; `gateway/Kaaka.apk` installed on the Galaxy S23 with `adb install -r` (Success).
- Limitations: Debug-signed builds. The client app requests the default-SMS role and is meant for a separate phone, not the gateway phone.

## 2026-10-24T21:41:04+05:30 — Make the Android apps' server and phone numbers configurable

- Changed: Removed hardcoded phone numbers, server IPs and device IDs from `client/` and `gateway/`. Client: new Settings card (`SettingsCard.svelte`, `appSettings.svelte.ts`) for gateway phone number, Mac server WebSocket and telemetry backend URL, with a red "Not set" warning; the authorized number is mirrored to native SharedPreferences for `SmsReceiver.java`; telemetry device ID is now a random per-install ID. Gateway: server endpoint starts empty and the app shows "no server" until set; saving a new endpoint reconnects; manual sends without a number show an error instead of using a fallback. `gateway/README.md` rewritten to describe the current app. `client/package-lock.json` resynced with `package.json`.
- Why: Old test-device values were baked into the apps and could send SMS to fixed numbers.
- Validation: `svelte-check` (client): 0 errors, 0 warnings; both apps built with `./gradlew assembleDebug`; repo-wide `git grep` finds none of the old numbers, IPs or paths.
- Limitations: Settings UI not yet checked on a real device; end-to-end SMS/WebSocket not yet tested. The client still starts its telemetry beacon for any SMS containing "call", "alert", "emergency" or "kaaka", from any sender (unchanged behavior, flagged for review).

## 2026-10-24T21:35:08+05:30 — Remove hardcoded phone numbers, addresses and device IDs from the server

- Changed: `server/server.py` no longer contains phone numbers, Bluetooth addresses or adb serials. `--bt-mac`/`KAAKA_BT_MAC` is required; new optional `--client-number`/`KAAKA_CLIENT_NUMBER` and `--adb-serial`/`KAAKA_ADB_SERIAL`. Calls without caller ID stay "unknown" and never trigger an auto-reply SMS (previously they were relabeled with a fixed number that the gateway app could SMS). "Last caller" shows none until a real call and is kept across restarts in `server/last_call.json` (ignored by Git). Simulated calls/telemetry no longer use real numbers. `server/audio_bridge.py` reads the n8n webhook from `KAAKA_WEBHOOK_URL`/`KAAKA_WEBHOOK_FALLBACK_URL` (bridge stays off without it) and the Linux speaker/mic from `KAAKA_SPEAKER_SINK`/`KAAKA_MIC_SOURCE` or the PipeWire defaults. The dashboard shows the configured Bluetooth address and webhook from `/api/status`. Removed a machine-specific Python path from `package.json` and the TTS service (`KAAKA_TTS_PYTHON`). Device-specific wording replaced with "gateway phone"; README documents all settings.
- Why: Values from the original test devices were showing as real data (for example an old number as "last caller extracted").
- Validation: Python compile checks; `git grep` finds none of the old numbers, IPs, MAC or adb serials outside the Android apps (handled separately); restarted the server against the S23: HFP connected, `/api/status` returns `last_call_number: null`, configured `bt_mac`, empty `webhook_url`; dashboard served.
- Limitations: No real call placed after this change. Hardcoded values in the Android apps are being removed in a separate change.

## 2026-10-24T21:35:08+05:30 — Connect hands-free on the first attempt

- Changed: `mac/hfp-bridge` now creates the hands-free object and calls `connect()` one second later (skipping stale attempts), and logs each connection step.
- Why: When the phone's link was already up, the SDP query returned from cache within a millisecond and IOBluetooth silently dropped a `connect()` issued in the same run-loop pass, so the first attempt always timed out (about 28 s to connect).
- Validation: Three bridge runs against the Galaxy S23 connected in 3.4 s, 2.2 s and 2.0 s on attempt 1; server end-to-end run (no calls) connected about 2 s after start.
- Limitations: Answer/hangup/caller ID not re-tested with a real call after this change.

## 2026-10-24T21:28:30+05:30 — Run the call server on macOS via hfp-bridge

- Changed: Added `mac/hfp-bridge` (Swift, IOBluetooth Hands-Free client that emits JSON-line events and accepts answer/hangup/status/quit commands, with a reconnect watchdog and caller-ID via CLIP/CLCC) and `server/mac_telephony.py` (subprocess client). `server/server.py` and `server/audio_bridge.py` guard Linux-only imports and, on macOS, use hfp-bridge for call detection, answer and hangup; auto-answer defaults off on macOS. Added `server/requirements-mac.txt` and a macOS section in the README. Also imported `subprocess` in `server.py`, which the ADB telemetry thread needed (it failed silently before, including on Linux).
- Why: Run the server side on a MacBook (Apple Silicon) with a Galaxy S23 as the hands-free audio gateway.
- Validation: `swift build -c release` with no warnings; Python compile checks; server run against a stub bridge (CALL_DETECTED broadcast, hangup/answer commands, /api/status, missing-binary path); live run with the real bridge and S23 on 2026-10-24: HFP connected, real incoming call detected with caller number, 1-ring hangup sent and call ended. Fresh server run confirmed dashboard title, /api/status and console banner show Kaaka.
- Limitations: No call audio on macOS (SCO unsupported), so the AI voice loop is disabled there. Bluetooth MAP SMS is Linux-only; the gateway app sends the auto-reply SMS. First HFP connect attempt after start can time out (20 s) before the retry succeeds.

## 2026-10-24T21:28:02+05:30 — Import call and telemetry system as Kaaka

- Changed: Imported the existing call and telemetry code from a separate local folder and renamed it to Kaaka during import: `client/` (Capacitor sensor + default-SMS app, app ID `com.kaaka.sensors`), `gateway/` (Capacitor call/SMS gateway app, app ID `com.kaaka.callapp`), `server/` (Python PipeWire/oFono call server, audio bridge, dashboard, Node telemetry backend), `scripts/`, and the project README. Alerts use the "Kaaka Alert:" prefix.
- Why: Consolidate the project into this repository under its new name before porting the server to macOS.
- Validation: Compared against the source folder: the only differences are the name, app ID and Java package changes. Dependency/build folders, prebuilt APKs and runtime telemetry data were not imported.
- Limitations: Server side is Linux-only at this point (PipeWire, BlueZ, D-Bus). Android apps must be rebuilt to get Kaaka APKs. This code was written before this repository was created. History was rewritten on 2026-10-24 (about 22:00 IST) at the owner's request so the earlier project name does not appear; the rename is folded into this import.

## 2026-10-24T21:19:14+05:30 — Add hfptest Bluetooth hands-free feasibility tool

- Changed: Added `tools/hfptest` (Swift package, IOBluetooth) that lists paired devices with HFP Audio Gateway SDP status, connects to a phone as a Hands-Free unit, logs indicators/incoming calls, answers calls, requests SCO audio and records any Bluetooth input device to WAV.
- Why: Check whether a MacBook (Apple Silicon, macOS 27) can replace the Linux PipeWire hands-free setup used by the call server.
- Validation: Built with `swift build`; live tests against a Galaxy S23 on 2026-10-24: HFP connection PASS, incoming call detected PASS, answer from Mac worked, SCO audio FAIL (`kIOReturnUnsupported`, 0xE00002C7), no Bluetooth CoreAudio device appeared.
- Limitations: macOS does not provide HFP call audio (SCO) to apps; only call control works. `connect()` silently does nothing unless the baseband link is opened and SDP refreshed first (handled in the tool).

## Template setup — 10 October 2026

- Changed: Added the event README, rules, agent guide, change log, AI usage record, submission checklist, Git ignore rules, and pull request checklist.
- Why: Give participants a consistent starting point for event rules, basic coding patterns, documented changes, and regular commits.
- Validation: Checked local Markdown links, event detail consistency, required documents, and diff whitespace before publishing.
- Limitations: Documentation scaffolding only; no participant project, application, or working demo is included. GitHub publication and template status are verified separately after creation.
