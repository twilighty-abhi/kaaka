#!/usr/bin/env python3
"""
SMS "network" between two Android emulators (for demos and tests).

Emulator instances on one Mac cannot text or call each other, so this relay polls each emulator's
sent SMS and delivers every new message to the emulator it was addressed to, unchanged, through the
emulator console (`adb emu sms send <from> <text>`). Calls are simulated separately with
`adb -s <gateway> emu gsm call <caller-number>`.

Emulator numbers follow the console port: emulator-5554 is 15555215554, emulator-5556 is 15555215556.

Usage: python3 scripts/emulator-network.py emulator-5554 emulator-5556 [seconds]
"""
import subprocess
import sys
import time


def adb(serial, *args):
    return subprocess.run(["adb", "-s", serial, *args], capture_output=True, text=True).stdout


def number_of(serial):
    return "1555521" + serial.split("-")[1]


def sent_ids(serial):
    out = adb(serial, "shell", "content query --uri content://sms/sent --projection _id")
    return sorted(int(line.split("_id=")[1]) for line in out.splitlines() if "_id=" in line)


def sent_field(serial, msg_id, field):
    out = adb(serial, "shell", f"content query --uri content://sms/sent --projection {field} --where _id={msg_id}")
    marker = f"{field}="
    return out.split(marker, 1)[1].rstrip("\n") if marker in out else ""


def main():
    serials = sys.argv[1:3]
    duration = float(sys.argv[3]) if len(sys.argv) > 3 else 3600
    by_number = {number_of(s)[-4:]: s for s in serials}
    seen = {s: max(sent_ids(s), default=0) for s in serials}
    print(f"relay up: {', '.join(f'{s}={number_of(s)}' for s in serials)}", flush=True)
    end = time.time() + duration
    while time.time() < end:
        for src in serials:
            for msg_id in (i for i in sent_ids(src) if i > seen[src]):
                seen[src] = msg_id
                address = sent_field(src, msg_id, "address")
                body = sent_field(src, msg_id, "body")
                target = by_number.get("".join(ch for ch in address if ch.isdigit())[-4:])
                if not target or target == src:
                    print(f"skip {src} -> {address} (not an emulator in this relay)", flush=True)
                    continue
                escaped = body.replace("\\", "\\\\").replace("\n", "\\n")
                adb(target, "emu", "sms", "send", number_of(src), escaped)
                print(f"{time.strftime('%H:%M:%S')} {number_of(src)} -> {number_of(target)}: {body.splitlines()[0][:60]}", flush=True)
        time.sleep(1)


if __name__ == "__main__":
    main()
