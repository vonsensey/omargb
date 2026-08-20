import QtQml
import "../lib/settings.js" as S

// Probe for lib/settings.js - the bar-layout settings lookup the service
// depends on. Run headlessly via test/check.sh.
QtObject {
  Component.onCompleted: {
    var fails = 0
    function ok(name, cond) {
      if (cond) console.log("ok   - " + name)
      else { console.log("FAIL - " + name); fails++ }
    }

    var config = {
      bar: { layout: {
        left: [{ id: "omarchy.clock" }],
        center: [],
        right: [
          { id: "io.github.vonsensey.omargb", followTheme: "Off", lockAction: "Lights off" },
          { id: "omarchy.power" }
        ]
      }},
      plugins: [{ id: "some.service.only", opt: "x" }]
    }

    var mine = S.lookupSettings(config, "io.github.vonsensey.omargb")
    ok("finds the bar entry by id", mine.followTheme === "Off")
    ok("reads sibling keys", mine.lockAction === "Lights off")
    ok("falls back to plugins[] entries",
       S.lookupSettings(config, "some.service.only").opt === "x")
    ok("unknown id yields empty object",
       JSON.stringify(S.lookupSettings(config, "nope")) === "{}")
    ok("null config yields empty object",
       JSON.stringify(S.lookupSettings(null, "x")) === "{}")
    ok("layout missing yields empty object",
       JSON.stringify(S.lookupSettings({}, "x")) === "{}")

    ok("setting returns the stored string", S.setting(mine, "followTheme", "On") === "Off")
    ok("setting falls back when missing", S.setting(mine, "urgentFlash", "On") === "On")
    ok("setting falls back on null", S.setting({ a: null }, "a", "d") === "d")
    ok("setting keeps falsy empty string... as fallback trigger",
       S.setting({}, "x", "fb") === "fb")

    console.log(fails === 0 ? "ALL PROBES PASSED" : "PROBES FAILED: " + fails)
    Qt.exit(fails === 0 ? 0 : 1)
  }
}
