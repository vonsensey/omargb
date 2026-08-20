import QtQuick
import Quickshell
import Quickshell.Io

// OmaRGB service: owns the bridge process (bin/omargb-bridge) that speaks the
// OpenRGB SDK protocol, mirrors its state for the widget and panel, and feeds
// it theme palettes and reactive events. Built out in U6.
Item {
  id: root
  visible: false

  property var shell: null
  property var manifest: null
}
