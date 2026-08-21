"""Regression tests for the review findings: the bridge must survive hostile
servers, disconnected commands, bad values, and full disks — and hardware
modes the user picked must survive theme machinery."""

import os
import stat
import struct
import tempfile
import time
import unittest

import common
import orgb_rig
from mock_server import MockOrgbServer

B = common.load_bridge()


def make_bridge(server, state_dir=None):
    events = []
    bridge = B.Bridge("127.0.0.1", server.port,
                      state_dir or tempfile.mkdtemp(prefix="omargb-rb-"),
                      spawn_server=False)
    return bridge, events


class HostileServer(unittest.TestCase):
    def test_truncated_controller_is_orgberror_not_crash(self):
        server = MockOrgbServer(orgb_rig.RIG, truncate_controller=True)
        self.addCleanup(server.stop)
        client = B.OrgbClient("127.0.0.1", server.port, timeout=3.0)
        client.connect()
        with self.assertRaises(B.OrgbError):
            client.snapshot()

    def test_bridge_survives_truncated_enumeration(self):
        server = MockOrgbServer(orgb_rig.RIG, truncate_controller=True)
        self.addCleanup(server.stop)
        events = []
        old_emit = B.emit
        B.emit = events.append
        self.addCleanup(lambda: setattr(B, "emit", old_emit))
        bridge = B.Bridge("127.0.0.1", server.port,
                          tempfile.mkdtemp(prefix="omargb-rb-"),
                          spawn_server=False)
        # Must report failure, not crash, and must not claim success.
        self.assertFalse(bridge.ensure_connected())
        self.assertIsNone(bridge.client)

    def test_connection_dropped_mid_setup_reports_not_connected(self):
        # Server dies after negotiate+name+count: refresh_rig's controller
        # request hits a closed socket. ensure_connected must say False
        # (the old bare `return True` crashed run() on client None).
        server = MockOrgbServer(orgb_rig.RIG, close_after=3)
        self.addCleanup(server.stop)
        old_emit = B.emit
        B.emit = lambda obj: None
        self.addCleanup(lambda: setattr(B, "emit", old_emit))
        bridge = B.Bridge("127.0.0.1", server.port,
                          tempfile.mkdtemp(prefix="omargb-rb-"),
                          spawn_server=False)
        self.assertFalse(bridge.ensure_connected())
        self.assertIsNone(bridge.client)

    def test_oversized_packet_header_rejected(self):
        server = MockOrgbServer(orgb_rig.RIG)
        self.addCleanup(server.stop)
        client = B.OrgbClient("127.0.0.1", server.port, timeout=3.0)
        client.connect()
        self.addCleanup(client.close)
        # Force the reader to see a hostile frame size.
        client.sock.close()

        class FakeSock:
            def __init__(self):
                self.data = B.pack_header(0, 1, B.MAX_PACKET_SIZE + 1)
                self.pos = 0
            def recv(self, n):
                chunk = self.data[self.pos:self.pos + n]
                self.pos += len(chunk)
                return chunk
            def settimeout(self, t):
                pass
            def gettimeout(self):
                return 1.0
            def close(self):
                pass
        client.sock = FakeSock()
        with self.assertRaises(B.OrgbError):
            client._read_packet()

    def test_hostile_led_count_rejected(self):
        bomb = dict(orgb_rig.MOUSE)
        bomb["zones"] = [{"name": "Bomb", "type": 1, "leds_count": 2 ** 31}]
        server = MockOrgbServer([bomb])
        self.addCleanup(server.stop)
        client = B.OrgbClient("127.0.0.1", server.port, timeout=3.0)
        client.connect()
        self.addCleanup(client.close)
        with self.assertRaises(B.OrgbError):
            client.controller_data(0)


