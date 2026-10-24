# AI usage record

Use Codex during the hackathon and briefly document its actual contribution here. Add a row after each meaningful task or milestone. Keep summaries concise and omit secrets, private data, and full chat transcripts.

## Event build log

| Date and time with timezone | Tool / model, if known | Task | Assistance and affected files | Human review / corrections | Validation and result |
| --- | --- | --- | --- | --- | --- |
| 2026-10-24T21:20:00+05:30 | Claude Code (Claude Opus 5.5) | Build HFP feasibility tool | Wrote `tools/hfptest` (IOBluetooth HF client, CoreAudio listing, WAV recording) and ran device tests | Reviewed and directed by Abhiram N J; corrected class choice (HandsFreeDevice, not AudioGateway) after reading SDK headers | Live S23 tests: connect/incoming/answer pass, SCO unsupported |
| 2026-10-24T21:50:00+05:30 | Claude Code (Claude Opus 5.5) | Rename imported code to Kaaka | Scripted name/app-ID replacement and Java package moves during import | Scope chosen by Abhiram N J | Diff against source shows only rename changes; build checks in the following commit |
| 2026-10-24T21:40:00+05:30 | Claude Code (Claude Opus 5.5), two parallel sub-agents | Port server to macOS | Planned the port; sub-agents wrote `mac/hfp-bridge` and the macOS changes in `server/server.py`, `server/audio_bridge.py`, `server/mac_telephony.py`, README section | Reviewed by Abhiram N J during live call tests | Stub-bridge tests and a live S23 call: number captured, hangup worked |
| 2026-10-24T21:28:00+05:30 | Claude Code (Claude Opus 5.5), sub-agent | Fix slow first HFP connect | Diagnosed run-loop timing issue and fixed `mac/hfp-bridge`; neutral wording in server logs; README path updates | Requested by Abhiram N J | Three timed S23 connections on first attempt |
| 2026-10-24T21:36:00+05:30 | Claude Code (Claude Opus 5.5) | Remove hardcoded values from server | Made numbers, addresses, adb serial, webhook and audio devices configurable in `server/`, dashboard, scripts and README | Requested by Abhiram N J | Compile checks, repo grep, live server status check |
| 2026-10-24T21:55:00+05:30 | Claude Code (Claude Opus 5.5), sub-agent | Configurable app settings; rebuild APKs | Replaced hardcoded numbers/IPs in `client/` and `gateway/` with settings, rebuilt both APKs, installed the gateway app on the S23 | Requested by Abhiram N J; on-device check pending | svelte-check clean; Gradle builds succeeded; `adb install` Success |
| 2026-10-24T22:05:00+05:30 | Claude Code (Claude Opus 5.5) | Fix live telemetry not reaching the dashboard | Diagnosed on-device settings and client sync code; server sensor-stream ingest + CORS preflight; client sync default and rebuild | Reported by Abhiram N J | Preflight, sample POST and WebSocket broadcast verified; APK installed |

## Template preparation

On 10 October 2026, Codex prepared this documentation template from the organizer's supplied rules and checked the linked Luma page for the event name and dates. This covered `README.md`, `RULES.md`, `AGENTS.md`, `CHANGELOG.md`, `AI_USAGE.md`, `SUBMISSION.md`, `.gitignore`, and the pull request checklist. Agent validation covered local links, event consistency, required documents, and diff whitespace; organizer review is pending.

This preparation is separate from participant project implementation and participant AI usage during the event.
