#!/usr/bin/env python3
"""
PipeWire Bluetooth Handsfree Call Monitor & Phone Number Extractor
==================================================================
Extracts phone numbers in real-time when the Bluetooth hands-free audio
device (HFP / mSBC codec shown in Helvum / PipeWire) comes online during a call.

Features:
- Real-time D-Bus event listener for PipeWire Telephony & oFono VoiceCallManager.
- Extracts phone number (LineIdentification), caller name, and call state.
- One-shot check (--once) or continuous live monitor mode.
- Can export caller information to a JSON file (--output).
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

def format_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

class BluetoothCallExtractor:
    def __init__(self, bus, output_file=None):
        self.bus = bus
        self.service_name = "org.pipewire.Telephony"
        self.output_file = output_file
        self.active_calls = {}

    def extract_call_info(self, call_props):
        """Extract number, name, and state from D-Bus call properties dictionary."""
        number = str(call_props.get("LineIdentification", "")).strip()
        name = str(call_props.get("Name", "")).strip()
        state = str(call_props.get("State", "")).strip()
        incoming_line = str(call_props.get("IncomingLine", "")).strip()

        return {
            "number": number,
            "name": name,
            "state": state,
            "incoming_line": incoming_line,
            "timestamp": format_timestamp()
        }

    def save_to_file(self, call_data):
        """Optionally write call info to a JSON file."""
        if self.output_file:
            try:
                with open(self.output_file, "w") as f:
                    json.dump(call_data, f, indent=2)
            except Exception as e:
                print(f"[Warning] Failed to write to {self.output_file}: {e}")

    def print_call_alert(self, call_path, info, event_type="ACTIVE CALL DETECTED"):
        number = info.get("number") or "Unknown / Private Number"
        name = info.get("name") or "N/A"
        state = info.get("state") or "active"

        print("\n" + "=" * 60)
        print(f"[{info['timestamp']}] 📞 {event_type}")
        print("=" * 60)
        print(f"  📱 Phone Number : \033[1;32m{number}\033[0m")
        if name and name != "N/A":
            print(f"  👤 Caller Name  : {name}")
        print(f"  ⚡ Call State   : {state.upper()}")
        print(f"  🔗 D-Bus Path   : {call_path}")
        print("=" * 60 + "\n", flush=True)

        self.save_to_file({
            "event": event_type,
            "path": str(call_path),
            **info
        })

    def check_current_calls(self):
        """Query any active calls currently in progress."""
        found_any = False
        try:
            telephony_obj = self.bus.get_object(self.service_name, "/org/pipewire/Telephony")
            manager = dbus.Interface(telephony_obj, "org.freedesktop.DBus.ObjectManager")
            objects = manager.GetManagedObjects()

            for path, interfaces in objects.items():
                if "org.pipewire.Telephony.Call1" in interfaces:
                    props = interfaces["org.pipewire.Telephony.Call1"]
                    info = self.extract_call_info(props)
                    self.active_calls[path] = info
                    self.print_call_alert(path, info, event_type="CURRENT ONGOING CALL")
                    found_any = True
                elif "org.ofono.VoiceCallManager" in interfaces:
                    ag_obj = self.bus.get_object(self.service_name, path)
                    vcm = dbus.Interface(ag_obj, "org.ofono.VoiceCallManager")
                    calls = vcm.GetCalls()
                    for call_path, call_props in calls.items():
                        info = self.extract_call_info(call_props)
                        self.active_calls[call_path] = info
                        self.print_call_alert(call_path, info, event_type="CURRENT ONGOING CALL")
                        found_any = True

            if not found_any:
                print(f"[{format_timestamp()}] No active calls currently detected.")
        except dbus.DBusException as e:
            print(f"[{format_timestamp()}] Telephony service query notice: {e}")

        return found_any

    def on_call_added(self, path, properties):
        """Triggered immediately when a call begins."""
        info = self.extract_call_info(properties)
        self.active_calls[path] = info
        self.print_call_alert(path, info, event_type="NEW CALL (HANDSFREE ACTIVATED)")

    def on_call_removed(self, path):
        """Triggered when the call terminates."""
        prev = self.active_calls.pop(path, {})
        num = prev.get("number", "Call")
        print(f"[{format_timestamp()}] 📴 Call Ended for: {num} (Path: {path})", flush=True)

    def on_interfaces_added(self, path, interfaces):
        """Triggered by DBus ObjectManager when a Call object appears."""
        if "org.pipewire.Telephony.Call1" in interfaces:
            props = interfaces["org.pipewire.Telephony.Call1"]
            info = self.extract_call_info(props)
            self.active_calls[path] = info
            self.print_call_alert(path, info, event_type="CALL CONNECTED (mSBC AUDIO ACTIVE)")

    def on_interfaces_removed(self, path, interfaces):
        if "org.pipewire.Telephony.Call1" in interfaces:
            self.on_call_removed(path)

    def on_properties_changed(self, interface, changed, invalidated, path=None):
        """Track call state updates (e.g. ringing -> active)."""
        if interface in ("org.pipewire.Telephony.Call1", "org.ofono.VoiceCall"):
            if "LineIdentification" in changed or "State" in changed:
                num = str(changed.get("LineIdentification", ""))
                state = str(changed.get("State", ""))
                print(f"[{format_timestamp()}] 🔄 Call State Changed ({path}): Number='{num}', State='{state}'", flush=True)

def main():
    parser = argparse.ArgumentParser(description="Extract phone numbers from Bluetooth handsfree audio calls in PipeWire/Helvum.")
    parser.add_argument("--once", action="store_true", help="Check for current call once and exit immediately.")
    parser.add_argument("--output", "-o", type=str, default=None, help="File to write extracted caller details (JSON).")
    args = parser.parse_args()

    # Initialize DBus with GLib mainloop for async signals
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()

    extractor = BluetoothCallExtractor(bus, output_file=args.output)

    print("=" * 60)
    print(" 🎧 PipeWire Handsfree Bluetooth Call Extractor")
    print("=" * 60)
    print(f"[{format_timestamp()}] Service: org.pipewire.Telephony")
    print(f"[{format_timestamp()}] Target Node: Bluetooth HFP (mSBC codec)")
    if args.output:
        print(f"[{format_timestamp()}] Output File: {args.output}")
    print("=" * 60 + "\n")

    has_active = extractor.check_current_calls()
    if args.once:
        sys.exit(0 if has_active else 1)

    print(f"[{format_timestamp()}] 📡 Real-time monitoring active. Waiting for call events...\n")

    # 1. Listen for ofono CallAdded / CallRemoved
    bus.add_signal_receiver(
        extractor.on_call_added,
        signal_name="CallAdded",
        dbus_interface="org.ofono.VoiceCallManager",
        bus_name="org.pipewire.Telephony"
    )

    bus.add_signal_receiver(
        extractor.on_call_removed,
        signal_name="CallRemoved",
        dbus_interface="org.ofono.VoiceCallManager",
        bus_name="org.pipewire.Telephony"
    )

    # 2. Listen for DBus ObjectManager interfaces added
    bus.add_signal_receiver(
        extractor.on_interfaces_added,
        signal_name="InterfacesAdded",
        dbus_interface="org.freedesktop.DBus.ObjectManager",
        bus_name="org.pipewire.Telephony"
    )

    bus.add_signal_receiver(
        extractor.on_interfaces_removed,
        signal_name="InterfacesRemoved",
        dbus_interface="org.freedesktop.DBus.ObjectManager",
        bus_name="org.pipewire.Telephony"
    )

    # 3. Listen for property updates
    bus.add_signal_receiver(
        extractor.on_properties_changed,
        signal_name="PropertiesChanged",
        dbus_interface="org.freedesktop.DBus.Properties",
        bus_name="org.pipewire.Telephony",
        path_keyword="path"
    )

    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        print("\nMonitor stopped.")

if __name__ == "__main__":
    main()