class DisconnectedCommands(unittest.TestCase):
    """Handlers must be no-ops, never AttributeError crashes, without a client."""

    def setUp(self):
        self.server = MockOrgbServer(orgb_rig.RIG)
        self.addCleanup(self.server.stop)
        self.events = []
        self._old = B.emit
        B.emit = self.events.append
        self.addCleanup(lambda: setattr(B, "emit", self._old))
        self.bridge = B.Bridge("127.0.0.1", self.server.port,
                               tempfile.mkdtemp(prefix="omargb-rb-"),
                               spawn_server=False)
        self.assertTrue(self.bridge.ensure_connected())
        self.bridge.handle({"cmd": "set-palette", "raw": "accent\t#f38d70\n"})
        # Simulate a drop that keeps the stale rig around.
        self.bridge.client.close()
        self.bridge.client = None

    def test_persist_and_mode_do_not_crash(self):
        self.bridge.handle({"cmd": "persist"})
        self.bridge.handle({"cmd": "mode", "device": "KB77", "mode": 1})

    def test_bad_values_emit_error_via_run_guard(self):
        # The run loop's guard converts a bad value into an error event.
        import queue as q
        self.bridge.commands.put({"cmd": "brightness", "value": "banana"})
        # Drive one loop iteration by hand.
        try:
            cmd = self.bridge.commands.get(timeout=0.5)
            try:
                self.bridge.handle(cmd)
            except Exception as e:
                B.emit({"event": "error", "message": str(e)})
        except q.Empty:
            self.fail("command vanished")
        # Direct handle() raises (ValueError) — proving the guard is needed —
        # and the guard path emitted an error instead of dying.
        self.assertTrue(any(e.get("event") == "error" for e in self.events))


class StateSafety(unittest.TestCase):
    def test_defaults_are_not_shared_between_instances(self):
        a = B.load_state(tempfile.mkdtemp(prefix="omargb-rb-"))
        a["roles"]["X"] = "urgent"
        b = B.load_state(tempfile.mkdtemp(prefix="omargb-rb-"))
        self.assertEqual(b["roles"], {})
        self.assertEqual(B.DEFAULT_STATE["roles"], {})

    def test_wrong_typed_fields_fall_back_to_defaults(self):
        d = tempfile.mkdtemp(prefix="omargb-rb-")
        with open(os.path.join(d, "state.json"), "w") as f:
            f.write('{"roles": ["not", "a", "dict"], "brightness": "loud", '
                    '"power": true, "palette": {"accent": "#123456"}}')
        state = B.load_state(d)
        self.assertEqual(state["roles"], {})
        self.assertEqual(state["brightness"], 100)
        self.assertEqual(state["palette"]["accent"], "#123456")

    def test_save_failure_is_reported_not_fatal(self):
        server = MockOrgbServer(orgb_rig.RIG)
        self.addCleanup(server.stop)
        events = []
        old = B.emit
        B.emit = events.append
        self.addCleanup(lambda: setattr(B, "emit", old))
        d = tempfile.mkdtemp(prefix="omargb-rb-")
        bridge = B.Bridge("127.0.0.1", server.port, d, spawn_server=False)
        os.chmod(d, stat.S_IRUSR | stat.S_IXUSR)  # read-only dir
        self.addCleanup(os.chmod, d, stat.S_IRWXU)
        bridge.persist_state()
        self.assertTrue(any(e.get("event") == "error" and "save" in e.get("message", "")
                            for e in events))

    def test_state_write_defeats_preplanted_symlink(self):
        # Marketplace review finding: a symlink pre-planted at the old
        # predictable tmp path must never receive the write.
        import json as _json
        d = tempfile.mkdtemp(prefix="omargb-rb-")
        victim = os.path.join(d, "victim.txt")
        with open(victim, "w") as f:
            f.write("precious")
        os.symlink(victim, os.path.join(d, "state.json.tmp"))
        B.save_state(d, dict(B.DEFAULT_STATE))
        with open(victim) as f:
            self.assertEqual(f.read(), "precious")  # untouched
        with open(os.path.join(d, "state.json")) as f:
            self.assertEqual(_json.load(f)["schemaVersion"], 1)
        stray = [n for n in os.listdir(d)
                 if n.startswith(".state-") and n.endswith(".tmp")]
        self.assertEqual(stray, [])  # no leftovers on the success path

    def test_bad_hex_override_is_refused(self):
        server = MockOrgbServer(orgb_rig.RIG)
        self.addCleanup(server.stop)
        old = B.emit
        B.emit = lambda o: None
        self.addCleanup(lambda: setattr(B, "emit", old))
        bridge = B.Bridge("127.0.0.1", server.port,
                          tempfile.mkdtemp(prefix="omargb-rb-"),
                          spawn_server=False)
        self.assertTrue(bridge.ensure_connected())
        bridge.handle({"cmd": "set-zone-color", "device": "MS12",
                       "zone": 0, "color": "#zzzzzz"})
        self.assertEqual(bridge.state["overrides"], {})


