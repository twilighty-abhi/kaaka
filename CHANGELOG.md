# Change log

Record each meaningful project change during the event, newest first. Update this file in the same commit as the change. Use a real timestamp with timezone, for example `YYYY-MM-DDTHH:MM:SS+05:30`.

## Event build log

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
