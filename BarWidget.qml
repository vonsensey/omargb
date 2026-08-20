import QtQuick
import qs.Ui
import qs.Commons
import "lib/format.js" as Format

// OmaRGB bar widget: a swatch wearing the color your rig is wearing, plus
// the device count. Never invisible - with no OpenRGB or no devices it shows
// its state instead of vanishing. Left click opens the control room panel;
// right click toggles all lights.
BarWidget {
  id: root
  moduleName: "io.github.vonsensey.omargb"

  readonly property string pluginId: "io.github.vonsensey.omargb"
  readonly property var svc: bar && bar.shell ? bar.shell.serviceFor(pluginId) : null

  readonly property int count: svc ? svc.deviceCount : 0
  readonly property bool healthy: svc ? svc.serverConnected === true : false
  readonly property bool powerOn: svc ? svc.powerOn : true
  readonly property string glyph: {
    if (!svc || !svc.bridgeUp) return "󰔟"      // starting
    if (svc.openrgbMissing) return "󰦉"          // doctor has news
    return "󰔟"                                  // connecting
  }

  implicitWidth: root.vertical ? barSize : row.width + Style.space(14)
  implicitHeight: root.vertical ? row.height + Style.space(14) : barSize

  Row {
    id: row
    anchors.centerIn: parent
    spacing: Style.space(5)

    Rectangle {
      id: swatch
      width: Style.space(11)
      height: width
      radius: width / 2
      anchors.verticalCenter: parent.verticalCenter
      color: root.healthy && root.powerOn ? Color.accent : "transparent"
      border.width: Math.max(1, Style.spaceReal(1))
      border.color: root.bar ? root.bar.barForeground : Color.foreground
      opacity: root.powerOn ? 1.0 : 0.4
    }

    Text {
      anchors.verticalCenter: parent.verticalCenter
      visible: !root.vertical
      textFormat: Text.PlainText
      color: root.bar ? root.bar.barForeground : Color.foreground
      font.family: root.bar ? root.bar.fontFamily : ""
      font.pixelSize: Style.fontSize(12)
      text: root.healthy ? String(root.count) : root.glyph
      opacity: root.healthy ? 0.9 : 0.6
    }
  }

  function tooltipText() {
    if (!root.svc) return "OmaRGB"
    var line = "OmaRGB - " + root.svc.statusLabel
    if (root.svc.openrgbMissing) line += ". Click for the Doctor."
    else if (root.healthy) line += (root.powerOn ? "" : " (lights off)") + ". Right click toggles lights."
    return line
  }

  MouseArea {
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor
    acceptedButtons: Qt.LeftButton | Qt.RightButton

    onClicked: function(mouse) {
      if (mouse.button === Qt.RightButton) {
        if (root.svc) root.svc.send({ cmd: "power", on: !root.powerOn })
      } else if (root.bar && root.bar.shell) {
        root.bar.shell.toggle(root.pluginId, "{}")
      }
    }
    onEntered: if (root.bar) root.bar.showTooltip(root, root.tooltipText())
    onExited: if (root.bar) root.bar.hideTooltip(root)
  }
}
