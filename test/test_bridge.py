"""Protocol tests: the bridge's client against the independent mock server."""

import struct
import time
import unittest

import common
import orgb_rig
from mock_server import MockOrgbServer

B = common.load_bridge()


class WireFormat(unittest.TestCase):
    """Golden bytes computed by hand from the SDK spec."""

    def test_header_bytes(self):
        self.assertEqual(
            B.pack_header(3, 1050, 8),
            b"ORGB" + struct.pack("<III", 3, 1050, 8))

    def test_rgbcolor_encoding(self):
        # RGBColor is (b<<16)|(g<<8)|r -> bytes r,g,b,0 on the wire.
        v = B.color_to_wire("#0a1b2c")
        self.assertEqual(v, (0x2C << 16) | (0x1B << 8) | 0x0A)
        self.assertEqual(struct.pack("<I", v), bytes([0x0A, 0x1B, 0x2C, 0x00]))
        self.assertEqual(B.wire_to_color(v), "#0a1b2c")

    def test_string_packing(self):
        # u16 length INCLUDING the null, then bytes, then null.
        self.assertEqual(B.pack_string("Hi"), b"\x03\x00Hi\x00")

    def test_scale_color(self):
        self.assertEqual(B.scale_color("#ffffff", 0.5), "#808080")
        self.assertEqual(B.scale_color("#000000", 0.5), "#000000")
        self.assertEqual(B.scale_color("#ff0000", 0.0), "#000000")
        self.assertEqual(B.scale_color("#123456", 1.0), "#123456")


class ClientAgainstMock(unittest.TestCase):
    def setUp(self):
        self.server = MockOrgbServer(orgb_rig.RIG)
        self.addCleanup(self.server.stop)
        self.client = B.OrgbClient("127.0.0.1", self.server.port, timeout=3.0)
        self.client.connect()
        self.addCleanup(self.client.close)

    def test_negotiates_protocol_5_and_names_itself(self):
        self.assertEqual(self.client.protocol, 5)
        deadline = time.time() + 2
        while self.server.client_name is None and time.time() < deadline:
            time.sleep(0.01)
        self.assertEqual(self.server.client_name, "OmaRGB")

    def test_enumerates_the_rig_exactly(self):
        rig = self.client.snapshot()
        self.assertEqual(len(rig), 6)
        self.assertEqual([d["name"] for d in rig],
                         [d["name"] for d in orgb_rig.RIG])
        self.assertEqual(rig[0]["type"], 0)
        self.assertEqual(len(rig[0]["zones"]), 3)
        self.assertEqual(rig[0]["zones"][1]["leds_count"], 12)
        self.assertEqual(rig[5]["type"], 3)  # cooler
        self.assertEqual([m["name"] for m in rig[0]["modes"]],
                         ["Direct", "Static", "Breathing", "Off"])

    def test_keyboard_matrix_parses_with_gaps(self):
        rig = self.client.snapshot()
        kb = rig[3]
        matrix = kb["zones"][0]["matrix"]
        self.assertEqual((matrix["height"], matrix["width"]), (6, 21))
        self.assertEqual(len(matrix["map"]), 126)
        self.assertIn(B.MATRIX_EMPTY, matrix["map"])
        real = [c for c in matrix["map"] if c != B.MATRIX_EMPTY]
        self.assertEqual(len(real), 104)
        self.assertEqual(sorted(real), list(range(104)))

    def test_update_leds_sends_golden_bytes(self):
        colors = [B.color_to_wire("#ff0000")] * 2
        self.client.update_leds(4, colors)
        deadline = time.time() + 2
        while not self.server.control_packets(1050) and time.time() < deadline:
            time.sleep(0.01)
        packets = self.server.control_packets(1050)
        self.assertEqual(len(packets), 1)
        dev_id, _, payload = packets[0]
        self.assertEqual(dev_id, 4)
        body = struct.pack("<H", 2) + struct.pack("<I", 0x0000FF) * 2
        self.assertEqual(payload, struct.pack("<I", 4 + len(body)) + body)

    def test_update_zone_leds_layout(self):
        self.client.update_zone_leds(0, 1, [B.color_to_wire("#00ff00")] * 12)
        deadline = time.time() + 2
        while not self.server.control_packets(1051) and time.time() < deadline:
            time.sleep(0.01)
        dev_id, _, payload = self.server.control_packets(1051)[0]
        self.assertEqual(dev_id, 0)
        (size,) = struct.unpack("<I", payload[:4])
        self.assertEqual(size, len(payload))
        zone_idx, count = struct.unpack("<IH", payload[4:10])
        self.assertEqual((zone_idx, count), (1, 12))

    def test_profiles_roundtrip(self):
        self.assertEqual(self.client.profile_list(), ["default"])
        self.client.profile_save("gaming")
        deadline = time.time() + 2
        while "gaming" not in self.server.profiles and time.time() < deadline:
            time.sleep(0.01)
        self.assertIn("gaming", self.client.profile_list())

    def test_device_list_push_sets_dirty(self):
        self.client.snapshot()
        self.server.push_device_list_updated()
        deadline = time.time() + 2
        while not self.client.rig_dirty and time.time() < deadline:
            self.client.poll_push()
            time.sleep(0.01)
        self.assertTrue(self.client.rig_dirty)


