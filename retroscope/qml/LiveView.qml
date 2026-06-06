pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtMultimedia
import "components"
import RetroScope 1.0

Item {
    id: root

    Theme { id: theme }

    property real   _focusRawScore: 0
    property string _focusSource: ""
    property bool   _objSwitchVisible: false
    readonly property bool cameraLive: App.cameraFrameTap.cameraConnected

    function _pointInItem(point, item, margin) {
        if (!item || !item.visible)
            return false
        margin = margin || 0
        var p = item.mapFromItem(stageInputSurface, point.x, point.y)
        return p.x >= -margin && p.x <= item.width + margin &&
               p.y >= -margin && p.y <= item.height + margin
    }

    function _stageInputBlockedAt(point) {
        return root._objSwitchVisible ||
               root._pointInItem(point, toolRow, 10) ||
               root._pointInItem(point, focusBadge, 10)
    }

    function _formatFocusScore(value) {
        var v = Math.max(0, Number(value))
        if (v >= 1000000)
            return (v / 1000000).toFixed(1) + "M"
        if (v >= 1000)
            return (v / 1000).toFixed(1) + "k"
        return v.toFixed(0)
    }

    Connections {
        target: App
        function onFocus_score_updated(score) { root._focusRawScore = score }
        function onFocus_source_updated(source) { root._focusSource = source }
    }

    Connections {
        target: App.objDetector
        function onSwitchDetected() { root._objSwitchVisible = true }
    }

    VideoOutput {
        id: directVideoOutput
        anchors.fill: parent
        visible: true
        fillMode: VideoOutput.PreserveAspectCrop
        onVisibleChanged: {
            if (visible)
                directSinkBindTimer.start()
        }
        Component.onCompleted: {
            directSinkBindTimer.start()
        }
    }

    Rectangle {
        id: cameraPlaceholder
        anchors.fill: parent
        visible: !root.cameraLive
        color: theme.dark ? "#05070a" : "#eef2f5"

        Column {
            anchors.centerIn: parent
            spacing: 12
            width: Math.min(parent.width - 48, 360)

            Icon {
                anchors.horizontalCenter: parent.horizontalCenter
                code: "\uf4e2"
                iconSize: 44
                color: theme.colorTextSub
                opacity: 0.8
            }

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                width: parent.width
                text: "Waiting for video input"
                color: theme.colorTextSub
                font.pixelSize: 12
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
            }
        }
    }

    Timer {
        id: directSinkBindTimer
        interval: 500
        repeat: true
        running: false
        property int attempts: 0
        onTriggered: {
            attempts += 1
            App.cameraFrameTap.setVideoSink(directVideoOutput.videoSink)
            if (App.cameraFrameTap.frameTapCount > 0 || attempts >= 20)
                stop()
        }
    }

    // Grid overlay
    Canvas {
        id: gridCanvas
        anchors.fill: parent
        visible: root.cameraLive && App.overlay.gridVisible
        opacity: 0.6

        onVisibleChanged: requestPaint()
        onWidthChanged:   requestPaint()
        onHeightChanged:  requestPaint()

        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            ctx.strokeStyle = Qt.rgba(1, 1, 1, 0.18)
            ctx.lineWidth = 1

            var cols = 8
            var rows = 6
            ctx.beginPath()
            for (var c = 1; c < cols; c++) {
                var x = width * c / cols
                ctx.moveTo(x, 0); ctx.lineTo(x, height)
            }
            for (var r = 1; r < rows; r++) {
                var y = height * r / rows
                ctx.moveTo(0, y); ctx.lineTo(width, y)
            }
            ctx.stroke()
        }
    }

    // Crosshair overlay
    Crosshair {
        anchors.fill: parent
        visible: root.cameraLive && App.overlay.crosshairVisible
        lineColor: theme.colorAccent
        lineWidth: 1
    }

    // Scale bar overlay
    ScaleBar {
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.margins: 16
        visible: root.cameraLive
        umPerPixel: App.objective.umPerPixel
    }

    // Touch stage movement, single tap to bring the tapped point to the centre
    Item {
        id: stageInputSurface
        anchors.fill: parent
        enabled: root.cameraLive

        TapHandler {
            id: stageTap
            acceptedButtons: Qt.LeftButton
            gesturePolicy: TapHandler.WithinBounds
            onTapped: function(eventPoint) {
                if (root._stageInputBlockedAt(eventPoint.position)) return
                var fr = directVideoOutput.sourceRect
                if (!(fr.width > 0 && fr.height > 0)) return
                var cover = Math.max(root.width / fr.width, root.height / fr.height)
                var frameDx = (eventPoint.position.x - root.width  / 2) / cover
                var frameDy = (eventPoint.position.y - root.height / 2) / cover
                App.motion.moveByFramePixels(frameDx, frameDy)
            }
        }
    }

    // Top-left floating tools
    Row {
        id: toolRow
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.margins: 16
        spacing: 6
        visible: root.cameraLive

        // Crosshair Tool
        Rectangle {
            width: 32; height: 32; radius: 8
            color: App.overlay.crosshairVisible
                   ? theme.colorAccentFill
                   : theme.floatingButtonBg
            border.color: App.overlay.crosshairVisible
                          ? theme.colorAccentFill
                          : theme.floatingButtonBorder
            border.width: 1

            Icon { anchors.centerIn: parent; code: "\uf05b"; iconSize: 14; color: App.overlay.crosshairVisible ? "#ffffff" : theme.colorText }
            TapHandler {
                onTapped: App.overlay.setCrosshairVisible(!App.overlay.crosshairVisible)
            }
        }

        // Grid Tool
        Rectangle {
            width: 32; height: 32; radius: 8
            color: App.overlay.gridVisible
                   ? theme.colorAccentFill
                   : theme.floatingButtonBg
            border.color: App.overlay.gridVisible
                          ? theme.colorAccentFill
                          : theme.floatingButtonBorder
            border.width: 1

            Icon { anchors.centerIn: parent; code: "\uf84c"; iconSize: 14; color: App.overlay.gridVisible ? "#ffffff" : theme.colorText }
            TapHandler {
                onTapped: App.overlay.setGridVisible(!App.overlay.gridVisible)
            }
        }

    }

    // Bottom-right focus quality badge
    Rectangle {
        id: focusBadge
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        anchors.margins: 16
        visible: root.cameraLive
        height: 24
        width: focusLayout.implicitWidth + 16
        radius: 6
        color: theme.floatingButtonBg
        border.color: theme.floatingButtonBorder
        border.width: 1

        RowLayout {
            id: focusLayout
            anchors.centerIn: parent
            spacing: 6
            Text {
                text: "Focus: " + root._formatFocusScore(root._focusRawScore) + (root._focusSource === "analysis" ? " low" : "")
                color: theme.dark ? theme.colorAccentLight : theme.colorAccent
                font.pixelSize: 11
                font.weight: Font.Medium
            }
        }
    }

    // Objective-switch popup overlay (Shown when the camera goes dark, then recovers. Objective detection)
    Rectangle {
        id: _objSwitchPopup
        anchors.fill: parent
        visible: root.cameraLive && root._objSwitchVisible
        color: Qt.rgba(0, 0, 0, 0.78)
        z: 100

        // Dismiss without selecting (tap outside the card)
        TapHandler {
            onTapped: {
                root._objSwitchVisible = false
                App.objDetector.cancel()
            }
        }

        Column {
            anchors.centerIn: parent
            spacing: 20

            // Title
            Column {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 4
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Objective changed?"
                    color: "white"
                    font.pixelSize: 18
                    font.weight: Font.Medium
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Tap the new objective to confirm"
                    color: Qt.rgba(1, 1, 1, 0.55)
                    font.pixelSize: 13
                }
            }

            // Objective buttons
            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 12

                Repeater {
                    model: App.objective.objectiveNames
                    delegate: Rectangle {
                        id: objectiveTile
                        required property string modelData
                        required property int index
                        width: 72; height: 72; radius: 14
                        property bool active: App.objective.activeObjective === objectiveTile.modelData
                        color: active
                               ? Qt.rgba(theme.colorAccentFill.r, theme.colorAccentFill.g, theme.colorAccentFill.b, 0.92)
                               : Qt.rgba(1, 1, 1, 0.13)
                        border.color: active ? theme.colorAccent : Qt.rgba(1, 1, 1, 0.28)
                        border.width: active ? 2 : 1

                        Column {
                            anchors.centerIn: parent
                            spacing: 2
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: App.objective.objectiveDisplayNames[objectiveTile.index] ?? objectiveTile.modelData
                                color: "white"
                                font.pixelSize: 18
                                font.weight: Font.Bold
                            }
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: objectiveTile.active ? "current" : ""
                                color: Qt.rgba(1, 1, 1, 0.55)
                                font.pixelSize: 9
                            }
                        }

                        TapHandler {
                            onTapped: {
                                App.objective.select(objectiveTile.modelData)
                                if (App.objDetector.autofocusOnSwitch)
                                    App.autofocus.startAutofocus()
                                root._objSwitchVisible = false
                                App.objDetector.cancel()
                            }
                        }
                    }
                }
            }

            // No-change button
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                width: 160; height: 40; radius: 10
                color: Qt.rgba(1, 1, 1, 0.10)
                border.color: Qt.rgba(1, 1, 1, 0.28)
                border.width: 1

                Text {
                    anchors.centerIn: parent
                    text: "No change"
                    color: Qt.rgba(1, 1, 1, 0.75)
                    font.pixelSize: 13
                }

                TapHandler {
                    onTapped: {
                        root._objSwitchVisible = false
                        App.objDetector.cancel()
                    }
                }
            }
        }
    }
}
