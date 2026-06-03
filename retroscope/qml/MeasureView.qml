pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtMultimedia
import "components"
import RetroScope 1.0

// Measurement view
Rectangle {
    id: root
    color: "transparent"

    Theme {
        id: theme
    }

    // State
    property string activeTool: "Distance"
    property bool showPxValues: false
    property string activeUnit: "µm"
    property real lineWidth: 1.5
    property int  labelFontSize: 12

    property var _cursor: ({x: 0, y: 0})

    property string sourceMode: "live"

    function selectTool(toolName) {
        activeTool = toolName
        App.measurement.resetPending()
        _repaint()
    }

    function _repaint() { drawCanvas.requestPaint() }

    Connections {
        target: App.measurement
        function onMeasurementsChanged() { root._repaint() }
        function onPendingPointsChanged() { root._repaint() }
        function onSelectedIdChanged() { root._repaint() }
    }

    // Layout
    RowLayout {
        anchors.fill: parent
        spacing: 0

        // Left: Canvas area
        Item {
                id: canvasArea
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true

                Rectangle { anchors.fill: parent; color: "#0a0a0c" }

                VideoOutput {
                    id: directMeasureVideo
                    anchors.fill: parent
                    visible: root.sourceMode === "live"
                    fillMode: VideoOutput.PreserveAspectCrop
                    onVisibleChanged: {
                        if (visible)
                            App.cameraFrameTap.setVideoSink(videoSink)
                    }
                    Component.onCompleted: {
                        if (visible)
                            App.cameraFrameTap.setVideoSink(videoSink)
                    }
                }

                // Camera / gallery image feed
                Image {
                    id: cameraImage
                    anchors.fill: parent
                    visible: root.sourceMode !== "live"
                    source: App.gallery.selectedItem.path && App.gallery.selectedItem.type !== "video"
                            ? "file://" + App.gallery.selectedItem.path : ""
                    cache: false
                    fillMode: Image.PreserveAspectCrop
                    smooth: false
                    asynchronous: false
                }

                // Drawing canvas overlay
                Canvas {
                    id: drawCanvas
                    anchors.fill: parent

                    onPaint: {
                        var ctx = getContext("2d")
                        ctx.reset()
                        ctx.clearRect(0, 0, width, height)

                        // Draw completed measurements
                        for (var i = 0; i < App.measurement.measurements.length; i++) {
                            root._drawMeasurement(
                                ctx,
                                App.measurement.measurements[i],
                                App.measurement.measurements[i].id === App.measurement.selectedId
                            )
                        }

                        // Draw pending points
                        if (App.measurement.pendingPoints.length > 0) {
                            root._drawPending(ctx)
                        }
                    }
                }

                // Mouse input
                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    acceptedButtons: Qt.LeftButton

                    onPositionChanged: function(mouse) {
                        root._cursor = { x: mouse.x, y: mouse.y }
                        root._repaint()
                    }

                    onClicked: function(mouse) {
                        App.measurement.handleClick(root.activeTool, mouse.x, mouse.y)
                    }
                }

                // Floating tool bar
                Row {
                    anchors.top: parent.top
                    anchors.left: parent.left
                    anchors.margins: 16
                    spacing: 6

                    FloatingIconButton {
                        iconCode: "\uf545"
                        toolTip: "Distance"
                        active: root.activeTool === toolTip
                        onTapped: root.selectTool(toolTip)
                    }
                    FloatingIconButton {
                        iconCode: "\uf568"
                        toolTip: "Angle"
                        active: root.activeTool === toolTip
                        onTapped: root.selectTool(toolTip)
                    }
                    FloatingIconButton {
                        iconCode: "\uf565"
                        toolTip: "Rectangle area"
                        active: root.activeTool === toolTip
                        onTapped: root.selectTool(toolTip)
                    }
                }

                // Scale bar
                ScaleBar {
                    anchors.left: parent.left
                    anchors.bottom: parent.bottom
                    anchors.margins: 16
                    umPerPixel: App.objective.umPerPixel
                }
            }

        // Right: Sidebar
        Rectangle {
            Layout.preferredWidth: 240
            Layout.fillHeight: true
            color: theme.colorSurface

            Rectangle { width: 1; height: parent.height; color: Qt.rgba(1, 1, 1, 0.06); anchors.left: parent.left }

            Flickable {
                anchors.fill: parent
                anchors.margins: 10
                contentHeight: sidebarCol.implicitHeight
                clip: true
                interactive: true
                acceptedButtons: Qt.LeftButton
                flickableDirection: Flickable.VerticalFlick
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                ColumnLayout {
                    id: sidebarCol
                    width: parent.width
                    spacing: 8

                    // Measurement header
                    Text {
                        text: "MEASUREMENTS"
                        color: theme.colorTextSub; font.pixelSize: 10; font.weight: Font.Medium; font.letterSpacing: 0.7
                        Layout.topMargin: 4; Layout.leftMargin: 4
                    }

                    // Empty state
                    Rectangle {
                        visible: App.measurement.measurements.length === 0
                        Layout.fillWidth: true
                        Layout.topMargin: 0
                        Layout.bottomMargin: 0
                        Layout.preferredHeight: 48; radius: 6
                        color: theme.bgSecondary
                        border.color: theme.colorBorder; border.width: 1
                        Text {
                            anchors.centerIn: parent
                            width: parent.width - 24
                            text: "No measurements yet.\nChoose a tool and tap the image."
                            color: theme.colorTextSub; opacity: 0.72; font.pixelSize: 11
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                        }
                    }

                    // Measurement cards
                    Repeater {
                        model: App.measurement.measurements

                        delegate: Rectangle {
                            id: cardRoot
                            required property var modelData
                            required property int index

                            Layout.fillWidth: true
                            height: cardCol.implicitHeight + 16
                            radius: 6
                            color: cardRoot.modelData.id === App.measurement.selectedId
                                   ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.08)
                                   : theme.colorSurfaceLight
                            border.color: cardRoot.modelData.id === App.measurement.selectedId
                                          ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.2)
                                          : "transparent"
                            border.width: cardRoot.modelData.id === App.measurement.selectedId ? 1 : 0

                            Rectangle {
                                width: 3; height: parent.height
                                color: cardRoot.modelData.color; anchors.left: parent.left; radius: 3
                            }

                            ColumnLayout {
                                id: cardCol
                                anchors.fill: parent; anchors.margins: 10; spacing: 3

                                RowLayout {
                                    Layout.fillWidth: true
                                    Text {
                                        text: cardRoot.modelData.type.charAt(0).toUpperCase() + cardRoot.modelData.type.slice(1) + " " + (cardRoot.index + 1)
                                        color: theme.colorTextSub; font.pixelSize: 11; font.weight: Font.Medium; Layout.fillWidth: true
                                    }
                                    Item {
                                        Layout.preferredWidth: 12; Layout.preferredHeight: 12
                                        opacity: 0.5
                                        Icon { anchors.centerIn: parent; code: "\uf00d"; iconSize: 10; color: theme.colorDanger }
                                        TapHandler {
                                            onTapped: App.measurement.deleteMeasurement(cardRoot.modelData.id)
                                        }
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    Text {
                                        text: App.measurement.formatValue(cardRoot.modelData, root.activeUnit, App.objective.umPerPixel)
                                        color: cardRoot.modelData.color; font.pixelSize: 13; font.weight: Font.Medium; font.family: "Courier New"
                                    }
                                    Item { Layout.fillWidth: true }
                                    Text {
                                        text: root.showPxValues ? App.measurement.formatSub(cardRoot.modelData) : ""
                                        color: theme.colorTextSub; font.pixelSize: 10
                                        visible: text !== ""
                                    }
                                }

                                // Row for rect dimensions
                                Text {
                                    visible: cardRoot.modelData.type === "rect"
                                    text: App.measurement.formatAux(cardRoot.modelData, root.activeUnit, App.objective.umPerPixel)
                                    color: theme.colorTextSub; font.pixelSize: 10
                                    Layout.fillWidth: true; wrapMode: Text.WordWrap
                                    Layout.topMargin: 2
                                }
                            }

                            TapHandler {
                                onTapped: App.measurement.selectMeasurement(cardRoot.modelData.id)
                            }
                        }
                    }

                    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Qt.rgba(1, 1, 1, 0.05); Layout.margins: 4 }

                    // Tool settings
                    Text {
                        text: "TOOL SETTINGS"
                        color: theme.colorTextSub; font.pixelSize: 10; font.weight: Font.Medium; font.letterSpacing: 0.7
                        Layout.leftMargin: 4
                    }

                    ColumnLayout {
                        Layout.fillWidth: true; Layout.leftMargin: 4; Layout.rightMargin: 4; spacing: 10

                        // Line width
                        RowLayout {
                            Layout.fillWidth: true
                            Text { text: "Line width"; color: theme.colorTextSub; font.pixelSize: 11; Layout.fillWidth: true }
                            Text { text: root.lineWidth.toFixed(1) + " px"; color: theme.colorTextSub; font.pixelSize: 11; font.family: "Courier New" }
                        }
                        SSlider {
                            Layout.fillWidth: true
                            from: 0.5; to: 3.5; stepSize: 0.1
                            value: root.lineWidth
                            onValueEdited: function(v) {
                                root.lineWidth = Number(v.toFixed(1))
                                root._repaint()
                            }
                        }

                        // Show px values
                        RowLayout {
                            Layout.fillWidth: true
                            Text { text: "Show px values"; color: theme.colorTextSub; font.pixelSize: 11; Layout.fillWidth: true }
                            SToggle {
                                checked: root.showPxValues
                                onToggled: function(value) { root.showPxValues = value }
                            }
                        }
                    }

                    // Units
                    Text {
                        text: "UNITS"
                        color: theme.colorTextSub; font.pixelSize: 10; font.weight: Font.Medium; font.letterSpacing: 0.7
                        Layout.leftMargin: 4; Layout.topMargin: 8
                    }

                    RowLayout {
                        Layout.fillWidth: true; spacing: 4

                        SegmentButton { label: "µm"; active: root.activeUnit === label; onTapped: root.activeUnit = label }
                        SegmentButton { label: "mm"; active: root.activeUnit === label; onTapped: root.activeUnit = label }
                        SegmentButton { label: "px"; active: root.activeUnit === label; onTapped: root.activeUnit = label }
                    }

                    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Qt.rgba(1, 1, 1, 0.05); Layout.margins: 4 }

                    // Actions
                    ColumnLayout {
                        Layout.fillWidth: true; spacing: 6

                        RowLayout {
                            Layout.fillWidth: true; spacing: 6
                            ActionButton {
                                label: "Export image"
                                onTapped: {
                                    canvasArea.grabToImage(function(result) {
                                        var path = App.saveMeasurementImage(result.image)
                                        if (path !== "")
                                            console.log("Exported image: " + path)
                                    })
                                }
                            }
                        }

                        ActionButton {
                            label: "Clear all measurements"
                            textColor: theme.colorDanger
                            bgColor: Qt.rgba(theme.colorDanger.r, theme.colorDanger.g, theme.colorDanger.b, 0.06)
                            borderColor: Qt.rgba(theme.colorDanger.r, theme.colorDanger.g, theme.colorDanger.b, 0.2)
                            onTapped: App.measurement.clearMeasurements()
                        }
                    }

                    // Bottom spacer
                    Item { Layout.fillHeight: true }
                }
            }
        }
    }

    // Canvas drawing functions
    function _drawMeasurement(ctx, m, selected) {
        ctx.strokeStyle = m.color
        ctx.lineWidth = root.lineWidth
        ctx.fillStyle = m.color
        ctx.font = root.labelFontSize + "px monospace"

        if (selected) {
            ctx.shadowColor = m.color
            ctx.shadowBlur = 6
        } else {
            ctx.shadowColor = "transparent"
            ctx.shadowBlur = 0
        }

        if (m.type === "distance") _drawDistance(ctx, m)
        else if (m.type === "angle") _drawAngle(ctx, m)
        else if (m.type === "rect") _drawRect(ctx, m)

        ctx.shadowColor = "transparent"
        ctx.shadowBlur = 0
    }

    function _drawDistance(ctx, m) {
        var p1 = m.points[0], p2 = m.points[1]
        ctx.beginPath()
        ctx.moveTo(p1.x, p1.y)
        ctx.lineTo(p2.x, p2.y)
        ctx.stroke()

        // Endpoint circles
        _drawDot(ctx, p1, m.color)
        _drawDot(ctx, p2, m.color)

        // Label at midpoint
        var mid = { x: (p1.x + p2.x) / 2, y: (p1.y + p2.y) / 2 }
        var label = App.measurement.formatValue(m, root.activeUnit, App.objective.umPerPixel)
        if (showPxValues) label += "  (" + App.measurement.formatSub(m) + ")"
        _drawLabel(ctx, mid.x, mid.y - 10, label, m.color)
    }

    function _drawAngle(ctx, m) {
        var p1 = m.points[0], vertex = m.points[1], p2 = m.points[2]

        // Two lines from vertex
        ctx.beginPath()
        ctx.moveTo(p1.x, p1.y); ctx.lineTo(vertex.x, vertex.y)
        ctx.moveTo(vertex.x, vertex.y); ctx.lineTo(p2.x, p2.y)
        ctx.stroke()

        _drawDot(ctx, p1, m.color)
        _drawDot(ctx, vertex, m.color)
        _drawDot(ctx, p2, m.color)

        // Arc indicator
        var a1 = Math.atan2(p1.y - vertex.y, p1.x - vertex.x)
        var a2 = Math.atan2(p2.y - vertex.y, p2.x - vertex.x)
        var r = 25
        ctx.beginPath()
        ctx.arc(vertex.x, vertex.y, r, Math.min(a1, a2), Math.max(a1, a2))
        ctx.stroke()

        // Label
        var labelX = vertex.x + r * 1.4 * Math.cos((a1 + a2) / 2)
        var labelY = vertex.y + r * 1.4 * Math.sin((a1 + a2) / 2)
        _drawLabel(ctx, labelX, labelY, App.measurement.formatValue(m, root.activeUnit, App.objective.umPerPixel), m.color)
    }

    function _drawRect(ctx, m) {
        var p1 = m.points[0], p2 = m.points[1]
        var x = Math.min(p1.x, p2.x), y = Math.min(p1.y, p2.y)
        var w = Math.abs(p2.x - p1.x), h = Math.abs(p2.y - p1.y)

        ctx.setLineDash([6, 4])
        ctx.beginPath()
        ctx.rect(x, y, w, h)
        ctx.stroke()
        ctx.setLineDash([])

        _drawDot(ctx, { x: x, y: y }, m.color)
        _drawDot(ctx, { x: x + w, y: y }, m.color)
        _drawDot(ctx, { x: x, y: y + h }, m.color)
        _drawDot(ctx, { x: x + w, y: y + h }, m.color)

        _drawLabel(ctx, x + w / 2, y + h / 2, App.measurement.formatValue(m, root.activeUnit, App.objective.umPerPixel), m.color)
    }

    function _drawDot(ctx, pt, color) {
        ctx.fillStyle = color
        ctx.beginPath()
        ctx.arc(pt.x, pt.y, 4, 0, 2 * Math.PI)
        ctx.fill()
    }

    function _drawLabel(ctx, x, y, text, color) {
        if (!text || text === "") return
        ctx.font = root.labelFontSize + "px monospace"
        var metrics = ctx.measureText(text)
        var tw = metrics.width
        var th = root.labelFontSize
        var pad = 4

        // Background
        ctx.fillStyle = "rgba(0, 0, 0, 0.7)"
        _roundRect(ctx, x - tw / 2 - pad, y - th / 2 - pad, tw + pad * 2, th + pad * 2, 4)
        ctx.fill()

        // Text
        ctx.fillStyle = color
        ctx.textAlign = "center"
        ctx.textBaseline = "middle"
        ctx.fillText(text, x, y)
    }

    function _roundRect(ctx, x, y, w, h, r) {
        ctx.beginPath()
        ctx.moveTo(x + r, y)
        ctx.lineTo(x + w - r, y)
        ctx.quadraticCurveTo(x + w, y, x + w, y + r)
        ctx.lineTo(x + w, y + h - r)
        ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h)
        ctx.lineTo(x + r, y + h)
        ctx.quadraticCurveTo(x, y + h, x, y + h - r)
        ctx.lineTo(x, y + r)
        ctx.quadraticCurveTo(x, y, x + r, y)
        ctx.closePath()
    }

    function _drawPending(ctx) {
        var pts = App.measurement.pendingPoints
        var cur = root._cursor
        var color = App.measurement.colorForType(App.measurement.toolType(root.activeTool))

        ctx.strokeStyle = color
        ctx.lineWidth = root.lineWidth
        ctx.fillStyle = color

        // Draw placed points
        for (var i = 0; i < pts.length; i++) _drawDot(ctx, pts[i], color)

        if (activeTool === "Distance") {
            if (pts.length === 1) {
                ctx.beginPath()
                ctx.moveTo(pts[0].x, pts[0].y)
                ctx.lineTo(cur.x, cur.y)
                ctx.stroke()
                // Live distance label
                var d = App.measurement.distanceUm(pts[0], cur, App.objective.umPerPixel)
                var mid = { x: (pts[0].x + cur.x) / 2, y: (pts[0].y + cur.y) / 2 }
                _drawLabel(ctx, mid.x, mid.y - 10, App.measurement.formatLength(d, root.activeUnit, App.objective.umPerPixel), color)
            }
        } else if (activeTool === "Angle") {
            if (pts.length >= 1) {
                ctx.beginPath()
                ctx.moveTo(pts[0].x, pts[0].y)
                if (pts.length >= 2) {
                    ctx.lineTo(pts[1].x, pts[1].y)
                    ctx.stroke()
                    ctx.beginPath()
                    ctx.moveTo(pts[1].x, pts[1].y)
                }
                ctx.lineTo(cur.x, cur.y)
                ctx.stroke()
                if (pts.length === 2) {
                    var deg = App.measurement.angleDeg(pts[0], pts[1], cur)
                    _drawLabel(ctx, pts[1].x + 30, pts[1].y - 10, deg.toFixed(1) + "°", color)
                }
            }
        } else if (activeTool === "Rectangle area") {
            if (pts.length === 1) {
                var rx = Math.min(pts[0].x, cur.x), ry = Math.min(pts[0].y, cur.y)
                var rw = Math.abs(cur.x - pts[0].x), rh = Math.abs(cur.y - pts[0].y)
                ctx.setLineDash([6, 4])
                ctx.beginPath()
                ctx.rect(rx, ry, rw, rh)
                ctx.stroke()
                ctx.setLineDash([])
            }
        }

        // Cursor circle
        ctx.strokeStyle = Qt.rgba(1, 1, 1, 0.3)
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.arc(cur.x, cur.y, 8, 0, 2 * Math.PI)
        ctx.stroke()
    }
}
