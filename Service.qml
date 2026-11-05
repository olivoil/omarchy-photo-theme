import QtQuick
import Quickshell
import Quickshell.Io

Item {
  id: root
  property var shell: null
  property var manifest: null
  property bool ready: false
  property string lease: Date.now().toString() + "-" + Math.random().toString(36).slice(2)
  property string lastStatus: "{}"
  readonly property string backend: decodeURIComponent(String(Qt.resolvedUrl("bin/photo-theme")).replace(/^file:\/\//, ""))

  function check() {
    if (ready && !statusProcess.running) statusProcess.running = true
  }
  function updateColors() {
    if (ready && !colorProcess.running) colorProcess.running = true
  }
  function sync() {
    if (ready && !syncProcess.running) syncProcess.running = true
  }
  Component.onCompleted: activation.running = true
  Component.onDestruction: Quickshell.execDetached([backend, "deactivate", lease])

  Process {
    id: activation
    command: [root.backend, "activate", root.lease]
    onExited: function(code) { root.ready = code === 0; root.check() }
  }
  Timer { interval: 5000; running: root.ready; repeat: true; onTriggered: root.check() }
  Process {
    id: statusProcess
    command: [root.backend, "status"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        root.lastStatus = String(text || "{}")
        try {
          let state = JSON.parse(root.lastStatus)
          if (state.transitionDue || state.colorDue || state.rotationDue) root.updateColors()
          if (state.syncDue) root.sync()
        } catch (e) { console.warn("Photo Theme: invalid status") }
      }
    }
  }
  Process {
    id: colorProcess
    command: [root.backend, "tick"]
    onExited: root.check()
  }
  Process {
    id: syncProcess
    command: [root.backend, "sync"]
    onExited: root.check()
  }
  IpcHandler {
    target: "io.github.olivoil.photo-theme.service"
    function status(): string { return root.lastStatus }
    function refresh(): void { root.check() }
    function sync(): void { root.sync() }
  }
}
