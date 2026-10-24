# kaaka — Kaaka Emergency Telemetry & Response Platform

> **Abstract**: An edge-aware emergency telemetry and rapid-response system combining real-time physical sensor detection with automated telephony gateways and localized speech microservices. Built with Capacitor 7, Svelte 5 (runes mode), Node.js, Linux PipeWire D-Bus telephony monitors, and Malayalam voice AI (TTS/ASR), the platform bridges on-device incident detection with automated dispatch and base-station notification channels for reliable emergency intervention.

Plan, status and next steps: [docs/PLAN.md](docs/PLAN.md)

## Unified setup: Mac + S23

The whole system is two devices. Callers are outside people using their own phones.

| Device | Role | What runs |
|---|---|---|
| **Galaxy S23** (the gateway number) | Telephony | **Kaaka Call** gateway app: screens incoming calls, rejects them, sends the caller an auto-reply SMS, and receives "Kaaka Alert" SMS reports |
| **Mac** | Dashboard / server | `server/server.py` **without `--bt-mac`**: receives the S23's events over Wi-Fi and shows them on the dashboard |

Flow:

1. A caller rings the S23's number.
2. The gateway app on the S23 screens the call, rejects it and sends an auto-reply SMS (no SMS when the caller ID is hidden).
3. The S23 reports the call to the Mac: `POST http://<mac-ip>:8080/api/call-event` with `{"number", "state": "rejected"|"allowed", "sms": "sent"|"failed"|"skipped", "timestamp"}`. The dashboard feed shows e.g. "call from … — rejected, auto-reply sent".
4. If a caller uses the optional **Kaaka Sensors** app, it sends "Kaaka Alert" SMS reports to the S23; the gateway app logs them and forwards them to the Mac (`POST /api/telemetry`).

Start the dashboard server on the Mac (no Bluetooth):

```bash
.venv-mac/bin/python server/server.py
```

Then, in the gateway app on the S23, set **Dashboard server** to `http://<mac-ip>:8080` (the server prints its IP on startup). Both devices must be on the same Wi-Fi.

**Do not combine this with the Bluetooth mode.** In this mode the server runs without `--bt-mac`. If the Mac were also connected to the S23 as a Bluetooth hands-free unit, both the Mac and the S23's own call screening would hang up the same call and handle it twice. The macOS Bluetooth section below describes an alternative mode, not an add-on.

**Kaaka Sensors (`client/`) is optional.** It is only for callers who choose to install it on their own phones; the S23 gateway does not need it.

---

## Project Description

**kaaka** establishes an integrated emergency response loop split across three specialized components:

* **Client App (`client/`)** — Personal device application monitoring 5 hardware sensors (accelerometer, gyroscope, magnetometer, ambient light, pedometer). It evaluates kinematic thresholds to detect incidents/falls, packages live telemetry into emergency SMS broadcasts, and acts as a designated Android Default SMS Handler to execute full-screen wake locks, lockscreen dismissal, and continuous vibration alarms upon authorized triggers.
* **Gateway App (`gateway/`)** — Mobile base-station client that links with local telephony listeners via WebSockets. It detects incoming calls over Bluetooth hands-free profiles (HFP) in real time and automatically dispatches immediate SMS alerts to callers without requiring manual device interaction.
* **Server & Services (`server/`)** — Edge infrastructure hosting real-time telemetry ingestion and WebSocket distribution (`server/backend`), PipeWire/oFono telephony D-Bus monitors (`server/server.py`), live bidirectional call audio bridge (`server/audio_bridge.py`), localized Malayalam Piper TTS (`server/services/malayalam-tts`), Malayalam voice ASR (`server/services/malayalam-voice-asr`), n8n workflow automation (`server/services/n8n`), and incident dashboard (`server/dashboard.html`).
* **Bidirectional Voice AI Loop** — Captures active Bluetooth phone call audio, transcribes Malayalam speech using the fine-tuned **Thennal Whisper** model, generates context-aware responses with **Gemma** via **Ollama**, synthesizes fluent speech using the **Meera ONNX** voice on **Piper TTS**, and injects audio back into the call uplink so callers converse with a local AI assistant in real time.

---

## Architecture

