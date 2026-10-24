// hfp-bridge — macOS Bluetooth hands-free (HFP HF) bridge for the Kaaka server.
//
// The Mac acts as the hands-free unit, the phone as the audio gateway (IOBluetoothHandsFreeDevice).
// Call control only: SCO audio is refused by macOS (connectSCO -> kIOReturnUnsupported).
//
// Usage: hfp-bridge <bt-address>
// stdout: one JSON event per line. stdin: answer | hangup | status | quit  (EOF = quit)

import Foundation
import IOBluetooth

setvbuf(stdout, nil, _IOLBF, 0)

let isoFormatter: ISO8601DateFormatter = {
    let f = ISO8601DateFormatter()
    f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    return f
}()

func emit(_ event: String, _ fields: [String: Any] = [:]) {
    var obj = fields
    obj["event"] = event
    obj["ts"] = isoFormatter.string(from: Date())
    guard let data = try? JSONSerialization.data(withJSONObject: obj, options: [.withoutEscapingSlashes]),
          let line = String(data: data, encoding: .utf8) else { return }
    print(line)
}

func hex(_ r: IOReturn) -> String { "0x" + String(UInt32(bitPattern: r), radix: 16) }

/// Splits an AT result payload like `"+911234",145,,,"Name"` into fields, honouring quotes.
func atFields(_ s: String) -> [String] {
    var out: [String] = [], cur = "", quoted = false
    for ch in s {
        if ch == "\"" { quoted.toggle() } else if ch == "," && !quoted { out.append(cur); cur = "" } else { cur.append(ch) }
    }
    out.append(cur)
    return out.map { $0.trimmingCharacters(in: .whitespaces) }
}

final class Bridge: NSObject, IOBluetoothHandsFreeDeviceDelegate, IOBluetoothDeviceAsyncCallbacks {
    let device: IOBluetoothDevice
    var hf: IOBluetoothHandsFreeDevice?

    var connected = false
    var attempt = 0          // generation counter; stale callbacks/timeouts check against it
    var retryScheduled = false

    var callActive = false
    var callSetup = 0
    // Incoming-call state
    var incomingPending = false
    var incomingEmitted = false
    var callerNumber = ""
    var callerName = ""

    init(device: IOBluetoothDevice) { self.device = device }

    // MARK: connection / watchdog

    func startAttempt() {
        retryScheduled = false
        attempt += 1
        let gen = attempt
        connected = false
        emit("connecting")
        // Without an open baseband link + fresh SDP, hf.connect() silently does nothing (observed on macOS 27).
        if device.isConnected() {
            querySDP(gen)
        } else {
            let r = device.openConnection(self)
            if r != kIOReturnSuccess {
                emit("log", ["message": "openConnection failed \(hex(r))"])
                scheduleRetry()
                return
            }
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 20) { [self] in
            if gen == attempt && !connected {
                emit("log", ["message": "no HFP connected callback within 20s; retrying"])
                hf?.disconnect()
                scheduleRetry()
            }
        }
    }

    func scheduleRetry() {
        guard !retryScheduled else { return }
        retryScheduled = true
        attempt += 1 // invalidate in-flight attempt
        DispatchQueue.main.asyncAfter(deadline: .now() + 5) { [self] in startAttempt() }
    }

    func querySDP(_ gen: Int) {
        let r = device.performSDPQuery(self)
        if r != kIOReturnSuccess {
            emit("log", ["message": "performSDPQuery failed \(hex(r)); trying HFP connect anyway"])
            connectHF(gen)
        }
    }

