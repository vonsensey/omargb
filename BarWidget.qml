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

  // A Grid so the swatch+state pair stacks in vertical bars instead of the
  // state text vanishing - the widget must show its state in all four
  // orientations.
  Grid {
    id: row
    anchors.centerIn: parent
    columns: root.vertical ? 1 : 2
    columnSpacing: Style.space(5)
    rowSpacing: Style.space(3)
    horizontalItemAlignment: Grid.AlignHCenter
    verticalItemAlignment: Grid.AlignVCenter

    // The RGB triad: three dots wearing the theme's own red, green, and
    // blue - the plugin's name, drawn. Dimmed hollow until there is a
    // palette-wearing rig to show.
    Item {
      id: swatch
      width: Style.space(13)
      height: Style.space(12)
      opacity: root.powerOn ? 1.0 : 0.4

      // Literal channel colors, deliberately: these are the hardware's
      // R/G/B, which no desktop theme redefines (ristretto's "blue" is
      // salmon). Same color-literal class as the panel's hue bar - a glyph
      // whose meaning IS the colors. Softened so they sit on any bar.
      readonly property bool lit: root.healthy
      readonly property real dot: Style.space(7)
      readonly property color rim: root.bar ? root.bar.barForeground : Color.foreground

      Rectangle {  // green, bottom-left
        width: swatch.dot; height: swatch.dot; radius: swatch.dot / 2
        x: 0; y: swatch.height - height
        color: swatch.lit ? "#44bb55" : "transparent"
        border.width: 1; border.color: swatch.rim
      }
      Rectangle {  // blue, bottom-right
        width: swatch.dot; height: swatch.dot; radius: swatch.dot / 2
        x: swatch.width - width; y: swatch.height - height
        color: swatch.lit ? "#4477ee" : "transparent"
        border.width: 1; border.color: swatch.rim
      }
      Rectangle {  // red on top, centered
        width: swatch.dot; height: swatch.dot; radius: swatch.dot / 2
        x: (swatch.width - width) / 2; y: 0
        color: swatch.lit ? "#ee4444" : "transparent"
        border.width: 1; border.color: swatch.rim
      }
    }

    Text {
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