class DowngradedServers(unittest.TestCase):
    def test_protocol_3_server_parses(self):
        server = MockOrgbServer(orgb_rig.RIG, protocol=3)
        self.addCleanup(server.stop)
        client = B.OrgbClient("127.0.0.1", server.port, timeout=3.0)
        client.connect()
        self.addCleanup(client.close)
        self.assertEqual(client.protocol, 3)
        rig = client.snapshot()
        self.assertEqual(len(rig), 6)
        matrix = rig[3]["zones"][0]["matrix"]
        self.assertEqual((matrix["height"], matrix["width"]), (6, 21))
        self.assertNotIn("flags", rig[0]["zones"][0])

    def test_silent_version_reply_falls_back_to_v0(self):
        server = MockOrgbServer(orgb_rig.RIG, protocol=0, mute_version=True)
        self.addCleanup(server.stop)
        client = B.OrgbClient("127.0.0.1", server.port, timeout=3.0)
        client.connect()
        self.addCleanup(client.close)
        self.assertEqual(client.protocol, 0)
        rig = client.snapshot()
        self.assertEqual(len(rig), 6)
        self.assertEqual(rig[0]["vendor"], "")  # v0 has no vendor field

    def test_empty_rig_is_a_state_not_an_error(self):
        server = MockOrgbServer([])
        self.addCleanup(server.stop)
        client = B.OrgbClient("127.0.0.1", server.port, timeout=3.0)
        client.connect()
        self.addCleanup(client.close)
        self.assertEqual(client.snapshot(), [])


