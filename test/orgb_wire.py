"""Server-side ORGB wire serialization for the mock server.

Deliberately written from the SDK spec independently of bin/omargb-bridge:
the bridge's parser is exercised against bytes it did not produce, so a
misreading in one implementation shows up as a test failure instead of
cancelling itself out.
"""

import struct

MAGIC = b"ORGB"


def header(dev_id, pkt_id, size):
    return MAGIC + struct.pack("<III", dev_id, pkt_id, size)


def string(s):
    raw = s.encode("utf-8") + b"\x00"
    return struct.pack("<H", len(raw)) + raw


def mode(m, ver):
    out = string(m["name"])
    out += struct.pack("<i", m.get("value", 0))
    out += struct.pack("<I", m.get("flags", 0))
    out += struct.pack("<II", m.get("speed_min", 0), m.get("speed_max", 0))
    if ver >= 3:
        out += struct.pack("<II", m.get("brightness_min", 0),
                           m.get("brightness_max", 0))
    out += struct.pack("<II", m.get("colors_min", 0), m.get("colors_max", 0))
    out += struct.pack("<I", m.get("speed", 0))
    if ver >= 3:
        out += struct.pack("<I", m.get("brightness", 0))
    out += struct.pack("<II", m.get("direction", 0), m.get("color_mode", 0))
    colors = m.get("colors", [])
    out += struct.pack("<H", len(colors))
    for c in colors:
        out += struct.pack("<I", c)
    return out


def zone(z, ver):
    out = string(z["name"])
    out += struct.pack("<i", z.get("type", 0))
    out += struct.pack("<III", z.get("leds_min", 0), z.get("leds_max", 0),
                       z["leds_count"])
    matrix = z.get("matrix")
    if matrix:
        out += struct.pack("<H", 8 + 4 * len(matrix["map"]))
        out += struct.pack("<II", matrix["height"], matrix["width"])
        for cell in matrix["map"]:
            out += struct.pack("<I", cell)
    else:
        out += struct.pack("<H", 0)
    if ver >= 4:
        segments = z.get("segments", [])
        out += struct.pack("<H", len(segments))
        for seg in segments:
            out += string(seg["name"])
            out += struct.pack("<iII", seg.get("type", 0),
                               seg.get("start_idx", 0), seg["leds_count"])
    if ver >= 5:
        out += struct.pack("<I", z.get("flags", 0))
    return out


def controller(dev, ver):
    body = struct.pack("<i", dev.get("type", 0))
    body += string(dev["name"])
    if ver >= 1:
        body += string(dev.get("vendor", ""))
    body += string(dev.get("description", ""))
    body += string(dev.get("version", ""))
    body += string(dev.get("serial", ""))
    body += string(dev.get("location", ""))
    modes = dev.get("modes", [])
    body += struct.pack("<H", len(modes))
    body += struct.pack("<i", dev.get("active_mode", 0))
    for m in modes:
        body += mode(m, ver)
    zones = dev.get("zones", [])
    body += struct.pack("<H", len(zones))
    for z in zones:
        body += zone(z, ver)
    leds = dev.get("leds", [])
    body += struct.pack("<H", len(leds))
    for led in leds:
        body += string(led["name"])
        body += struct.pack("<I", led.get("value", 0))
    colors = dev.get("colors", [])
    body += struct.pack("<H", len(colors))
    for c in colors:
        body += struct.pack("<I", c)
    return struct.pack("<I", 4 + len(body)) + body
