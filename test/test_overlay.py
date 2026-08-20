"""Overlay tests: dim/flash are temporary transforms; restore is exact."""

import struct
import tempfile
import time
import unittest

import common
import orgb_rig
from mock_server import MockOrgbServer

B = common.load_bridge()


class OverlayMath(unittest.TestCase):
    def test_dim_scales(self):
        base = {0: ["#ff0000", "#00ff00"]}
        out = B.overlay_targets(base, ("dim", 0.5))
        self.assertEqual(out[0], ["#800000", "#008000"])

    def test_off_is_dim_zero(self):
        base = {0: ["#ff0000"]}
        out = B.overlay_targets(base, ("dim", 0.0))
        self.assertEqual(out[0], ["#000000"])

    def test_flash_replaces_all(self):
        base = {0: ["#ff0000", "#00ff00"], 1: ["#0000ff"]}
        out = B.overlay_targets(base, ("flash", "#a55555"))
        self.assertEqual(out[0], ["#a55555", "#a55555"])
        self.assertEqual(out[1], ["#a55555"])

    def test_none_is_identity(self):
        base = {0: ["#ff0000"]}
        self.assertIs(B.overlay_targets(base, None), base)


class OverlayBridge(unittest.TestCase):
    def setUp(self):
        self.server = MockOrgbServer(orgb_rig.RIG)
        self.addCleanup(self.server.stop)
        self.events = []
        self._old_emit = B.emit
        B.emit = self.events.append
        self.addCleanup(lambda: setattr(B, "emit", self._old_emit))
        self.bridge = B.Bridge("127.0.0.1", self.server.port,
                               tempfile.mkdtemp(prefix="omargb-ov-"),
                               spawn_server=False)
        self.assertTrue(self.bridge.ensure_connected())
        self.bridge.handle({"cmd": "set-palette", "raw": "accent\t#f38d70\n"})
        self.wait_packets(6)

    def wait_packets(self, n, timeout=2.0):
        deadline = time.time() + timeout
        while len(self.server.control_packets(1050)) < n and time.time() < deadline:
            time.sleep(0.01)
        return self.server.control_packets(1050)

    def mouse_first_color(self, packets):
        mouse = [p for p in packets if p[0] == 4][-1]
        (first,) = struct.unpack("<I", mouse[2][6:10])
        return B.wire_to_color(first)

    def test_dim_then_clear_restores_exact_base(self):
        self.bridge.handle({"cmd": "overlay-dim", "factor": 0.25})
        self.assertEqual(self.mouse_first_color(self.wait_packets(12)), "#3d231c")
        self.bridge.handle({"cmd": "overlay-clear"})
        self.assertEqual(self.mouse_first_color(self.wait_packets(18)), "#f38d70")

    def test_lights_off_overlay(self):
        self.bridge.handle({"cmd": "overlay-off"})
        self.assertEqual(self.mouse_first_color(self.wait_packets(12)), "#000000")

    def test_flash_auto_restores_after_duration(self):
        self.bridge.handle({"cmd": "overlay-flash", "color": "#a55555",
                            "duration_ms": 80})
        self.assertEqual(self.mouse_first_color(self.wait_packets(12)), "#a55555")
        # The run loop owns expiry; simulate one tick after the deadline.
        time.sleep(0.12)
        self.assertIsNotNone(self.bridge.flash_until)
        if time.monotonic() >= self.bridge.flash_until:
            self.bridge.overlay = None
            self.bridge.flash_until = None
            self.bridge.apply(force=True)
        self.assertEqual(self.mouse_first_color(self.wait_packets(18)), "#f38d70")

    def test_overlay_atop_overlay_restores_to_base_not_intermediate(self):
        self.bridge.handle({"cmd": "overlay-dim", "factor": 0.25})
        self.wait_packets(12)
        self.bridge.handle({"cmd": "overlay-flash", "color": "#ffffff",
                            "duration_ms": 60})
        self.assertEqual(self.mouse_first_color(self.wait_packets(18)), "#ffffff")
        self.bridge.handle({"cmd": "overlay-clear"})
        self.assertEqual(self.mouse_first_color(self.wait_packets(24)), "#f38d70")

    def test_state_changes_under_overlay_keep_overlay_on_top(self):
        self.bridge.handle({"cmd": "overlay-dim", "factor": 0.0})
        self.wait_packets(12)
        self.bridge.handle({"cmd": "set-palette", "raw": "accent\t#00ff00\n"})
        packets = self.wait_packets(18)
        # Base changed but the overlay keeps the visible state dark.
        self.assertEqual(self.mouse_first_color(packets), "#000000")
        self.bridge.handle({"cmd": "overlay-clear"})
        self.assertEqual(self.mouse_first_color(self.wait_packets(24)), "#00ff00")


if __name__ == "__main__":
    unittest.main()