class BridgeIntegration(unittest.TestCase):
    """The Bridge orchestration layer against the mock, no stdio involved."""

    def setUp(self):
        self.server = MockOrgbServer(orgb_rig.RIG)
        self.addCleanup(self.server.stop)
        self.events = []
        self._old_emit = B.emit
        B.emit = self.events.append
        self.addCleanup(self._restore_emit)
        import tempfile
        self.state_dir = tempfile.mkdtemp(prefix="omargb-test-")
        self.bridge = B.Bridge("127.0.0.1", self.server.port,
                               self.state_dir, spawn_server=False)
        self.assertTrue(self.bridge.ensure_connected())

    def _restore_emit(self):
        B.emit = self._old_emit

    def events_named(self, name):
        return [e for e in self.events if e.get("event") == name]

    def wait_packets(self, pkt_id, n, timeout=2.0):
        """The mock's reader thread consumes TCP asynchronously; wait for it."""
        deadline = time.time() + timeout
        while len(self.server.control_packets(pkt_id)) < n and time.time() < deadline:
            time.sleep(0.01)
        return self.server.control_packets(pkt_id)

    def test_connect_emits_rig(self):
        rigs = self.events_named("rig")
        self.assertEqual(len(rigs), 1)
        devices = rigs[0]["devices"]
        self.assertEqual(len(devices), 6)
        self.assertEqual(devices[3]["typeName"], "keyboard")
        self.assertEqual(devices[3]["zones"][0]["matrix"]["height"], 6)

    def test_palette_apply_paints_every_device_accent(self):
        self.bridge.handle({"cmd": "set-palette",
                            "raw": "accent\t#f38d70\nurgent\t#a55555\n"})
        packets = self.wait_packets(1050, 6)
        self.assertEqual(len(packets), 6)  # one UpdateLEDs per device
        custom = self.wait_packets(1100, 6)
        self.assertEqual(len(custom), 6)   # each switched to Direct once
        # Mouse (index 4): 2 LEDs, both accent.
        mouse = [p for p in packets if p[0] == 4][0]
        body = mouse[2][4:]
        (count,) = struct.unpack("<H", body[:2])
        self.assertEqual(count, 2)
        (first,) = struct.unpack("<I", body[2:6])
        self.assertEqual(B.wire_to_color(first), "#f38d70")

    def test_identical_palette_is_a_no_op(self):
        self.bridge.handle({"cmd": "set-palette", "raw": "accent\t#f38d70\n"})
        first = len(self.wait_packets(1050, 6))
        self.bridge.handle({"cmd": "set-palette", "raw": "accent\t#f38d70\n"})
        time.sleep(0.15)
        self.assertEqual(len(self.server.control_packets(1050)), first)

    def test_brightness_scales_and_power_blacks_out(self):
        self.bridge.handle({"cmd": "set-palette", "raw": "accent\t#ff0000\n"})
        self.bridge.handle({"cmd": "brightness", "value": 50})
        packets = self.wait_packets(1050, 12)
        mouse = [p for p in packets if p[0] == 4][-1]
        (first,) = struct.unpack("<I", mouse[2][6:10])
        self.assertEqual(B.wire_to_color(first), "#800000")
        self.bridge.handle({"cmd": "power", "on": False})
        mouse = [p for p in self.wait_packets(1050, 18) if p[0] == 4][-1]
        (first,) = struct.unpack("<I", mouse[2][6:10])
        self.assertEqual(B.wire_to_color(first), "#000000")

    def test_zone_override_wins_and_clears(self):
        self.bridge.handle({"cmd": "set-palette", "raw": "accent\t#00ff00\n"})
        self.bridge.handle({"cmd": "set-zone-color", "device": "MS12",
                            "zone": 0, "color": "#0000ff"})
        self.wait_packets(1050, 7)
        mouse = [p for p in self.server.control_packets(1050) if p[0] == 4][-1]
        colors = struct.unpack("<II", mouse[2][6:14])
        self.assertEqual([B.wire_to_color(c) for c in colors],
                         ["#0000ff", "#00ff00"])  # logo overridden, wheel accent
        self.bridge.handle({"cmd": "clear-override", "device": "MS12", "zone": 0})
        self.wait_packets(1050, 8)
        mouse = [p for p in self.server.control_packets(1050) if p[0] == 4][-1]
        colors = struct.unpack("<II", mouse[2][6:14])
        self.assertEqual([B.wire_to_color(c) for c in colors],
                         ["#00ff00", "#00ff00"])

    def test_device_list_update_reenumerates(self):
        self.server.set_rig(orgb_rig.RIG[:2])
        self.server.push_device_list_updated()
        deadline = time.time() + 2
        while not self.bridge.client.rig_dirty and time.time() < deadline:
            self.bridge.client.poll_push()
            time.sleep(0.01)
        self.bridge.refresh_rig()
        self.assertEqual(len(self.bridge.rig), 2)

    def test_state_survives_bridge_restart(self):
        self.bridge.handle({"cmd": "set-palette", "raw": "accent\t#f38d70\n"})
        self.bridge.handle({"cmd": "brightness", "value": 40})
        # Settle the wire, then retire the first bridge like a real restart.
        self.wait_packets(1050, 12)
        self.bridge.client.close()
        before = len(self.server.control_packets(1050))
        again = B.Bridge("127.0.0.1", self.server.port,
                         self.state_dir, spawn_server=False)
        self.assertEqual(again.state["brightness"], 40)
        self.assertEqual(again.state["palette"]["accent"], "#f38d70")
        self.assertTrue(again.ensure_connected())
        self.assertIsNotNone(again.client)
        self.addCleanup(again.client.close)
        # Reconnect re-applies the saved look without being asked.
        deadline = time.time() + 2
        while len(self.server.control_packets(1050)) <= before and time.time() < deadline:
            time.sleep(0.01)
        self.assertGreater(len(self.server.control_packets(1050)), before)


if __name__ == "__main__":
    unittest.main()
