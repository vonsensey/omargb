"""Mapper tests: palette + roles + overrides -> per-LED targets. Pure logic."""

import unittest

import common
import orgb_rig

B = common.load_bridge()

PALETTE = {"accent": "#f38d70", "background": "#101315", "urgent": "#a55555",
           "foreground": "#cacccc", "red": "#f7768e"}


def rig():
    """The fixture rig in the bridge's parsed shape (subset that matters)."""
    parsed = []
    for dev in orgb_rig.RIG:
        parsed.append({
            "type": dev["type"], "name": dev["name"],
            "serial": dev.get("serial", ""),
            "zones": [{"leds_count": z["leds_count"]} for z in dev["zones"]],
            "leds": dev["leds"],
        })
    return parsed


def state(**kw):
    s = {"power": True, "brightness": 100, "roles": {}, "zone_roles": {},
         "overrides": {}, "palette": dict(PALETTE)}
    s.update(kw)
    return s


class Mapper(unittest.TestCase):
    def test_default_everything_wears_accent(self):
        targets = B.compute_targets(rig(), state())
        self.assertEqual(len(targets), 6)
        for colors in targets.values():
            self.assertTrue(all(c == "#f38d70" for c in colors))
        self.assertEqual(len(targets[3]), 104)  # keyboard: one per LED

    def test_device_role_paints_all_its_zones(self):
        s = state(roles={"CL9": "urgent"})
        targets = B.compute_targets(rig(), s)
        self.assertTrue(all(c == "#a55555" for c in targets[5]))
        self.assertTrue(all(c == "#f38d70" for c in targets[4]))

    def test_zone_role_beats_device_role(self):
        s = state(roles={"MB001": "background"},
                  zone_roles={"MB001": {"1": "red"}})
        targets = B.compute_targets(rig(), s)
        mb = targets[0]
        self.assertEqual(mb[0], "#101315")            # zone 0: device role
        self.assertEqual(mb[1:13], ["#f7768e"] * 12)  # zone 1: zone role
        self.assertEqual(mb[13:], ["#101315"] * 8)    # zone 2: device role

    def test_override_beats_everything(self):
        s = state(zone_roles={"MS12": {"0": "red"}},
                  overrides={"MS12": {"0": "#123456"}})
        targets = B.compute_targets(rig(), s)
        self.assertEqual(targets[4][0], "#123456")

    def test_unknown_role_falls_back_to_accent(self):
        s = state(roles={"KB77": "no-such-role"})
        targets = B.compute_targets(rig(), s)
        self.assertTrue(all(c == "#f38d70" for c in targets[3]))

    def test_palette_without_accent_falls_back_to_white(self):
        s = state(palette={"background": "#000000"})
        targets = B.compute_targets(rig(), s)
        self.assertTrue(all(c == "#ffffff" for c in targets[4]))

    def test_brightness_scales_all(self):
        s = state(brightness=50, palette={"accent": "#ff0000"})
        targets = B.compute_targets(rig(), s)
        self.assertTrue(all(c == "#800000" for c in targets[4]))

    def test_power_off_is_black(self):
        s = state(power=False)
        targets = B.compute_targets(rig(), s)
        for colors in targets.values():
            self.assertTrue(all(c == "#000000" for c in colors))

    def test_device_key_prefers_serial_then_name(self):
        self.assertEqual(B.device_key({"serial": "ABC", "name": "X"}), "ABC")
        self.assertEqual(B.device_key({"serial": "  ", "name": "X"}), "X")
        self.assertEqual(B.device_key({"name": "X"}), "X")


if __name__ == "__main__":
    unittest.main()
