import QtQuick
import Quickshell
import Quickshell.Wayland
import qs.Commons
import qs.Ui
import "lib/format.js" as Format

// OmaRGB panel: the control room. Every device as a card - zones with
// theme roles, manual colors through a full saturation/value picker,
// hardware modes, OpenRGB profiles, a live keyboard matrix - and the
// Doctor, which takes over whenever there is nothing to control yet.
Item {
  id: root

  property var shell: null
  property var manifest: null
  property var service: null
  property bool opened: false

  readonly property var svc: service
  readonly property var devices: svc ? svc.devices : []
  readonly property var checks: svc ? svc.doctorChecks : []
  readonly property bool connected: svc ? svc.serverConnected === true : false
  readonly property bool powerOn: svc ? svc.powerOn : true
  property bool showDoctor: false

  readonly property var roles: ["accent", "foreground", "background", "muted",
    "urgent", "red", "orange", "yellow", "green", "cyan", "blue", "magenta"]

  // Color picker session state.
  property string pickerDevice: ""
  property int pickerZone: -1
  property real pickH: 0
  property real pickS: 1
  property real pickV: 1
  readonly property string pickerHex: Format.hsvToHex(pickH, pickS, pickV)

  function open(payloadJson) {
    root.opened = true
    root.showDoctor = !root.connected
    if (root.svc) {
      root.svc.send({ cmd: "doctor" })
      root.svc.send({ cmd: "profile-list" })
      root.svc.send({ cmd: "snapshot" })
    }
    Qt.callLater(function() { keyCatcher.forceActiveFocus() })
  }

  // Automation surface: everything the panel can do, a script or agent can
  // do headlessly through the shell IPC -
  //   omarchy-shell shell call io.github.vonsensey.omargb command '{"cmd":"power","on":false}'
  //   omarchy-shell shell call io.github.vonsensey.omargb status ""
  function command(payloadJson) {
    if (!root.svc) return "no service"
    var cmd
    try { cmd = JSON.parse(payloadJson) } catch (e) { return "bad json" }
    if (!cmd || typeof cmd.cmd !== "string") return "missing cmd"
    root.svc.send(cmd)
    return "ok"
  }

  function status() {
    if (!root.svc) return "{}"
    return JSON.stringify({
      connected: root.svc.serverConnected,
      protocol: root.svc.protocol,
      power: root.svc.powerOn,
      brightness: root.svc.brightness,
      profiles: root.svc.profiles,
      doctor: root.svc.doctorChecks,
      devices: root.svc.devices
    })
  }
  function close() {
    root.pickerZone = -1
    root.opened = false
  }
  function toggle() { root.opened ? close() : open("{}") }

  onConnectedChanged: if (opened && !connected) showDoctor = true

  function openPicker(deviceKey, zoneIdx, currentHex) {
    var hsv = Format.hexToHsv(currentHex || "#ff0000")
    pickH = hsv.h; pickS = hsv.s; pickV = hsv.v
    pickerDevice = deviceKey
    pickerZone = zoneIdx
  }

  function zoneSwatch(dev, zoneIdx) {
    var start = Format.zoneStart(dev.zones, zoneIdx)
    var colors = (root.svc && root.svc.colorsByDevice[String(dev.index)]) || dev.colors
    if (colors && colors.length > start) return colors[start]
    return "#000000"
  }

  function copyFix(fix) {
    if (fix) Quickshell.execDetached(["wl-copy", String(fix)])
  }

  readonly property color background: Color.menu.background
  readonly property color foreground: Color.menu.text
  readonly property color borderColor: Color.menu.border
  readonly property var borderSpec: Border.surfaceSpec("menu", "border", borderColor, Math.max(1, Style.space(2)))
  readonly property string fontFamily: Style.font.menuFamily
  readonly property color faint: Qt.rgba(foreground.r, foreground.g, foreground.b, 0.12)

  PanelWindow {
    id: panel
    visible: root.opened
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    WlrLayershell.namespace: "omarchy-omargb"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: root.opened ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
    exclusionMode: ExclusionMode.Ignore

    Rectangle { anchors.fill: parent; color: Color.menu.scrim }
    MouseArea { anchors.fill: parent; onClicked: root.close() }

    BorderSurface {
      id: card
      width: Math.min(Style.space(680), panel.width - Style.gapsOut * 2)
      height: Math.min(Style.space(800), panel.height - Style.gapsOut * 2)
      radius: Style.cornerRadius
      anchors.centerIn: parent
      color: root.background
      borderSpec: root.borderSpec
      padding: Style.spacing.panelPadding

      MouseArea { anchors.fill: parent; onClicked: {} }

      Item {
        id: keyCatcher
        anchors.fill: parent
        focus: true
        Keys.priority: Keys.BeforeItem
        Keys.onPressed: function(event) {
          if (event.key === Qt.Key_Escape) {
            if (root.pickerZone >= 0) root.pickerZone = -1
            else root.close()
            event.accepted = true
          } else if (event.key === Qt.Key_P) {
            if (root.svc) root.svc.send({ cmd: "power", on: !root.powerOn })
            event.accepted = true
          } else if (event.key === Qt.Key_D) {
            root.showDoctor = !root.showDoctor
            event.accepted = true
          } else if (event.key === Qt.Key_Minus || event.key === Qt.Key_Underscore) {
            // No || fallback: 0 is falsy and would jump 0 -> 90.
            if (root.svc) root.svc.send({ cmd: "brightness",
              value: Math.max(0, root.svc.brightness - 10) })
            event.accepted = true
          } else if (event.key === Qt.Key_Plus || event.key === Qt.Key_Equal) {
            if (root.svc) root.svc.send({ cmd: "brightness",
              value: Math.min(100, root.svc.brightness + 10) })
            event.accepted = true
          }
        }
      }

      Column {
        anchors.fill: parent
        anchors.topMargin: card.contentTopInset
        anchors.rightMargin: card.contentRightInset
        anchors.bottomMargin: card.contentBottomInset
        anchors.leftMargin: card.contentLeftInset
        spacing: Style.spacing.md

        // ---------------------------------------------------------- header
        Item {
          width: parent.width
          height: Math.max(titleText.implicitHeight, headerRow.implicitHeight)

          Text {
            id: titleText
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            text: "OmaRGB"
            textFormat: Text.PlainText
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.heading
            font.bold: true
          }

          Text {
            anchors.left: titleText.right
            anchors.leftMargin: Style.space(10)
            anchors.verticalCenter: parent.verticalCenter
            text: root.svc ? root.svc.statusLabel : ""
            textFormat: Text.PlainText
            color: root.foreground
            opacity: 0.55
            font.family: root.fontFamily
            font.pixelSize: Style.font.small
          }

          Row {
            id: headerRow
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            spacing: Style.space(6)

            Button {
              text: "Doctor"
              iconText: Format.doctorBadge(root.checks) === "ok" ? "󰄬" : "󰀪"
              selected: root.showDoctor
              bordered: true
              fontFamily: root.fontFamily
              onClicked: root.showDoctor = !root.showDoctor
            }
            Button {
              text: root.powerOn ? "Lights off" : "Lights on"
              iconText: "󰐥"
              bordered: true
              fontFamily: root.fontFamily
              onClicked: if (root.svc) root.svc.send({ cmd: "power", on: !root.powerOn })
            }
            PanelActionButton {
              iconText: "󰆓"
              tooltipText: "Persist current colors to device flash"
              onClicked: if (root.svc) root.svc.send({ cmd: "persist" })
            }
          }
        }

        // ------------------------------------------------- brightness row
        Item {
          width: parent.width
          height: root.connected && !root.showDoctor ? brightRow.implicitHeight : 0
          visible: root.connected && !root.showDoctor

          Row {
            id: brightRow
            width: parent.width
            spacing: Style.space(10)

            Text {
              anchors.verticalCenter: parent.verticalCenter
              text: "Brightness"
              textFormat: Text.PlainText
              color: root.foreground
              opacity: 0.8
              font.family: root.fontFamily
              font.pixelSize: Style.font.small
            }
            PanelSlider {
              width: brightRow.width - Style.space(180)
              anchors.verticalCenter: parent.verticalCenter
              minimum: 0
              maximum: 100
              step: 5
              integer: true
              value: root.svc ? root.svc.brightness : 100
              onReleased: function(v) {
                if (root.svc) root.svc.send({ cmd: "brightness", value: Math.round(v) })
              }
            }
            Text {
              anchors.verticalCenter: parent.verticalCenter
              text: (root.svc ? root.svc.brightness : 100) + "%"
              textFormat: Text.PlainText
              color: root.foreground
              opacity: 0.6
              font.family: root.fontFamily
              font.pixelSize: Style.font.small
            }
          }
        }

        // --------------------------------------------------- profiles row
        Item {
          width: parent.width
          height: root.connected && !root.showDoctor ? profRow.implicitHeight : 0
          visible: root.connected && !root.showDoctor

          Row {
            id: profRow
            width: parent.width
            spacing: Style.space(6)

            Text {
              anchors.verticalCenter: parent.verticalCenter
              text: "Profiles"
              textFormat: Text.PlainText
              color: root.foreground
              opacity: 0.8
              font.family: root.fontFamily
              font.pixelSize: Style.font.small
            }
            Repeater {
              model: root.svc ? root.svc.profiles : []
              delegate: Button {
                required property var modelData
                // plain(): profile names come from the server and Button
                // sets no textFormat of its own.
                text: Format.plain(modelData)
                bordered: true
                fontFamily: root.fontFamily
                tooltipText: "Load OpenRGB profile"
                onClicked: if (root.svc) root.svc.send({ cmd: "profile-load", name: String(modelData) })
              }
            }
            TextField {
              id: profileName
              width: Style.space(120)
              anchors.verticalCenter: parent.verticalCenter
              placeholderText: "new profile"
            }
            Button {
              text: "Save"
              bordered: true
              fontFamily: root.fontFamily
              onClicked: {
                if (root.svc && profileName.text !== "") {
                  root.svc.send({ cmd: "profile-save", name: profileName.text })
                  profileName.text = ""
                }
              }
            }
          }
        }

        PanelSeparator { width: parent.width }

        // ------------------------------------------------------- content
        Flickable {
          id: content
          width: parent.width
          // Leave room for the footer hint below - `parent.height - y` alone
          // pushes it off the card.
          height: parent.height - y - footerHint.implicitHeight - parent.spacing
          contentHeight: root.showDoctor || !root.connected
            ? doctorColumn.implicitHeight : deviceColumn.implicitHeight
          clip: true

          // ------------------------------------------------------ doctor
          Column {
            id: doctorColumn
            width: content.width
            visible: root.showDoctor || !root.connected
            spacing: Style.space(8)

            Text {
              width: parent.width
              visible: !root.connected
              text: "No OpenRGB server yet - here is what this machine needs:"
              textFormat: Text.PlainText
              wrapMode: Text.WordWrap
              color: root.foreground
              opacity: 0.8
              font.family: root.fontFamily
              font.pixelSize: Style.font.body
            }

            Repeater {
              model: root.checks
              delegate: Rectangle {
                required property var modelData
                width: doctorColumn.width
                height: checkCol.implicitHeight + Style.space(14)
                radius: Style.cornerRadius / 2
                color: root.faint
                opacity: modelData.status === "skip" ? 0.55 : 1

                Column {
                  id: checkCol
                  anchors.left: parent.left
                  anchors.right: parent.right
                  anchors.verticalCenter: parent.verticalCenter
                  anchors.leftMargin: Style.space(10)
                  anchors.rightMargin: Style.space(10)
                  spacing: Style.space(4)

                  Row {
                    spacing: Style.space(8)
                    Text {
                      text: modelData.status === "ok" ? "󰄬"
                        : modelData.status === "warn" ? "󰀪"
                        : modelData.status === "fail" ? "󰅖" : "󰧟"
                      textFormat: Text.PlainText
                      color: modelData.status === "fail" ? Color.urgent : root.foreground
                      opacity: modelData.status === "ok" ? 0.7 : 1
                      font.pixelSize: Style.font.body
                    }
                    Text {
                      width: checkCol.width - Style.space(30)
                      text: String(modelData.summary)
                      textFormat: Text.PlainText
                      wrapMode: Text.WordWrap
                      color: root.foreground
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.body
                    }
                  }

                  Rectangle {
                    visible: modelData.fix !== null && modelData.fix !== undefined
                             && modelData.status !== "ok"
                    width: parent.width
                    height: fixText.implicitHeight + Style.space(10)
                    radius: Style.cornerRadius / 3
                    color: Color.menu.background
                    border.width: 1
                    border.color: root.faint

                    Text {
                      id: fixText
                      anchors.left: parent.left
                      anchors.right: copyGlyph.left
                      anchors.verticalCenter: parent.verticalCenter
                      anchors.leftMargin: Style.space(8)
                      text: String(modelData.fix || "")
                      textFormat: Text.PlainText
                      wrapMode: Text.WrapAnywhere
                      color: root.foreground
                      opacity: 0.85
                      font.family: "monospace"
                      font.pixelSize: Style.font.small
                    }
                    Text {
                      id: copyGlyph
                      anchors.right: parent.right
                      anchors.rightMargin: Style.space(8)
                      anchors.verticalCenter: parent.verticalCenter
                      text: "󰆏"
                      textFormat: Text.PlainText
                      color: root.foreground
                      opacity: 0.6
                    }
                    MouseArea {
                      anchors.fill: parent
                      cursorShape: Qt.PointingHandCursor
                      onClicked: root.copyFix(modelData.fix)
                    }
                  }
                }
              }
            }
          }

          // ----------------------------------------------------- devices
          Column {
            id: deviceColumn
            width: content.width
            visible: root.connected && !root.showDoctor
            spacing: Style.space(10)

            Repeater {
              model: root.devices
              delegate: Rectangle {
                id: deviceCard
                required property var modelData
                width: deviceColumn.width
                height: devCol.implicitHeight + Style.space(18)
                radius: Style.cornerRadius / 2
                color: root.faint

                readonly property var dev: modelData

                Column {
                  id: devCol
                  anchors.left: parent.left
                  anchors.right: parent.right
                  anchors.verticalCenter: parent.verticalCenter
                  anchors.leftMargin: Style.space(12)
                  anchors.rightMargin: Style.space(12)
                  spacing: Style.space(6)

                  Row {
                    spacing: Style.space(8)
                    Text {
                      text: {
                        var t = deviceCard.dev.typeName
                        if (t === "keyboard") return "󰌌"
                        if (t === "mouse") return "󰍽"
                        if (t === "cooler") return "󰈐"
                        if (t === "dram") return "󰑭"
                        if (t === "gpu") return "󰢮"
                        if (t === "motherboard") return "󰚗"
                        if (t === "ledstrip" || t === "light") return "󰛨"
                        return "󰌵"
                      }
                      textFormat: Text.PlainText
                      color: root.foreground
                      font.pixelSize: Style.font.heading
                      anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                      text: String(deviceCard.dev.name)
                      textFormat: Text.PlainText
                      color: root.foreground
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.body
                      font.bold: true
                      anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                      text: String(deviceCard.dev.typeName)
                      textFormat: Text.PlainText
                      color: root.foreground
                      opacity: 0.5
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.small
                      anchors.verticalCenter: parent.verticalCenter
                    }
                  }

                  // Hardware mode: OmaRGB drives Direct for theme mapping,
                  // but the device's own effects are one pick away.
                  Row {
                    spacing: Style.space(8)
                    visible: (deviceCard.dev.modes || []).length > 1
                    Text {
                      anchors.verticalCenter: parent.verticalCenter
                      text: "Mode"
                      textFormat: Text.PlainText
                      color: root.foreground
                      opacity: 0.6
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.small
                    }
                    Dropdown {
                      width: Style.space(150)
                      showLabel: false
                      // Sanitized copies for display (mode names are
                      // server-provided); selection maps back by position.
                      readonly property var saneModes: (deviceCard.dev.modes || []).map(Format.plain)
                      options: saneModes
                      value: {
                        var a = Number(deviceCard.dev.activeMode)
                        return a >= 0 && a < saneModes.length ? saneModes[a] : ""
                      }
                      onChanged: function(v) {
                        var idx = saneModes.indexOf(v)
                        if (idx >= 0 && root.svc)
                          root.svc.send({ cmd: "mode", device: deviceCard.dev.key, mode: idx })
                      }
                    }
                  }

                  // Zone rows: role dropdown + live swatch + manual color.
                  Repeater {
                    model: deviceCard.dev.zones
                    delegate: Item {
                      id: zoneRow
                      required property var modelData
                      readonly property var zone: modelData
                      width: devCol.width
                      height: Style.spacing.controlHeight

                      Text {
                        id: zoneName
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        width: Style.space(185)
                        elide: Text.ElideRight
                        text: String(zoneRow.zone.name) + " (" + zoneRow.zone.ledsCount + ")"
                        textFormat: Text.PlainText
                        color: root.foreground
                        opacity: 0.85
                        font.family: root.fontFamily
                        font.pixelSize: Style.font.small
                      }

                      Dropdown {
                        anchors.left: zoneName.right
                        anchors.verticalCenter: parent.verticalCenter
                        width: Style.space(150)
                        showLabel: false
                        options: root.roles
                        value: zoneRow.zone.override ? "manual" : String(zoneRow.zone.role)
                        onChanged: function(v) {
                          if (root.svc) root.svc.send({ cmd: "set-role",
                            device: deviceCard.dev.key, zone: zoneRow.zone.index, role: v })
                        }
                      }

                      Row {
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: Style.space(6)

                        Rectangle {
                          width: Style.space(30)
                          height: Style.space(18)
                          radius: Style.space(4)
                          anchors.verticalCenter: parent.verticalCenter
                          color: root.zoneSwatch(deviceCard.dev, zoneRow.zone.index)
                          border.width: 1
                          border.color: root.faint
                          MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.openPicker(deviceCard.dev.key,
                              zoneRow.zone.index,
                              root.zoneSwatch(deviceCard.dev, zoneRow.zone.index))
                          }
                        }
                        Button {
                          visible: !!zoneRow.zone.override
                          iconText: "󰜺"
                          tooltipText: "Back to the theme role"
                          fontFamily: root.fontFamily
                          onClicked: if (root.svc) root.svc.send({ cmd: "clear-override",
                            device: deviceCard.dev.key, zone: zoneRow.zone.index })
                        }
                      }
                    }
                  }

                  // Keyboard matrix: the real layout, live colors.
                  Repeater {
                    model: deviceCard.dev.zones
                    delegate: Item {
                      id: matrixWrap
                      required property var modelData
                      readonly property var zone: modelData
                      readonly property var matrix: zone.matrix || null
                      visible: matrix !== null
                      width: devCol.width
                      height: matrix ? matrixGrid.implicitHeight + Style.space(6) : 0

                      Grid {
                        id: matrixGrid
                        columns: matrixWrap.matrix ? matrixWrap.matrix.width : 1
                        spacing: Math.max(1, Style.spaceReal(2))

                        readonly property real cell: matrixWrap.matrix
                          ? Math.max(4, Math.floor((devCol.width - (matrixWrap.matrix.width - 1) * spacing) / matrixWrap.matrix.width))
                          : 6
                        readonly property int start: Format.zoneStart(deviceCard.dev.zones, matrixWrap.zone.index)
                        // Live colors come from the light per-device color
                        // stream, so routine repaints touch only this binding
                        // and never rebuild the cell delegates.
                        readonly property var liveColors:
                          (root.svc && root.svc.colorsByDevice[String(deviceCard.dev.index)]) || deviceCard.dev.colors

                        Repeater {
                          model: matrixWrap.matrix ? matrixWrap.matrix.map : []
                          delegate: Rectangle {
                            required property var modelData
                            readonly property bool empty: Number(modelData) === Format.MATRIX_EMPTY
                            width: matrixGrid.cell
                            height: matrixGrid.cell
                            radius: Math.max(1, matrixGrid.cell / 4)
                            color: empty ? "transparent"
                              : (matrixGrid.liveColors[matrixGrid.start + Number(modelData)] || "#000000")
                            border.width: empty ? 0 : 1
                            border.color: root.faint
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }

        // ------------------------------------------------------- footer
        Text {
          id: footerHint
          width: parent.width
          horizontalAlignment: Text.AlignHCenter
          text: "Esc close · P lights · D doctor · +/- brightness · swatch = pick a color"
          textFormat: Text.PlainText
          color: root.foreground
          opacity: 0.4
          font.family: root.fontFamily
          font.pixelSize: Style.font.small
        }
      }
    }

    // ------------------------------------------------------ color picker
    // A modal layer over the card: click-away cancels, the picker floats
    // centered. Plain surfaces - PopupCard is bar-popout machinery.
    MouseArea {
      anchors.fill: parent
      visible: root.pickerZone >= 0
      onClicked: root.pickerZone = -1
    }
    BorderSurface {
      id: picker
      visible: root.pickerZone >= 0
      anchors.centerIn: parent
      width: Style.space(270)
      height: pickerCol.implicitHeight + Style.space(36)
      radius: Style.cornerRadius
      color: root.background
      borderSpec: root.borderSpec

      MouseArea { anchors.fill: parent; onClicked: {} }

      Column {
        id: pickerCol
        anchors.centerIn: parent
        width: Style.space(230)
        spacing: Style.space(10)

        // Saturation/value square: hue base, white->right, black->down.
        Rectangle {
          id: svSquare
          width: parent.width
          height: Style.space(150)
          radius: Style.space(4)
          color: Format.hsvToHex(root.pickH, 1, 1)

          Rectangle {
            anchors.fill: parent
            radius: parent.radius
            gradient: Gradient {
              orientation: Gradient.Horizontal
              GradientStop { position: 0.0; color: "#ffffff" }
              GradientStop { position: 1.0; color: "transparent" }
            }
          }
          Rectangle {
            anchors.fill: parent
            radius: parent.radius
            gradient: Gradient {
              GradientStop { position: 0.0; color: "transparent" }
              GradientStop { position: 1.0; color: "#000000" }
            }
          }
          Rectangle {
            x: root.pickS * (svSquare.width - width)
            y: (1 - root.pickV) * (svSquare.height - height)
            width: Style.space(12)
            height: width
            radius: width / 2
            color: "transparent"
            border.width: 2
            border.color: root.pickV > 0.6 && root.pickS < 0.4 ? "#000000" : "#ffffff"
          }
          MouseArea {
            anchors.fill: parent
            onPressed: function(mouse) { update(mouse) }
            onPositionChanged: function(mouse) { if (pressed) update(mouse) }
            function update(mouse) {
              root.pickS = Math.max(0, Math.min(1, mouse.x / svSquare.width))
              root.pickV = Math.max(0, Math.min(1, 1 - mouse.y / svSquare.height))
            }
          }
        }

        // Hue bar.
        Rectangle {
          id: hueBar
          width: parent.width
          height: Style.space(16)
          radius: Style.space(4)
          gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.00; color: "#ff0000" }
            GradientStop { position: 0.17; color: "#ffff00" }
            GradientStop { position: 0.33; color: "#00ff00" }
            GradientStop { position: 0.50; color: "#00ffff" }
            GradientStop { position: 0.67; color: "#0000ff" }
            GradientStop { position: 0.83; color: "#ff00ff" }
            GradientStop { position: 1.00; color: "#ff0000" }
          }
          Rectangle {
            x: root.pickH * (hueBar.width - width)
            width: Style.space(6)
            height: hueBar.height
            radius: 2
            color: "transparent"
            border.width: 2
            border.color: "#ffffff"
          }
          MouseArea {
            anchors.fill: parent
            onPressed: function(mouse) { update(mouse) }
            onPositionChanged: function(mouse) { if (pressed) update(mouse) }
            function update(mouse) {
              root.pickH = Math.max(0, Math.min(0.9999, mouse.x / hueBar.width))
            }
          }
        }

        Row {
          spacing: Style.space(8)
          Rectangle {
            width: Style.space(34)
            height: Style.space(22)
            radius: Style.space(4)
            color: root.pickerHex
            border.width: 1
            border.color: root.faint
            anchors.verticalCenter: parent.verticalCenter
          }
          Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.pickerHex
            textFormat: Text.PlainText
            color: root.foreground
            font.family: "monospace"
            font.pixelSize: Style.font.body
          }
        }

        Row {
          spacing: Style.space(8)
          Button {
            text: "Apply"
            bordered: true
            fontFamily: root.fontFamily
            onClicked: {
              if (root.svc) root.svc.send({ cmd: "set-zone-color",
                device: root.pickerDevice, zone: root.pickerZone,
                color: root.pickerHex })
              root.pickerZone = -1
            }
          }
          Button {
            text: "Cancel"
            bordered: true
            fontFamily: root.fontFamily
            onClicked: root.pickerZone = -1
          }
        }
      }
    }
  }
}