    func connectHF(_ gen: Int) {
        guard gen == attempt else { return }
        if device.handsFreeAudioGatewayServiceRecord() == nil {
            emit("log", ["message": "no Handsfree Gateway SDP record on device; trying anyway"])
        }
        hf?.delegate = nil
        guard let h = IOBluetoothHandsFreeDevice(device: device, delegate: self) else {
            emit("error", ["message": "IOBluetoothHandsFreeDevice init returned nil"])
            scheduleRetry()
            return
        }
        // HF features: EC/NR 0x1, CLI presentation 0x4, remote volume 0x10, enhanced call status 0x20
        h.supportedFeatures = 0x1 | 0x4 | 0x10 | 0x20
        hf = h
        // A connect() issued in the same run-loop pass as the first IOBluetoothHandsFreeDevice
        // init is silently dropped (no callback); give IOBluetooth a moment to set up first.
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) { [self] in
            guard gen == attempt, hf === h else { return }
            emit("log", ["message": "HFP connect issued (attempt \(gen))"])
            h.connect()
        }
    }

    // IOBluetoothDeviceAsyncCallbacks
    func remoteNameRequestComplete(_ device: IOBluetoothDevice!, status: IOReturn) {}
    func connectionComplete(_ device: IOBluetoothDevice!, status: IOReturn) {
        let gen = attempt
        if status != kIOReturnSuccess {
            emit("log", ["message": "baseband connection failed \(hex(status))"])
            scheduleRetry()
            return
        }
        emit("log", ["message": "baseband connected"])
        querySDP(gen)
    }
    func sdpQueryComplete(_ device: IOBluetoothDevice!, status: IOReturn) {
        emit("log", ["message": "SDP query complete \(hex(status))"])
        connectHF(attempt)
    }

    // MARK: IOBluetoothHandsFreeDelegate

    func handsFree(_ device: IOBluetoothHandsFree!, connected status: NSNumber!) {
        guard status.int32Value == kIOReturnSuccess else {
            emit("log", ["message": "HFP connect failed status \(status!)"])
            scheduleRetry()
            return
        }
        connected = true
        emit("connected", ["ag_features": Int(hf?.deviceSupportedFeatures ?? 0)])
        hf?.send(atCommand: "AT+CLIP=1") // make sure caller-ID (+CLIP) is delivered
    }

    func handsFree(_ device: IOBluetoothHandsFree!, disconnected status: NSNumber!) {
        let wasConnected = connected
        connected = false
        if wasConnected || status.int32Value != kIOReturnSuccess {
            emit("disconnected", ["status": status.intValue])
        }
        if callActive || incomingPending { callActive = false; finishCall() }
        scheduleRetry()
    }

    func handsFree(_ device: IOBluetoothHandsFree!, scoConnectionOpened status: NSNumber!) {
        emit("log", ["message": "SCO opened status \(status!)"])
    }
    func handsFree(_ device: IOBluetoothHandsFree!, scoConnectionClosed status: NSNumber!) {
        emit("log", ["message": "SCO closed status \(status!)"])
    }

    // MARK: IOBluetoothHandsFreeDeviceDelegate

    func indicator(_ name: String, _ v: NSNumber) { emit("indicator", ["name": name, "value": v.intValue]) }

    func handsFree(_ device: IOBluetoothHandsFreeDevice!, isServiceAvailable v: NSNumber!) { indicator("service", v) }
    func handsFree(_ device: IOBluetoothHandsFreeDevice!, callHoldState v: NSNumber!) { indicator("callheld", v) }
    func handsFree(_ device: IOBluetoothHandsFreeDevice!, signalStrength v: NSNumber!) { indicator("signal", v) }
    func handsFree(_ device: IOBluetoothHandsFreeDevice!, isRoaming v: NSNumber!) { indicator("roam", v) }
    func handsFree(_ device: IOBluetoothHandsFreeDevice!, batteryCharge v: NSNumber!) { indicator("battchg", v) }

    func handsFree(_ device: IOBluetoothHandsFreeDevice!, isCallActive v: NSNumber!) {
        indicator("call", v)
        let active = v.intValue == 1
        if active && !callActive {
            callActive = true
            emit("call_active")
        } else if !active && callActive {
            callActive = false
            finishCall()
        }
    }

    func handsFree(_ device: IOBluetoothHandsFreeDevice!, callSetupMode v: NSNumber!) {
        indicator("callsetup", v)
        callSetup = v.intValue
        if callSetup == 1 && !incomingPending {
            incomingPending = true
            incomingEmitted = false
            callerNumber = ""
            callerName = ""
            hf?.currentCallList() // AT+CLCC -> currentCall: / +CLCC result
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) { [self] in emitIncoming() }
        } else if callSetup == 0 && incomingPending && !callActive {
            // Setup ended: either answered (call=1 arrives around now) or rejected/missed.
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { [self] in
                if incomingPending && !callActive && callSetup == 0 { finishCall() }
            }
        }
    }

    func handsFree(_ device: IOBluetoothHandsFreeDevice!, incomingCallFrom number: String!) {
        gotCaller(number: number ?? "", name: "")
    }

    func handsFree(_ device: IOBluetoothHandsFreeDevice!, ringAttempt v: NSNumber!) {
        emit("log", ["message": "RING \(v!)"])
    }

    func handsFree(_ device: IOBluetoothHandsFreeDevice!, currentCall: [AnyHashable: Any]!) {
        guard let c = currentCall else { return }
        let dir = (c[IOBluetoothHandsFreeCallDirection] as? NSNumber)?.intValue
        let stat = (c[IOBluetoothHandsFreeCallStatus] as? NSNumber)?.intValue
        if dir == 1 || stat == 4 || stat == 5 {
            gotCaller(number: c[IOBluetoothHandsFreeCallNumber] as? String ?? "",
                      name: c[IOBluetoothHandsFreeCallName] as? String ?? "")
        }
    }

    func handsFree(_ device: IOBluetoothHandsFreeDevice!, subscriberNumber: String!) {}
    func handsFree(_ device: IOBluetoothHandsFreeDevice!, incomingSMS sms: [AnyHashable: Any]!) {}

    func handsFree(_ device: IOBluetoothHandsFreeDevice!, unhandledResultCode code: String!) {
        let line = (code ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        if line.hasPrefix("+CLIP:") {
            let f = atFields(String(line.dropFirst(6)))
            gotCaller(number: f.first ?? "", name: f.count > 4 ? f[4] : "")
        } else if line.hasPrefix("+CLCC:") {
            // +CLCC: idx,dir,stat,mode,mpty,"number",type[,"alpha"]
            let f = atFields(String(line.dropFirst(6)))
            if f.count >= 6, f[1] == "1" || f[2] == "4" || f[2] == "5" {
                gotCaller(number: f[5], name: f.count > 7 ? f[7] : "")
            }
        } else {
            emit("log", ["message": "unhandled result: \(line)"])
        }
    }

    // MARK: call bookkeeping

    func gotCaller(number: String, name: String) {
        if !number.isEmpty && callerNumber.isEmpty { callerNumber = number }
        if !name.isEmpty && callerName.isEmpty { callerName = name }
        if incomingPending && !callerNumber.isEmpty { emitIncoming() }
    }

    func emitIncoming() {
        guard incomingPending && !incomingEmitted else { return }
        incomingEmitted = true
        emit("incoming_call", ["number": callerNumber, "name": callerName])
    }

    func finishCall() {
        if incomingPending && !incomingEmitted { emitIncoming() }
        incomingPending = false
        incomingEmitted = false
        callerNumber = ""
        callerName = ""
        emit("call_ended")
    }

    // MARK: commands

    func command(_ raw: String) {
        let cmd = raw.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        switch cmd {
        case "": break
        case "answer":
            guard let hf, connected else { emit("error", ["message": "answer: HFP not connected"]); return }
            hf.acceptCall()
            emit("log", ["message": "acceptCall sent"])
        case "hangup":
            guard let hf, connected else { emit("error", ["message": "hangup: HFP not connected"]); return }
            hf.endCall()
            emit("log", ["message": "endCall sent"])
        case "status":
            emit("state", ["connected": connected, "baseband": device.isConnected(),
                           "call_active": callActive, "call_setup": callSetup])
        case "quit":
            hf?.disconnect()
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) { exit(0) }
        default:
            emit("error", ["message": "unknown command: \(cmd)"])
        }
    }
}

