"""
Local-network discovery (mDNS / Bonjour)
=========================================
Announces the control room on the local network so people can open http://<name>.local:<port>
instead of an IP address that changes, and so service browsers list it as "Kaaka Control Room".

Uses the system's own tools, no Python packages: `dns-sd` on macOS (built in) and `avahi-publish`
on Linux (package avahi-utils). Every CHECK_SECONDS it re-reads the machine's IP and re-announces
when it changed (for example after joining another Wi-Fi network).
"""

import re
import shutil
import subprocess
import sys
import threading

NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
SERVICE_NAME = "Kaaka Control Room"
CHECK_SECONDS = 30


def valid_name(name) -> bool:
    """A single DNS label: letters, digits and hyphens, not starting or ending with a hyphen."""
    return bool(NAME_RE.match(name or ""))


def announce_commands(platform, name, port, ip):
    """The commands that publish <name>.local -> ip and the _http._tcp service, or None if unsupported."""
    host = f"{name}.local"
    if platform == "darwin":
        # -P proxies a registration: one process publishes both the host record and the service.
        return [["dns-sd", "-P", SERVICE_NAME, "_http._tcp", "local", str(port), host, ip, "path=/"]]
    if platform.startswith("linux"):
        return [["avahi-publish", "-a", "-R", host, ip],
                ["avahi-publish", "-s", "-H", host, SERVICE_NAME, "_http._tcp", str(port), "path=/"]]
    return None


class MdnsAnnouncer:
    def __init__(self, name, port, get_ip, log=print, platform=sys.platform):
        self.name, self.port, self.get_ip, self.log, self.platform = name, port, get_ip, log, platform
        self.procs = []
        self.ip = None
        self.stop_event = threading.Event()
        self.thread = None

    @property
    def url(self):
        return f"http://{self.name}.local:{self.port}"

    def start(self) -> bool:
        """Starts announcing in a background thread; False (with a logged reason) when it cannot."""
        cmds = announce_commands(self.platform, self.name, self.port, "0.0.0.0")
        if cmds is None:
            self.log(f"Local-network name off: mDNS announcing is not supported on {self.platform}.")
            return False
        missing = sorted({c[0] for c in cmds if not shutil.which(c[0])})
        if missing:
            hint = " (install avahi-utils)" if "avahi-publish" in missing else ""
            self.log(f"Local-network name off: {', '.join(missing)} not found{hint}.")
            return False
        self.thread = threading.Thread(target=self._run, name="mdns", daemon=True)
        self.thread.start()
        return True

    def _run(self):
        while not self.stop_event.is_set():
            ip = self.get_ip()
            alive = self.procs and all(p.poll() is None for p in self.procs)
            if ip and not ip.startswith("127.") and (ip != self.ip or not alive):
                self._stop_procs()
                try:
                    self.procs = [subprocess.Popen(c, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                  for c in announce_commands(self.platform, self.name, self.port, ip)]
                    if ip != self.ip:
                        self.log(f"Announced on the local network: {self.url} -> {ip}")
                    self.ip = ip
                except OSError as e:
                    self.log(f"Local-network name failed: {e}")
                    return
            self.stop_event.wait(CHECK_SECONDS)

    def _stop_procs(self):
        for p in self.procs:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    p.kill()
        self.procs = []

    def stop(self):
        self.stop_event.set()
        self._stop_procs()