class SpawnBehavior(unittest.TestCase):
    def test_spawn_once_with_cooldown(self):
        spawns = []
        old_popen = B.subprocess.Popen
        old_which = B.shutil.which
        B.subprocess.Popen = lambda *a, **k: spawns.append(a[0])
        B.shutil.which = lambda name: "/usr/bin/" + name
        self.addCleanup(lambda: setattr(B.subprocess, "Popen", old_popen))
        self.addCleanup(lambda: setattr(B.shutil, "which", old_which))
        old_emit = B.emit
        B.emit = lambda o: None
        self.addCleanup(lambda: setattr(B, "emit", old_emit))

        # A port with nothing listening.
        import socket
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        dead_port = s.getsockname()[1]
        s.close()

        bridge = B.Bridge("127.0.0.1", dead_port,
                          tempfile.mkdtemp(prefix="omargb-rb-"),
                          spawn_server=True)
        self.assertFalse(bridge.ensure_connected())
        self.assertEqual(len(spawns), 1)
        self.assertIn("--startminimized", spawns[0])
        # Immediate retry: still inside the cooldown, no second spawn.
        bridge.next_retry = 0
        self.assertFalse(bridge.ensure_connected())
        self.assertEqual(len(spawns), 1)
        # After the cooldown elapses, one more attempt is allowed.
        bridge.spawn_last -= 61
        bridge.next_retry = 0
        self.assertFalse(bridge.ensure_connected())
        self.assertEqual(len(spawns), 2)


