import QtQuick
import Quickshell
import qs.Ui as Ui
import qs.Commons as Commons

Ui.BarWidget {
  id: root
  moduleName: "io.github.olivoil.photo-theme"
  Commons.Translations { id: strings; directory: Qt.resolvedUrl("i18n") }
  readonly property string backend: decodeURIComponent(String(Qt.resolvedUrl("bin/photo-theme")).replace(/^file:\/\//, ""))
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight
  Ui.BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: ""
    tooltipText: strings.t("tooltip")
    onPressed: function(mouseButton) {
      if (mouseButton === Qt.RightButton)
        Quickshell.execDetached([root.backend, "toggle-mode"])
      else
        root.bar.run("omarchy menu summon photo-theme")
    }
  }
}
