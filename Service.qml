import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import qs.Commons
import "lib/format.js" as Format

// OmaRGB service: the shell's half of the bridge conversation.
//
// The OpenRGB SDK is a binary TCP protocol and Quickshell's Socket is
// unix-domain-and-text only, so all protocol work lives in a child process
// (bin/omargb-bridge, python3 stdlib). This file starts that bridge, speaks
// JSON lines with it, and mirrors its state for the widget and panel.
//
// Theme following needs no hook file: the Color singleton's roles change on
// every theme IPC push, and that change triggers a re-read of the full
// resolved palette (omarchy-theme-color --all) which is handed to the bridge.
// Lock and urgent reactions come from in-process signals too: the built-in
// lock service's `locked` property and Hyprland's raw event stream.
Item {
  id: root
  visible: false

  property var shell: null
  property var manifest: null

  readonly property string pluginId: (manifest && manifest.id) || "io.github.vonsensey.omargb"
  readonly property string sourceDir: (manifest && manifest.__sourceDir) ? String(manifest.__sourceDir) : ""

  // ------------------------------------------------------------- settings
  // Read from the bar layout entry the widget writes, exactly as the widget
  // reads them, so changes land without a shell restart (omajam pattern).
  readonly property var settings: lookupSettings(shell ? shell.shellConfig : null, pluginId)

  function lookupSettings(config, id) {
    if (!config || !id) return ({})
    var sections = ["left", "center", "right"]
    if (config.bar && config.bar.layout) {
      for (var s = 0; s < sections.length; s++) {
        var list = config.bar.layout[sections[s]]
        if (!Array.isArray(list)) continue
        for (var i = 0; i < list.length; i++) {
          if (list[i] && String(list[i].id) === id) return list[i]
        }
      }
    }
    if (Array.isArray(config.plugins)) {
      for (var j = 0; j < config.plugins.length; j++) {
        if (config.plugins[j] && String(config.plugins[j].id) === id) return config.plugins[j]
      }
    }
    return ({})
  }

  function setting(name, fallback) {
    var value = settings ? settings[name] : undefined
    return value === undefined || value === null ? fallback : value
  }

  readonly property bool followTheme: Format.isOn(setting("followTheme", "On"), true)
  readonly property string lockAction: String(setting("lockAction", "Dim"))
  readonly property bool urgentFlash: Format.isOn(setting("urgentFlash", "On"), true)

  // ---------------------------------------------------------------- state
  property bool serverConnected: false
  property int protocol: 0
  property var devices: []
  property var rigState: ({})
  property var doctorChecks: []
  property var profiles: []
  property string lastError: ""

  readonly property bool bridgeUp: bridge.running
  readonly property int deviceCount: devices.length
  readonly property bool powerOn: rigState && rigState.power !== false
  readonly property int brightness: rigState && rigState.brightness !== undefined
    ? Number(rigState.brightness) : 100
  readonly property bool openrgbMissing: {
    for (var i = 0; i < doctorChecks.length; i++) {
      if (doctorChecks[i].id === "openrgb-installed")
        return doctorChecks[i].status === "fail"
    }
    return false
  }
  readonly property string statusLabel: Format.statusLabel(
    bridgeUp, serverConnected, openrgbMissing, deviceCount)

  function send(cmd) {
    if (bridge.running) bridge.write(JSON.stringify(cmd) + "\n")
  }

  function handleLine(line) {
    var msg
    try { msg = JSON.parse(line) } catch (e) { return }
    switch (msg.event) {
    case "connected":
      serverConnected = true
      protocol = Number(msg.protocol) || 0
      lastError = ""
      refreshPalette()
      send({ cmd: "doctor" })
      send({ cmd: "profile-list" })
      break
    case "disconnected":
      serverConnected = false
      devices = []
      // With no server the Doctor is the whole story - keep it current.
      if (doctorChecks.length === 0) send({ cmd: "doctor" })
      break
    case "rig":
      devices = msg.devices || []
      rigState = msg.state || ({})
      break
    case "doctor":
      doctorChecks = msg.checks || []
      break
    case "profiles":
      profiles = msg.names || []
      break
    case "error":
      lastError = String(msg.message || "")
      break
    }
  }

  // --------------------------------------------------------------- bridge
  Process {
    id: bridge
    running: false
    // Through the interpreter rather than the shebang so a checkout that
    // lost its executable bit still works.
    command: ["python3", root.sourceDir + "/bin/omargb-bridge"]
    stdinEnabled: true
    stdout: SplitParser {
      splitMarker: "\n"
      onRead: function(line) { root.handleLine(line) }
    }
    onExited: {
      root.serverConnected = false
      restartTimer.restart()
    }
  }

  Timer {
    id: restartTimer
    interval: 2000
    onTriggered: root.syncBridge()
  }

  // `running` is set imperatively rather than bound so the process never
  // launches with an empty sourceDir path (before manifest injection).
  function syncBridge() {
    if (sourceDir !== "" && !bridge.running) {
      bridge.running = true
      firstDoctor.restart()
    }
  }

  // Run the Doctor immediately at startup: when OpenRGB is missing there is
  // no "connected" event to hang it off, and the widget must never look
  // broken on a fresh install.
  Timer {
    id: firstDoctor
    interval: 1200
    onTriggered: root.send({ cmd: "doctor" })
  }
  onSourceDirChanged: Qt.callLater(syncBridge)
  Component.onCompleted: Qt.callLater(syncBridge)

  // ---------------------------------------------------------------- theme
  // One string so a theme push (which reassigns every role at once) costs a
  // single palette refresh.
  readonly property string themeKey: [
    String(Color.accent), String(Color.background), String(Color.foreground),
    String(Color.urgent), String(Color.muted)
  ].join("|")
  onThemeKeyChanged: paletteDebounce.restart()
  onFollowThemeChanged: if (followTheme) paletteDebounce.restart()

  Timer {
    id: paletteDebounce
    interval: 250
    onTriggered: root.refreshPalette()
  }

  function refreshPalette() {
    if (!followTheme) return
    if (themeColor.running) {
      paletteDebounce.restart()
      return
    }
    themeColor.running = true
  }

  Process {
    id: themeColor
    running: false
    command: ["omarchy-theme-color", "--all"]
    stdout: StdioCollector { id: paletteOut }
    onExited: function(code) {
      if (code === 0 && paletteOut.text !== "")
        root.send({ cmd: "set-palette", raw: paletteOut.text })
    }
  }

  // ------------------------------------------------------------- reactive
  // Lock: the built-in lock plugin's service exposes `locked`; binding to it
  // costs nothing and needs no polling.
  readonly property var lockService: shell ? shell.serviceFor("omarchy.lock") : null
  readonly property bool sessionLocked: lockService ? lockService.locked === true : false

  onSessionLockedChanged: {
    if (sessionLocked) {
      if (lockAction === "Dim") send({ cmd: "overlay-dim", factor: 0.08 })
      else if (lockAction === "Lights off") send({ cmd: "overlay-off" })
    } else if (lockAction !== "Nothing") {
      send({ cmd: "overlay-clear" })
    }
  }

  Connections {
    target: Hyprland
    function onRawEvent(event) {
      if (!root.urgentFlash) return
      if (String(event.name) !== "urgent") return
      root.send({ cmd: "overlay-flash", color: Format.hex6(Color.urgent),
                  duration_ms: 700 })
    }
  }
}
