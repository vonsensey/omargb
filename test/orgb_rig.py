"""The fixture rig: a plausible six-device desktop, defined as plain dicts
in the mock server's own vocabulary (see orgb_wire.controller for the
serialized layout)."""

E = 0xFFFFFFFF  # empty matrix cell


def _mode(name, flags=0, color_mode=0, colors=None):
    return {"name": name, "value": 0, "flags": flags,
            "speed_min": 0, "speed_max": 0, "brightness_min": 0,
            "brightness_max": 100, "colors_min": 0, "colors_max": 0,
            "speed": 0, "brightness": 100, "direction": 0,
            "color_mode": color_mode, "colors": colors or []}


DIRECT = _mode("Direct", flags=(1 << 5), color_mode=1)   # per-LED
STATIC = _mode("Static", flags=(1 << 6), color_mode=2, colors=[0])
BREATHE = _mode("Breathing", flags=(1 << 0) | (1 << 6), color_mode=2, colors=[0])
OFF = _mode("Off")


def _leds(prefix, n):
    return [{"name": "%s %d" % (prefix, i), "value": 0} for i in range(n)]


def keyboard_matrix():
    """6x21 layout with gaps, 104 LEDs."""
    rows, cols, mapping, led = 6, 21, [], 0
    for r in range(rows):
        for c in range(cols):
            skip = (r == 0 and c in (1, 5, 9, 13)) or \
                   (r == 5 and 4 <= c <= 9) or \
                   (r in (1, 2, 3, 4) and c == 20 and r != 1)
            if skip or led >= 104:
                mapping.append(E)
            else:
                mapping.append(led)
                led += 1
    return {"height": rows, "width": cols, "map": mapping}


MOTHERBOARD = {
    "type": 0, "name": "Fixture B550 Motherboard", "vendor": "Fixture",
    "description": "test motherboard", "version": "1.0", "serial": "MB001",
    "location": "I2C: /dev/i2c-0", "active_mode": 0,
    "modes": [DIRECT, STATIC, BREATHE, OFF],
    "zones": [
        {"name": "Onboard LED", "type": 0, "leds_count": 1},
        {"name": "Addressable 1", "type": 1, "leds_count": 12},
        {"name": "Addressable 2", "type": 1, "leds_count": 8},
    ],
    "leds": _leds("MB LED", 21),
    "colors": [0] * 21,
}

DRAM_A = {
    "type": 1, "name": "Fixture DDR4 A", "vendor": "Fixture",
    "description": "ram stick", "version": "", "serial": "",
    "location": "I2C: 0x50", "active_mode": 1,
    "modes": [DIRECT, STATIC, OFF],
    "zones": [{"name": "DRAM", "type": 1, "leds_count": 8}],
    "leds": _leds("DRAM LED", 8),
    "colors": [0] * 8,
}

DRAM_B = dict(DRAM_A, name="Fixture DDR4 B", location="I2C: 0x51")

KEYBOARD = {
    "type": 5, "name": "Fixture RGB Keyboard", "vendor": "Fixture",
    "description": "keyboard", "version": "2.1", "serial": "KB77",
    "location": "HID: /dev/hidraw2", "active_mode": 0,
    "modes": [DIRECT, STATIC, BREATHE],
    "zones": [{"name": "Keys", "type": 2, "leds_count": 104,
               "matrix": keyboard_matrix()}],
    "leds": _leds("Key", 104),
    "colors": [0] * 104,
}

MOUSE = {
    "type": 6, "name": "Fixture Gaming Mouse", "vendor": "Fixture",
    "description": "mouse", "version": "", "serial": "MS12",
    "location": "HID: /dev/hidraw3", "active_mode": 0,
    "modes": [DIRECT, STATIC],
    "zones": [
        {"name": "Logo", "type": 0, "leds_count": 1},
        {"name": "Scroll Wheel", "type": 0, "leds_count": 1},
    ],
    "leds": _leds("Mouse LED", 2),
    "colors": [0] * 2,
}

COOLER = {
    "type": 3, "name": "Fixture AIO Cooler", "vendor": "Fixture",
    "description": "cpu cooler", "version": "", "serial": "CL9",
    "location": "USB: 1a2b:3c4d", "active_mode": 0,
    "modes": [DIRECT, STATIC, BREATHE, OFF],
    "zones": [
        {"name": "Pump", "type": 1, "leds_count": 16},
        {"name": "Fan 1", "type": 1, "leds_count": 8},
        {"name": "Fan 2", "type": 1, "leds_count": 8},
    ],
    "leds": _leds("Cooler LED", 32),
    "colors": [0] * 32,
}

RIG = [MOTHERBOARD, DRAM_A, DRAM_B, KEYBOARD, MOUSE, COOLER]
