import QtQml
import "../lib/format.js" as Format

// Probe for lib/format.js. Run with:
//   QT_FORCE_STDERR_LOGGING=1 QT_QPA_PLATFORM=offscreen qml6 probe_format.qml
QtObject {
  Component.onCompleted: {
    var fails = 0
    function ok(name, cond) {
      if (cond) console.log("ok   - " + name)
      else { console.log("FAIL - " + name); fails++ }
    }

    ok("hex6 strips alpha", Format.hex6("#ffa55555") === "#a55555")
    ok("hex6 passes rgb through", Format.hex6("#a55555") === "#a55555")

    ok("isOn: 'On' is true", Format.isOn("On", false) === true)
    ok("isOn: 'Off' is false", Format.isOn("Off", true) === false)
    ok("isOn: empty uses fallback", Format.isOn("", true) === true)
    ok("isOn: undefined uses fallback", Format.isOn(undefined, false) === false)
    ok("isOn: garbage is false", Format.isOn("banana", true) === false)

    ok("status: bridge down", Format.statusLabel(false, false, false, 0) === "starting")
    ok("status: needs openrgb", Format.statusLabel(true, false, true, 0) === "needs OpenRGB")
    ok("status: connecting", Format.statusLabel(true, false, false, 0) === "connecting")
    ok("status: no devices", Format.statusLabel(true, true, false, 0) === "no devices")
    ok("status: singular", Format.statusLabel(true, true, false, 1) === "1 device")
    ok("status: plural", Format.statusLabel(true, true, false, 6) === "6 devices")
    ok("status: live server outranks missing binary",
       Format.statusLabel(true, true, true, 6) === "6 devices")

    ok("doctorBadge: fail wins", Format.doctorBadge(
         [{status:"ok"},{status:"warn"},{status:"fail"}]) === "fail")
    ok("doctorBadge: warn beats ok", Format.doctorBadge(
         [{status:"ok"},{status:"warn"}]) === "warn")
    ok("doctorBadge: all ok", Format.doctorBadge([{status:"ok"},{status:"skip"}]) === "ok")
    ok("doctorBadge: empty is ok", Format.doctorBadge([]) === "ok")

    ok("hsv red", Format.hsvToHex(0, 1, 1) === "#ff0000")
    ok("hsv green", Format.hsvToHex(1/3, 1, 1) === "#00ff00")
    ok("hsv white (S=0)", Format.hsvToHex(0.5, 0, 1) === "#ffffff")
    ok("hsv black (V=0)", Format.hsvToHex(0.5, 1, 0) === "#000000")
    ok("hsv grey", Format.hsvToHex(0, 0, 0.5) === "#808080")
    var rt = Format.hexToHsv("#f38d70")
    ok("hex->hsv->hex roundtrip", Format.hsvToHex(rt.h, rt.s, rt.v) === "#f38d70")
    var corner = Format.hexToHsv("#000000")
    ok("black hsv is v=0", corner.v === 0 && corner.s === 0)

    ok("zoneStart first is 0", Format.zoneStart([{ledsCount:1},{ledsCount:12}], 0) === 0)
    ok("zoneStart sums preceding", Format.zoneStart([{ledsCount:1},{ledsCount:12},{ledsCount:8}], 2) === 13)
    ok("zoneStart clamps", Format.zoneStart([{ledsCount:5}], 3) === 5)

    ok("MATRIX_EMPTY is the SDK sentinel", Format.MATRIX_EMPTY === 4294967295)

    ok("plain strips markup", Format.plain("<img src=x> Corsair & K70") === "img src=x Corsair  K70")
    ok("plain passes clean names", Format.plain("Fixture AIO Cooler") === "Fixture AIO Cooler")
    ok("plain stringifies non-strings", Format.plain(42) === "42")

    console.log(fails === 0 ? "ALL PROBES PASSED" : "PROBES FAILED: " + fails)
    Qt.exit(fails === 0 ? 0 : 1)
  }
}
