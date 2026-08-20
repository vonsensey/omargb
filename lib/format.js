// Pure helpers shared by the widget and panel. No Quickshell imports so the
// whole file is probeable with plain qml6 (see test/probe_format.mjs).
.pragma library

// QML colors stringify as #aarrggbb when they carry alpha; the bridge and
// the OpenRGB wire want plain #rrggbb.
function hex6(c) {
  var s = String(c);
  if (s.length === 9 && s[0] === "#") return "#" + s.slice(3);
  return s;
}

// Settings arrive from the bar layout as strings; coerce safely.
function isOn(value, fallbackOn) {
  if (value === undefined || value === null || value === "")
    return fallbackOn;
  return String(value) === "On";
}

// Connection state -> short label for the widget tooltip and panel header.
function statusLabel(bridgeUp, serverUp, openrgbMissing, deviceCount) {
  if (!bridgeUp) return "starting";
  // A live server outranks a missing binary: the rig is real either way
  // (someone may run the SDK server remotely or from a build).
  if (serverUp) {
    if (deviceCount === 0) return "no devices";
    return deviceCount + (deviceCount === 1 ? " device" : " devices");
  }
  if (openrgbMissing) return "needs OpenRGB";
  return "connecting";
}

// Doctor summary: worst status wins the badge.
function doctorBadge(checks) {
  var worst = "ok";
  for (var i = 0; i < (checks || []).length; i++) {
    var s = checks[i].status;
    if (s === "fail") return "fail";
    if (s === "warn") worst = "warn";
  }
  return worst;
}

// hsv (0..1 each) -> "#rrggbb". Used by the color picker.
function hsvToHex(h, s, v) {
  var r, g, b;
  var i = Math.floor(h * 6) % 6;
  var f = h * 6 - Math.floor(h * 6);
  var p = v * (1 - s), q = v * (1 - f * s), t = v * (1 - (1 - f) * s);
  switch (i) {
    case 0: r = v; g = t; b = p; break;
    case 1: r = q; g = v; b = p; break;
    case 2: r = p; g = v; b = t; break;
    case 3: r = p; g = q; b = v; break;
    case 4: r = t; g = p; b = v; break;
    default: r = v; g = p; b = q; break;
  }
  function cc(x) {
    var n = Math.round(x * 255);
    n = Math.max(0, Math.min(255, n));
    return (n < 16 ? "0" : "") + n.toString(16);
  }
  return "#" + cc(r) + cc(g) + cc(b);
}

// "#rrggbb" -> {h, s, v} each 0..1. Inverse of hsvToHex.
function hexToHsv(hex) {
  var s6 = hex6(hex).slice(1);
  var r = parseInt(s6.slice(0, 2), 16) / 255;
  var g = parseInt(s6.slice(2, 4), 16) / 255;
  var b = parseInt(s6.slice(4, 6), 16) / 255;
  var max = Math.max(r, g, b), min = Math.min(r, g, b);
  var d = max - min;
  var h = 0;
  if (d > 0) {
    if (max === r) h = ((g - b) / d) % 6;
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h /= 6;
    if (h < 0) h += 1;
  }
  return { h: h, s: max === 0 ? 0 : d / max, v: max };
}

// First LED index of a zone: zones are laid out consecutively in the
// device's flat color array.
function zoneStart(zones, zoneIdx) {
  var start = 0;
  for (var i = 0; i < zoneIdx && i < zones.length; i++)
    start += Number(zones[i].ledsCount) || 0;
  return start;
}

// LED index -> {row, col} in a matrix map, or null. The map is row-major
// with 0xFFFFFFFF (4294967295) marking empty cells.
function matrixCell(matrix, ledIndex) {
  if (!matrix || !matrix.map) return null;
  for (var i = 0; i < matrix.map.length; i++) {
    if (matrix.map[i] === ledIndex)
      return { row: Math.floor(i / matrix.width), col: i % matrix.width };
  }
  return null;
}
