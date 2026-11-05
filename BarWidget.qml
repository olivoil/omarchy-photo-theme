import QtQuick
import Quickshell
import qs.Ui
import qs.Commons as Commons

BarWidget {
  id: root
  moduleName: "io.github.olivoil.personal-theme"
  Commons.Translations { id: strings; directory: Qt.resolvedUrl("i18n") }
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight
  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: ""
    tooltipText: strings.t("tooltip")
    onPressed: function(mouseButton) {
      root.bar.run("omarchy menu summon personal-theme")
    }
  }
}
