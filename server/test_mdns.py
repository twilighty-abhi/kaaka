"""Tests for the local-network announcer's name rules and commands (no network traffic)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mdns  # noqa: E402


class NameTests(unittest.TestCase):
    def test_valid_names(self):
        for name in ("kaaka", "kaaka-kochi", "k1", "a" * 63):
            self.assertTrue(mdns.valid_name(name), name)

    def test_invalid_names(self):
        for name in ("", "-kaaka", "kaaka-", "kaaka.local", "Kaaka Room", "a" * 64, "kaa_ka", None):
            self.assertFalse(mdns.valid_name(name), name)


class CommandTests(unittest.TestCase):
    def test_macos_uses_one_dns_sd_proxy_registration(self):
        cmds = mdns.announce_commands("darwin", "kaaka", 8080, "10.0.0.5")
        self.assertEqual(cmds, [["dns-sd", "-P", "Kaaka Control Room", "_http._tcp", "local", "8080",
                                 "kaaka.local", "10.0.0.5", "path=/"]])

    def test_linux_publishes_address_and_service(self):
        cmds = mdns.announce_commands("linux", "kaaka", 9000, "192.168.1.9")
        self.assertEqual(cmds[0], ["avahi-publish", "-a", "-R", "kaaka.local", "192.168.1.9"])
        self.assertIn("_http._tcp", cmds[1])
        self.assertIn("9000", cmds[1])

    def test_unsupported_platform(self):
        self.assertIsNone(mdns.announce_commands("win32", "kaaka", 8080, "10.0.0.5"))
        logs = []
        self.assertFalse(mdns.MdnsAnnouncer("kaaka", 8080, lambda: "10.0.0.5", log=logs.append, platform="win32").start())
        self.assertIn("not supported", logs[0])

    def test_missing_tool_is_reported(self):
        logs = []
        a = mdns.MdnsAnnouncer("kaaka", 8080, lambda: "10.0.0.5", log=logs.append, platform="linux")
        original = mdns.shutil.which
        mdns.shutil.which = lambda _: None
        try:
            self.assertFalse(a.start())
        finally:
            mdns.shutil.which = original
        self.assertIn("avahi-utils", logs[0])


if __name__ == "__main__":
    unittest.main()