```
kaaka/
├── client/                     # Sensor telemetry, fall detection & default SMS receiver
├── gateway/                    # Automated Bluetooth call monitor & quick-dial app
└── server/
    ├── backend/                # Telemetry ingestion & WebSocket streaming server
    ├── services/
    │   ├── malayalam-tts/      # Malayalam Piper Text-to-Speech container (Meera model)
    │   ├── malayalam-voice-asr/# Malayalam Speech Recognition service (Thennal Whisper model)
    │   └── n8n/                # n8n event orchestration workflows
    ├── audio_bridge.py         # Real-time Bluetooth call audio recording & AI playback bridge
    ├── server.py               # PipeWire Bluetooth call monitor & WebSocket server
    ├── dashboard.html          # Real-time incident & telemetry web dashboard
    └── extract_call_number.py  # D-Bus telephony inspection CLI
```

---

## System Sequence Diagrams

The interactions between **Client (App)**, **Gateway (App)**, and **Server** are coordinated via cellular SMS, local WebSockets, D-Bus IPC, PipeWire audio routing, and HTTP REST APIs.

### 1. Hands-Free Telephony & Auto-Responder (`server.py` & Gateway)
When an incoming call is picked up via Bluetooth hands-free audio, the Python telephony server extracts caller metadata over Linux D-Bus and coordinates with the Gateway app over WebSockets for automatic SMS response.

```mermaid
sequenceDiagram
    autonumber
    actor Caller as 📞 External Caller
    participant PW as 🎧 Linux PipeWire (D-Bus)
    participant PyServer as 🐍 Python Telephony Server (server.py)
    participant Gateway as 📱 Gateway App (Phone B)
    actor Responders as 👥 Emergency Responders

    Caller->>PW: Incoming phone call (HFP / mSBC codec)
    PW->>PyServer: D-Bus signal: org.pipewire.Telephony.CallAdded
    Note over PyServer: extract_call_number() parses LineIdentification & caller name
    PyServer->>PyServer: Check debounce window (15s throttle)
    PyServer->>Gateway: WebSocket Broadcast (port 8765): CALL_DETECTED {number, name, state}
    Note over Gateway: Svelte 5 state catches event & triggers autoSend check
    Gateway->>Gateway: DirectSmsPlugin.sendSms(number, message)
    Gateway-->>Caller: Instant automated SMS dispatch via cellular network
    Gateway->>PyServer: WebSocket confirmation: SMS_SENT {number, timestamp}
    PyServer->>Responders: Telephony event logged & ready for n8n notification
```

---

### 2. Emergency Incident Detection & Server Telemetry Ingestion
When kinematics detect an emergency or fall anomaly, the Client app executes multi-channel alerting: syncing full 5-axis telemetry with the backend server while dispatching an emergency SMS payload to the Gateway.

```mermaid
sequenceDiagram
    autonumber
    actor User as 🏃 Person / Device Carrier
    participant Sensors as 🧭 Hardware Sensors (5-Axis)
    participant Client as 📱 Client App (Phone A)
    participant Server as 🖥️ Server (Backend & Microservices)
    participant Gateway as 📱 Gateway App (Phone B)

    User->>Sensors: Impact / Kinematic shock event (Fall anomaly)
    Sensors->>Client: High sampling rate streams (Accel >2.5G, Gyro tilt, Stillness)
    Note over Client: sensorManager.svelte.ts evaluates threshold anomaly
    
    par Multi-Channel Alert & Ingestion
        Client->>Server: HTTP POST /api/telemetry (Accel, Gyro, Mag, Lux, Pedometer)
        Server->>Server: alertEngine checks safety thresholds & caches readings
        Server->>Server: Synthesize Malayalam voice alert (Piper TTS /speech)
        Server->>Server: Trigger n8n webhook workflow for multi-platform dispatch
    and Direct Cellular Emergency SMS
        Client->>Client: DirectSmsPlugin.sendSms(authorizedTarget, telemetrySnapshot)
        Client-->>Gateway: Encoded Emergency SMS broadcast (to gateway number)
    end

    Note over Gateway: Gateway / Phone B receives distress telemetry and logs incident
```

---

### 3. Default SMS App Role & Emergency Alarm Wake Lock
When an incoming emergency trigger is received on an Android device running the Client app with the Default SMS role, it intercepts the message at highest priority, bypasses lockscreens, and sounds vibration alarms.

