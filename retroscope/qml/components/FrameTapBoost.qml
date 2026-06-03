pragma ComponentBehavior: Bound
import QtQuick
import RetroScope 1.0

QtObject {
    id: root

    property int targetFps: 12
    property bool active: false
    property int restoreFps: 0

    function start() {
        var configuredFps = Math.max(1, App.settings.cameraFps)
        if (!active) {
            restoreFps = configuredFps
            active = true
        }

        App.cameraFrameTap.setCameraFps(Math.max(targetFps, restoreFps))
    }

    function stop() {
        if (!active)
            return

        var fps = restoreFps > 0 ? restoreFps : Math.max(1, App.settings.cameraFps)
        active = false
        restoreFps = 0

        App.cameraFrameTap.setCameraFps(fps)
    }
}
