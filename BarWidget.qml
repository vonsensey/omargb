import QtQuick
import qs.Ui
import qs.Commons

// OmaRGB bar widget: device count and the color the rig is wearing.
// Built out in U6.
BarWidget {
  id: root
  moduleName: "io.github.vonsensey.omargb"

  implicitWidth: root.vertical ? barSize : dot.width + Style.space(14)
  implicitHeight: root.vertical ? dot.height + Style.space(14) : barSize

  Rectangle {
    id: dot
    width: Style.space(12)
    height: width
    radius: width / 2
    anchors.centerIn: parent
    color: "transparent"
    border.width: Math.max(1, Style.spaceReal(1))
    border.color: root.bar ? root.bar.barForeground : Color.foreground
  }
}