```mermaid
sequenceDiagram
    autonumber
    participant Cellular as 📶 Cellular Network
    participant AndroidOS as 🤖 Android OS (Telephony Provider)
    participant SmsReceiver as ⚡ SmsReceiver (Java BroadcastReceiver)
    participant MainActivity as 📱 MainActivity (Full-Screen Activity)
    participant SvelteUI as 🎨 Svelte 5 UI (/receiver route)

    Cellular->>AndroidOS: Incoming SMS payload
    AndroidOS->>SmsReceiver: Broadcast intent: SMS_DELIVER (Priority 999)
    SmsReceiver->>AndroidOS: Save SMS to telephony provider inbox
    SmsReceiver->>SmsReceiver: Verify sender matches configured gateway number

    alt Sender is Authorized Emergency Contact
        SmsReceiver->>SmsReceiver: Acquire PowerManager Full WakeLock (10s)
        SmsReceiver->>SmsReceiver: Trigger high-intensity alarm vibration waveform
        SmsReceiver->>AndroidOS: Post heads-up notification with FullScreenIntent
        SmsReceiver->>MainActivity: launchMainActivity() with FLAG_ACTIVITY_REORDER_TO_FRONT
        MainActivity->>MainActivity: unlockAndTurnOnScreen() & hideStatusBar()
        MainActivity->>SvelteUI: DefaultSmsPlugin.handleIncomingSms(sender, message)
        Note over SvelteUI: Svelte 5 runes update triggerCount & display active alert card
    else Regular Contact
        SmsReceiver->>AndroidOS: Post standard messages notification (no screen wake)
    end
```

---

### 4. Bidirectional Malayalam Voice AI Conversation Loop (`audio_bridge.py` & n8n)
During an active Bluetooth call, the audio bridge records 10s segments and routes them through a complete edge AI pipeline—transcribing via Thennal Whisper, reasoning via Gemma on Ollama, synthesizing fluent Malayalam speech via Piper TTS (Meera model), and streaming the reply directly into the phone call uplink.

```mermaid
sequenceDiagram
    autonumber
    actor Caller as 📞 Caller
    participant PW as 🎧 PipeWire / PulseAudio (HFP Audio)
    participant Bridge as 🎙️ audio_bridge.py
    participant N8N as ⚡ n8n Webhook Workflow
    participant Thennal as 🗣️ Thennal Whisper ASR
    participant Ollama as 🧠 Ollama (Gemma LLM)
    participant Meera as 🔊 Piper TTS (Meera Model)

    Caller->>PW: Speaks in Malayalam over active Bluetooth phone call
    PW->>Bridge: Routes call audio to call_record null-sink
    Note over Bridge: Records 10s audio segment & encodes to MP3 via ffmpeg
    Bridge->>N8N: POST /webhook/passive (record.mp3)

    rect rgb(20, 30, 40)
        Note over N8N: Voice AI Conversation Pipeline
        N8N->>Thennal: Pass audio chunk for speech transcription
        Thennal-->>N8N: Extracted Malayalam text (Thennal fine-tuned Whisper)
        N8N->>Ollama: Prompt with transcript, emergency telemetry & intent
        Ollama-->>N8N: Generated Malayalam conversational response (Gemma)
        N8N->>Meera: Synthesize response text into speech (ml_IN-meera-medium.onnx)
        Meera-->>N8N: High-quality neural Malayalam audio reply
    end

    N8N-->>Bridge: Returns generated Malayalam audio response (.mp3/.wav)
    Bridge->>PW: Injects audio into call_playback sink & BlueZ mic uplink
    PW-->>Caller: Plays synthesized AI voice directly into phone earpiece
    Note over Caller,Bridge: Conversation continues iteratively for duration of active call
```

## Quick Start

### Client (App)
```bash
# Run web preview
npm run dev:client

# Build web assets
npm run build:client
```

### Gateway (App)
```bash
# Run web preview
npm run dev:gateway

# Build web assets
npm run build:gateway
```

### Server
```bash
# Run telemetry server
npm run dev:server

# Run Bluetooth telephony listener
python3 server/server.py
```

---

## Optional alternative: Mac as a Bluetooth hands-free unit (macOS)

> Alternative to the unified Mac + S23 setup above, not to be combined with it: here the Mac detects and hangs up calls over Bluetooth (`--bt-mac`) and the gateway app only sends the SMS.

The server side also runs on an Apple Silicon Mac (tested on macOS 27). The Linux PipeWire/oFono telephony layer is replaced by `mac/hfp-bridge`, a small Swift helper that connects to the phone as a Bluetooth hands-free unit through Apple's IOBluetooth framework. `server/server.py` starts it automatically and talks to it over stdin/stdout. All Linux code paths are unchanged.

