# kaaka — Kaaka Emergency Telemetry & Response Platform

> **Abstract**: An edge-aware emergency telemetry and rapid-response system combining real-time physical sensor detection with automated telephony gateways and localized speech microservices. Built with Capacitor 7, Svelte 5 (runes mode), Node.js, Linux PipeWire D-Bus telephony monitors, and Malayalam voice AI (TTS/ASR), the platform bridges on-device incident detection with automated dispatch and base-station notification channels for reliable emergency intervention.

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
        Client-->>Gateway: Encoded Emergency SMS broadcast (9495364448)
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
    SmsReceiver->>SmsReceiver: Verify sender matches target suffix (9495364448)

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
    actor Caller as 📞 Caller (Redmi Note 10)
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

## Running the server on macOS

The server side also runs on an Apple Silicon Mac (tested on macOS 27). The Linux PipeWire/oFono telephony layer is replaced by `mac/hfp-bridge`, a small Swift helper that connects to the phone as a Bluetooth hands-free unit through Apple's IOBluetooth framework. `server/server.py` starts it automatically and talks to it over stdin/stdout. All Linux code paths are unchanged.

### Setup

1. **Pair the phone** with the Mac (System Settings → Bluetooth), and allow **Calls** for the Mac in the phone's Bluetooth settings for that device.
2. **Build the bridge:**
   ```bash
   cd mac/hfp-bridge && swift build -c release
   ```
3. **Bluetooth permission:** macOS asks the app you launch the server from (Terminal, iTerm, VS Code…). Allow it under System Settings → Privacy & Security → Bluetooth. Without it, the bridge hangs or sees no devices.
4. **Python environment:**
   ```bash
   python3 -m venv .venv-mac
   .venv-mac/bin/pip install -r server/requirements-mac.txt
   ```
5. **Run** (use your phone's Bluetooth address, shown in System Settings → Bluetooth or `system_profiler SPBluetoothDataType`):
   ```bash
   .venv-mac/bin/python server/server.py --bt-mac CC:F9:F0:55:B0:DE
   ```
   Set `HFP_BRIDGE_BIN` to use a bridge binary from another location.
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

Hackathon repository docs: [RULES.md](RULES.md) · [AGENTS.md](AGENTS.md) · [SUBMISSION.md](SUBMISSION.md) · [CHANGELOG.md](CHANGELOG.md) · [AI_USAGE.md](AI_USAGE.md)