// MARK: main

let args = CommandLine.arguments
guard args.count == 2 else {
    FileHandle.standardError.write("usage: hfp-bridge <bt-address>\n".data(using: .utf8)!)
    exit(2)
}
let address = args[1].lowercased().replacingOccurrences(of: ":", with: "-")
let paired = (IOBluetoothDevice.pairedDevices() as? [IOBluetoothDevice]) ?? []
guard let device = paired.first(where: { $0.addressString?.lowercased() == address })
        ?? IOBluetoothDevice(addressString: address) else {
    emit("error", ["message": "invalid Bluetooth address: \(args[1])"])
    exit(2)
}
if !device.isPaired() { emit("log", ["message": "device \(args[1]) is not paired with this Mac"]) }

let bridge = Bridge(device: device)
signal(SIGPIPE, SIG_IGN)
signal(SIGINT, SIG_IGN)
signal(SIGTERM, SIG_IGN)
var signalSources: [DispatchSourceSignal] = []
for sig in [SIGINT, SIGTERM] {
    let src = DispatchSource.makeSignalSource(signal: sig, queue: .main)
    src.setEventHandler { bridge.command("quit") }
    src.resume()
    signalSources.append(src)
}

Thread.detachNewThread {
    while let line = readLine() {
        DispatchQueue.main.async { bridge.command(line) }
    }
    DispatchQueue.main.async { bridge.command("quit") } // EOF: parent went away
}

emit("log", ["message": "hfp-bridge starting for \((device.name ?? "").isEmpty ? args[1] : device.name!) (\(address))"])
bridge.startAttempt()
RunLoop.main.run()