### Setup

Run all commands from the repository root (`kaaka/`).

1. **Pair the phone** with the Mac (System Settings → Bluetooth), and allow **Calls** for the Mac in the phone's Bluetooth settings for that device.
2. **Build the bridge:**
   ```bash
   (cd mac/hfp-bridge && swift build -c release)
   ```
3. **Bluetooth permission:** macOS asks the app you launch the server from (Terminal, iTerm, VS Code…). Allow it under System Settings → Privacy & Security → Bluetooth. Without it, the bridge hangs or sees no devices.
4. **Python environment:**
   ```bash
   python3 -m venv .venv-mac
   .venv-mac/bin/pip install -r server/requirements-mac.txt
   ```
5. **Run** with your phone's Bluetooth address (shown in System Settings → Bluetooth or `system_profiler SPBluetoothDataType`); the address below is only an example:
   ```bash
   .venv-mac/bin/python server/server.py --bt-mac AA:BB:CC:DD:EE:FF   # your phone's Bluetooth address (System Settings → Bluetooth)
   ```
   Leave the terminal input alone while it runs: pressing Enter in the server console simulates a call.
   Set `HFP_BRIDGE_BIN` to use a bridge binary from another location.

   Settings (nothing is hardcoded; unset optional settings disable that feature):

   | Option | Environment variable | Purpose |
   |---|---|---|
   | `--bt-mac` (this mode only) | `KAAKA_BT_MAC` | Gateway phone's Bluetooth address; omit it for the unified Mac + S23 setup |
   | `--client-number` | `KAAKA_CLIENT_NUMBER` | Client (sensor) phone number; its SMS are read as telemetry (otherwise only "Kaaka Alert" texts match) |
   | `--adb-serial` | `KAAKA_ADB_SERIAL` | adb device to read SMS from (default: the only attached device) |
   | — | `KAAKA_WEBHOOK_URL`, `KAAKA_WEBHOOK_FALLBACK_URL` | n8n voice-AI webhook (Linux audio bridge; off when unset) |
   | — | `KAAKA_SPEAKER_SINK`, `KAAKA_MIC_SOURCE` | Linux PipeWire speaker/mic (default: system defaults) |
   | — | `KAAKA_TTS_PYTHON` | Python with `piper-tts` for `npm run tts` |

   Calls without caller ID stay "unknown" and never trigger an auto-reply SMS. The last real caller is kept in `server/last_call.json` (not committed).
6. **Point the Gateway app** at the Mac: open its settings and set the WebSocket URL to `ws://<Mac's Wi-Fi IP>:8765` (the server prints this IP on startup).

### What works on macOS

| Feature | macOS | Notes |
|---|---|---|
| Incoming call detection + caller number → `CALL_DETECTED` over WebSocket | ✅ | via `hfp-bridge` |
| Gateway app auto-SMS reply | ✅ | triggered by `CALL_DETECTED` |
| Answer / 1-ring hangup | ✅ | via `hfp-bridge`. **Default mode on macOS is 1-ring hangup**; toggle with `POST /api/audio-bridge/mode` |
| Hands-free auto-reconnect | ✅ | `hfp-bridge` reconnects itself (replaces the BlueZ watchdog) |
| Dashboard (`:8080`), WebSocket (`:8765`), HTTP/WebSocket telemetry, ADB SMS ingest | ✅ | unchanged |
| Bluetooth MAP SMS reading / sending | ❌ | macOS has no Message Access Profile client API. Telemetry still arrives via ADB, HTTP and WebSocket; the reply SMS is sent by the Gateway app |
| Voice AI loop (`audio_bridge.py`: call audio → n8n → reply into the call) | ❌ | macOS refuses hands-free call audio: IOBluetooth's `connectSCO` returns `kIOReturnUnsupported`, and no Bluetooth audio device appears in CoreAudio. Call audio stays on the phone. The dashboard reports the bridge as "unsupported on macOS" |

For the voice AI loop, keep using the Linux setup (or a Linux machine/VM with its own USB Bluetooth adapter).

---

Project records: [CHANGELOG.md](CHANGELOG.md) · [AI_USAGE.md](AI_USAGE.md) · [docs/PLAN.md](docs/PLAN.md)
