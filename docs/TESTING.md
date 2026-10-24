# Kaaka device test checklist

Run these in order with the Mac dashboard and the Galaxy S23 (gateway). Tick each step and note anything unexpected.
Phone numbers below are placeholders; use your own test phones.

## 0. Setup

- [ ] Mac: dashboard running (`.venv-mac/bin/python server/server.py`, no `--bt-mac`); open `http://<mac-ip>:8080`.
- [ ] S23 connected by USB; install the latest gateway build: `adb install -r gateway/Kaaka.apk`.
- [ ] S23 on the same Wi-Fi as the Mac.
- [ ] Kaaka Call setup rows all green: call screening **on**, SMS **granted**, calls from contacts **granted**, battery optimisation **exempt**.
- [ ] Kaaka Call [config]: dashboard server `http://<mac-ip>:8080`; responder numbers = one test phone (call it **Responder**); public link URL empty for now; save.

## 1. Heartbeat

- [ ] Within a minute of saving settings the dashboard shows "s23: last seen …" with battery and "setup ok".

## 2. Call from an unknown number (call screening)

Use a phone whose number is **not** saved in the S23's contacts (call it **Caller**).

- [ ] Call is rejected immediately.
- [ ] Caller receives: "Kaaka received your call. Help is being arranged. If in immediate danger, call 112."
- [ ] Responder receives "Kaaka: call from <Caller> … Reply ACK <Caller> to confirm."
- [ ] Kaaka Call event list shows the call (no "(contact)"), "sms sent", "1 responders texted".
- [ ] Dashboard: new incident for Caller, "awaiting acknowledgement".

## 3. Call from a saved contact (fallback)

- [ ] Same as step 2, event shows "(contact)". (Already verified once on 2026-10-24.)

## 4. S23 locked, app closed

- [ ] Swipe Kaaka Call away from recents, lock the S23, repeat step 2. Same results.

## 5. Responder ACK

- [ ] From Responder, text the S23: `ACK <Caller number>`.
- [ ] Caller receives "A Kaaka responder has seen your call and will contact you soon."
- [ ] Responder receives "Kaaka: ACK recorded for <Caller>".
- [ ] Dashboard incident shows "acknowledged by <Responder>".
- [ ] Texting `ACK` from a number that is not a responder does nothing.

## 5b. Round 3 on the S23

- [ ] **Help by SMS:** from Caller, text the S23 "HELP stuck near the bridge". Caller gets the reply; Responder gets "Kaaka: help SMS from …"; dashboard incident shows the message; Mac shows a notification.
- [ ] An ordinary SMS without HELP/SOS/KAAKA does nothing.
- [ ] **Escalation:** after a call, do not ACK. After 5 minutes Responder gets "Kaaka UNACKNOWLEDGED: …" once.
- [ ] **Rate limit:** call 4 times from Caller within an hour; the 4th gets no reply and no responder text (event shows "rate-limited"; dashboard still shows the call).
- [ ] **STATUS:** Responder texts `STATUS`; gets the list of open incidents.
- [ ] **RESOLVE:** Responder texts `RESOLVE <Caller number> reached, safe`; gets "Kaaka: resolved …"; dashboard shows resolved (greyed); a new call from Caller reopens it.
- [ ] **Caller reports SAFE:** after a call from Caller, text `SAFE` (or "I'm safe") from Caller to the S23. Caller gets "Kaaka: glad you are safe. Your alert is closed…"; Responder gets "Kaaka: <Caller> reported safe at …"; dashboard shows the green "safe" badge and "closed by caller"; no escalation reminder follows. Texting `SAFE` again (no open incident) gets no reply.
- [ ] **I'm safe button (Kaaka Sensors):** press SOS, then "I'm safe — close my alert": the beacon stops, the app shows "SAFE sent", and the dashboard closes the incident.
- [ ] **Resolve from dashboard:** press [resolve] on an incident, add a note; status changes; [hide resolved] hides it.
- [ ] **Reply language:** set Malayalam, call; check the Malayalam reply arrives correctly (and have a native speaker check the wording). Set back to English or Both.
- [ ] **Silent S23 alert:** turn off the S23's Wi-Fi for 20+ minutes (or stop Kaaka Call); the dashboard and a Mac notification report the S23 as silent; turning Wi-Fi back on clears it.
- [ ] **Map and CSV:** incidents with locations appear on the dashboard map (needs internet); [download csv] downloads the incident list.

## 6. Kaaka Sensors on a second Android phone (optional)

Install `client/KaakaSensors.apk` on a phone that is **not** the S23. In its Settings set the gateway number to the S23's number.

- [ ] Press **SOS**: the S23 receives a "Kaaka Alert" SMS; Responder gets "Kaaka alert from …"; dashboard incident shows the alert and a Maps link once GPS is available.
- [ ] Beacon keeps sending reports and stops after its duration (or Stop).
- [ ] **Safety timer:** start a 15-minute timer; press "I'm safe" → it stops. Start again and let it run out → 30-second countdown → SOS ("Trigger: safety timer").
- [ ] Auto SOS on fall (enable in settings): a hard drop onto a bed followed by stillness starts a 15-second countdown; "I'm OK" cancels it.
- [ ] Automatic trigger (only if Kaaka Sensors is that phone's default SMS app): calling the S23 from that phone makes the reply start the beacon.

## 7. Location link (optional, needs an https public URL)

Only after deciding how to expose the dashboard (for example a tunnel to port 8080). Set `KAAKA_ADMIN_TOKEN` on the Mac and the same value as "dashboard token" in Kaaka Call first.

- [ ] Set Kaaka Call's public link URL to the https address; call from Caller.
- [ ] The reply SMS contains "Share your location: https://…/l/<token>".
- [ ] Opening it on Caller's phone and allowing location shows the location in the dashboard incident.

## Known limits

- No voice conversation with the caller (Android/macOS give apps no call audio).
- Kaaka Sensors fall detection and beacon only run while the app is open; fall thresholds are untuned.
- Ending a ringing call from a saved contact uses a deprecated Android API; if it stops working the SMS and dashboard event still happen.