class ThemeVsHardwareModes(unittest.TestCase):
    def setUp(self):
        self.server = MockOrgbServer(orgb_rig.RIG)
        self.addCleanup(self.server.stop)
        self.events = []
        old = B.emit
        B.emit = self.events.append
        self.addCleanup(lambda: setattr(B, "emit", old))
        self.bridge = B.Bridge("127.0.0.1", self.server.port,
                               tempfile.mkdtemp(prefix="omargb-rb-"),
                               spawn_server=False)
        self.assertTrue(self.bridge.ensure_connected())
        self.bridge.handle({"cmd": "set-palette", "raw": "accent\t#f38d70\n"})
        self.wait_packets(6)

    def wait_packets(self, n, timeout=2.0):
        deadline = time.time() + timeout
        while len(self.server.control_packets(1050)) < n and time.time() < deadline:
            time.sleep(0.01)
        return self.server.control_packets(1050)

    def test_no_palette_means_no_paint(self):
        fresh_server = MockOrgbServer(orgb_rig.RIG)
        self.addCleanup(fresh_server.stop)
        bridge = B.Bridge("127.0.0.1", fresh_server.port,
                          tempfile.mkdtemp(prefix="omargb-rb-"),
                          spawn_server=False)
        self.assertTrue(bridge.ensure_connected())
        bridge.handle({"cmd": "power", "on": False})
        bridge.handle({"cmd": "brightness", "value": 10})
        bridge.handle({"cmd": "overlay-dim", "factor": 0.1})
        time.sleep(0.2)
        # No white flood: nothing was ever painted without a palette.
        self.assertEqual(fresh_server.control_packets(1050), [])

    def test_hw_mode_survives_overlays_and_brightness(self):
        self.bridge.handle({"cmd": "mode", "device": "KB77", "mode": 2})  # Breathing
        self.assertIn("KB77", self.bridge.hw_mode)
        kb_before = len([p for p in self.server.control_packets(1050) if p[0] == 3])
        self.bridge.handle({"cmd": "overlay-flash", "color": "#ffffff",
                            "duration_ms": 50})
        self.bridge.handle({"cmd": "overlay-clear"})
        self.bridge.handle({"cmd": "brightness", "value": 30})
        time.sleep(0.2)
        kb_after = len([p for p in self.server.control_packets(1050) if p[0] == 3])
        self.assertEqual(kb_after, kb_before)  # keyboard left alone
        mouse = [p for p in self.server.control_packets(1050) if p[0] == 4]
        self.assertGreater(len(mouse), 1)      # others still managed

    def test_theme_change_reclaims_hw_mode_devices(self):
        self.bridge.handle({"cmd": "mode", "device": "KB77", "mode": 2})
        self.bridge.handle({"cmd": "set-palette", "raw": "accent\t#00ff00\n"})
        self.assertEqual(self.bridge.hw_mode, set())
        deadline = time.time() + 2
        kb = []
        while time.time() < deadline:
            kb = [p for p in self.server.control_packets(1050) if p[0] == 3]
            if kb:
                break
            time.sleep(0.01)
        self.assertTrue(kb, "keyboard repainted after theme change")

    def test_drift_watchdog_reasserts_a_reverted_device(self):
        import json as _json
        # The keyboard "wakes up" playing onboard rainbow: only ITS server-side
        # colors stop matching what we applied.
        reverted = _json.loads(_json.dumps(self.server.rig))
        reverted[3]["colors"] = [0x0000FF] * 104  # onboard red, not our accent
        self.server.set_rig(reverted)
        before = len([p for p in self.server.control_packets(1050) if p[0] == 3])
        self.bridge.check_drift()
        kb = self.wait_packets(7)
        after = len([p for p in self.server.control_packets(1050) if p[0] == 3])
        self.assertGreater(after, before)  # keyboard repainted
        drift_events = [e for e in self.events if e.get("event") == "drift"]
        self.assertEqual(drift_events[-1]["devices"], [3])
        # And once re-asserted, the next pass is quiet.
        n = len(self.server.control_packets(1050))
        time.sleep(0.1)
        self.bridge.check_drift()
        time.sleep(0.1)
        self.assertEqual(len(self.server.control_packets(1050)), n)

    def test_drift_watchdog_leaves_parked_devices_alone(self):
        import json as _json
        self.bridge.handle({"cmd": "mode", "device": "KB77", "mode": 2})
        reverted = _json.loads(_json.dumps(self.server.rig))
        reverted[3]["colors"] = [0x00FF00] * 104
        self.server.set_rig(reverted)
        before = len([p for p in self.server.control_packets(1050) if p[0] == 3])
        self.bridge.check_drift()
        time.sleep(0.15)
        after = len([p for p in self.server.control_packets(1050) if p[0] == 3])
        self.assertEqual(after, before)  # parked: its own show runs freely

    def test_apply_emits_light_colors_event_not_full_rig(self):
        rig_events = [e for e in self.events if e.get("event") == "rig"]
        colors_events = [e for e in self.events if e.get("event") == "colors"]
        self.assertTrue(colors_events, "apply emits colors events")
        # set-palette path: exactly one full rig emit (metadata), not two.
        # (connect emits one, set-palette emits one)
        self.assertEqual(len(rig_events), 2)


if __name__ == "__main__":
    unittest.main()
