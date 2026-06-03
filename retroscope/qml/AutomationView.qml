pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components"
import RetroScope 1.0

Item {
    id: root

    property int currentSubTab: 0

    Theme {
        id: theme
    }

    // Focus stack config
    property int    fsStepSize:   5
    property int    fsSettleMs:   1000
    property string fsBlending:   "laplacian"
    property int    fsZStart:     App.motion.posZ
    property int    fsZEnd:       App.motion.posZ
    readonly property int  _stagePosZ:    App.motion.posZ

    // Tile scan config
    property int    tsCols:           4
    property int    tsRows:           4
    property int    tsOverlapPct:     20
    property string tsPattern:        "raster"
    property bool   tsAutofocusEach:  false
    property bool   tsRecordVideo:    false
    property bool   tsStitchAfter:    true
    property int    tsSettleMs:       1000

    // Estimate display values
    readonly property int fsTotalSteps: App.automation.focusStackTotalSteps(fsZStart, fsZEnd)
    readonly property int fsFrameCount: App.automation.focusStackFrameCount(fsZStart, fsZEnd, fsStepSize)
    readonly property int fsPreviewLines: App.automation.focusStackPreviewLines(fsZStart, fsZEnd, fsStepSize)
    readonly property int fsEstimateSeconds: App.automation.estimateFocusStackSeconds(fsZStart, fsZEnd, fsStepSize, fsSettleMs)
    readonly property int tsTileCount: App.automation.tileCount(tsCols, tsRows)
    readonly property int tsEstimateSeconds: App.automation.estimateTileScanSeconds(tsCols, tsRows, tsSettleMs)

    function applyObjectiveDefaults() {
        fsStepSize = Math.max(1, App.objective.activeFocusStackStep)
        if (fsStepSizeSlider)
            fsStepSizeSlider.setValue(fsStepSize)
    }

    Component.onCompleted: {
        fsZStart = root._stagePosZ
        fsZEnd = root._stagePosZ
        applyObjectiveDefaults()
    }

    Connections {
        target: App.objective
        function onParams_changed() {
            if (fsUseDefaults.checked)
                root.applyObjectiveDefaults()
        }
        function onObjective_changed() {
            if (fsUseDefaults.checked)
                root.applyObjectiveDefaults()
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // Left: Main content
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            StackLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.leftMargin: 16; Layout.rightMargin: 16
                Layout.topMargin: 16;  Layout.bottomMargin: 16
                currentIndex: root.currentSubTab

                // Tab 0: Focus stack
                TouchScrollView {
                    id: focusStackScroll
                    Layout.fillWidth: true; Layout.fillHeight: true
                    clip: true
                    contentWidth: availableWidth
                    ScrollBar.vertical.policy: ScrollBar.AsNeeded

                    property int mainRowHeight: Math.max(290, Math.min(680, Math.round(availableHeight - 64)))

                    ColumnLayout {
                        width: focusStackScroll.availableWidth
                        spacing: 14

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.preferredHeight: focusStackScroll.mainRowHeight
                        spacing: 14

                        ColumnLayout {
                            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 10

                            Rectangle {
                                Layout.fillWidth: true; implicitHeight: 116
                                color: theme.colorSurface; radius: 8; border.color: theme.colorBorder
                                ColumnLayout {
                                    anchors.fill: parent; anchors.margins: 14; spacing: 8

                                    RowLayout {
                                        Layout.fillWidth: true
                                        Text { text: "Z RANGE"; color: theme.colorTextSub; font.pixelSize: 10; font.weight: Font.Medium; font.letterSpacing: 0.7 }
                                        Item { Layout.fillWidth: true }
                                        Text {
                                            text: root.fsTotalSteps + " steps · " + root.fsFrameCount + " frames"
                                            color: theme.colorAccent
                                            font.pixelSize: 10; font.weight: Font.Medium; font.family: "Courier New"
                                        }
                                    }

                                    // START row
                                    RowLayout {
                                        Layout.fillWidth: true; spacing: 10
                                        Text {
                                            text: "Start"; color: theme.colorTextSub; font.pixelSize: 11
                                            Layout.preferredWidth: 38
                                        }
                                        Rectangle {
                                            Layout.fillWidth: true; Layout.preferredHeight: 30; radius: 6
                                            color: theme.colorSurfaceLight; border.color: theme.colorBorder
                                            Text {
                                                text: "Z " + root.fsZStart
                                                color: theme.colorAccent
                                                font.pixelSize: 12; font.family: "Courier New"
                                                anchors.centerIn: parent
                                            }
                                        }
                                        Rectangle {
                                            Layout.preferredWidth: 70; Layout.preferredHeight: 30; radius: 6
                                            color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.1)
                                            border.color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.25)
                                            Text {
                                                text: "Current Z"
                                                color: theme.colorAccent
                                                font.pixelSize: 10; font.weight: Font.Medium
                                                anchors.centerIn: parent
                                            }
                                            TapHandler { onTapped: root.fsZStart = root._stagePosZ }
                                        }
                                    }
                                    // END row

                                    RowLayout {
                                        Layout.fillWidth: true; spacing: 10
                                        Text {
                                            text: "End"; color: theme.colorTextSub; font.pixelSize: 11
                                            Layout.preferredWidth: 38
                                        }
                                        Rectangle {
                                            Layout.fillWidth: true; Layout.preferredHeight: 30; radius: 6
                                            color: theme.colorSurfaceLight; border.color: theme.colorBorder
                                            Text {
                                                text: "Z " + root.fsZEnd
                                                color: theme.colorAccent
                                                font.pixelSize: 12; font.family: "Courier New"
                                                anchors.centerIn: parent
                                            }
                                        }
                                        Rectangle {
                                            Layout.preferredWidth: 70; Layout.preferredHeight: 30; radius: 6
                                            color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.1)
                                            border.color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.25)
                                            Text {
                                                text: "Current Z"
                                                color: theme.colorAccent
                                                font.pixelSize: 10; font.weight: Font.Medium
                                                anchors.centerIn: parent
                                            }
                                            TapHandler { onTapped: root.fsZEnd = root._stagePosZ }
                                        }
                                    }
                                }
                            }

                            // Step card
                            Rectangle {
                                Layout.fillWidth: true; implicitHeight: 160
                                color: theme.colorSurface; radius: 8; border.color: theme.colorBorder
                                ColumnLayout {
                                    anchors.fill: parent; anchors.margins: 14; spacing: 10
                                    Text { text: "STEP"; color: theme.colorTextSub; font.pixelSize: 10; font.weight: Font.Medium; font.letterSpacing: 0.7 }

                                    SliderRow {
                                        id: fsStepSizeSlider
                                        label: "Step size"; from: 1; to: 500; value: root.fsStepSize; decimals: 0; unit: "steps"
                                        readOnly: fsUseDefaults.checked
                                        onValueChanged: { var v = Math.round(value); if (v !== root.fsStepSize) root.fsStepSize = v }
                                    }

                                    SliderRow {
                                        id: fsSettleSlider
                                        label: "Settle delay"; from: 1000; to: 3000; value: root.fsSettleMs; decimals: 0; unit: "ms"
                                        onValueChanged: { var v = Math.round(value); if (v !== root.fsSettleMs) root.fsSettleMs = v }
                                    }

                                    ToggleRow {
                                        id: fsUseDefaults
                                        label: "Use objective defaults"
                                        checked: true
                                        onCheckedChanged: if (checked) root.applyObjectiveDefaults()
                                    }

                                    Item { Layout.fillHeight: true }
                                }
                            }

                            Item { Layout.fillHeight: true }
                        }

                        // Middle col: Output
                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            spacing: 10

                            Rectangle {
                                Layout.fillWidth: true; implicitHeight: 95
                                color: theme.colorSurface; radius: 8; border.color: theme.colorBorder
                                ColumnLayout {
                                    anchors.fill: parent; anchors.margins: 14; spacing: 10
                                    Text { text: "OUTPUT"; color: theme.colorTextSub; font.pixelSize: 10; font.weight: Font.Medium; font.letterSpacing: 0.7 }

                                    ColumnLayout {
                                        Layout.fillWidth: true; spacing: 5
                                        Text { text: "Blending mode"; color: theme.colorTextSub; font.pixelSize: 11 }
                                        RowLayout {
                                            Layout.fillWidth: true; spacing: 5
                                            Rectangle {
                                                Layout.fillWidth: true; Layout.preferredHeight: 26; radius: 5
                                                color: root.fsBlending === "laplacian"
                                                       ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12)
                                                       : theme.bgSecondary
                                                border.color: root.fsBlending === "laplacian"
                                                              ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.3)
                                                              : "transparent"
                                                Text {
                                                    text: "Laplacian"
                                                    color: root.fsBlending === "laplacian" ? theme.colorAccent : theme.colorTextSub
                                                    font.pixelSize: 10; font.weight: root.fsBlending === "laplacian" ? Font.Medium : Font.Normal
                                                    anchors.centerIn: parent
                                                }
                                                MouseArea { anchors.fill: parent; onClicked: root.fsBlending = "laplacian" }
                                            }
                                            Rectangle {
                                                Layout.fillWidth: true; Layout.preferredHeight: 26; radius: 5
                                                color: root.fsBlending === "average"
                                                       ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12)
                                                       : theme.bgSecondary
                                                border.color: root.fsBlending === "average"
                                                              ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.3)
                                                              : "transparent"
                                                Text {
                                                    text: "Average"
                                                    color: root.fsBlending === "average" ? theme.colorAccent : theme.colorTextSub
                                                    font.pixelSize: 10; font.weight: root.fsBlending === "average" ? Font.Medium : Font.Normal
                                                    anchors.centerIn: parent
                                                }
                                                MouseArea { anchors.fill: parent; onClicked: root.fsBlending = "average" }
                                            }
                                        }
                                    }

                                    Item { Layout.fillHeight: true }
                                }
                            }

                            Item { Layout.fillHeight: true }
                        }

                        // Right col: Z Preview
                        Rectangle {
                            Layout.preferredWidth: 120; Layout.minimumWidth: 120; Layout.maximumWidth: 120; Layout.fillHeight: true
                            Layout.preferredHeight: focusStackScroll.mainRowHeight
                            color: theme.colorSurface; radius: 8; border.color: theme.colorBorder
                            ColumnLayout {
                                anchors.fill: parent; anchors.margins: 14; spacing: 6
                                Text { text: "Z PREVIEW"; color: theme.colorTextSub; font.pixelSize: 10; font.weight: Font.Medium; font.letterSpacing: 0.7; Layout.alignment: Qt.AlignHCenter }

                                Rectangle {
                                    id: zPreviewBar
                                    Layout.fillWidth: true; Layout.fillHeight: true; Layout.alignment: Qt.AlignHCenter
                                    color: theme.colorSurfaceLight; radius: 4

                                    Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.topMargin: parent.height*0.1; height: parent.height*0.8; color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.1); radius: 3 }
                                    Rectangle { width: parent.width + 6; x: -3; height: 2; color: theme.colorAccent; y: zPreviewBar.height*0.1 }
                                    Rectangle { width: parent.width + 6; x: -3; height: 2; color: theme.colorAccent; y: zPreviewBar.height*0.9 }
                                    Rectangle { width: parent.width + 6; x: -3; height: 2; color: theme.colorWarning; y: zPreviewBar.height*0.5 }

                                    Repeater {
                                        model: root.fsPreviewLines
                                        Rectangle {
                                            required property int index
                                            width: 10; height: 1
                                            color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.5)
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            y: zPreviewBar.height * (0.12 + index * (0.76 / Math.max(root.fsPreviewLines - 1, 1)))
                                        }
                                    }
                                }

                                Column {
                                    Layout.alignment: Qt.AlignHCenter; spacing: 2
                                    Text { text: root.fsTotalSteps + " steps"; color: theme.colorTextSub; font.pixelSize: 9; anchors.horizontalCenter: parent.horizontalCenter }
                                    Text { text: root.fsFrameCount + " frames"; color: theme.colorAccent; font.pixelSize: 10; font.weight: Font.Medium; anchors.horizontalCenter: parent.horizontalCenter }
                                }
                            }
                        }
                    }

                    // Bottom Info Bar
                    Rectangle {
                        Layout.fillWidth: true; Layout.preferredHeight: 50
                        color: theme.colorSurface; radius: 6; border.color: theme.colorBorder
                        RowLayout {
                            anchors.left: parent.left; anchors.right: parent.right
                            anchors.top: parent.top; anchors.bottom: parent.bottom
                            anchors.leftMargin: 14; anchors.rightMargin: 14
                            anchors.topMargin: 8; anchors.bottomMargin: 8
                            spacing: 16
                            Column { Layout.alignment: Qt.AlignVCenter; Text { text: "Frames";     color: theme.colorTextSub; font.pixelSize: 10 } Text { text: root.fsFrameCount + ""; color: theme.colorText; font.pixelSize: 11; font.family: "Courier New" } }
                            Rectangle { implicitWidth: 1; implicitHeight: 24; color: theme.colorSurfaceLight }
                            Column { Layout.alignment: Qt.AlignVCenter; Text { text: "Est. time";  color: theme.colorTextSub; font.pixelSize: 10 } Text { text: "~" + root.fsEstimateSeconds + " s"; color: theme.colorText; font.pixelSize: 11; font.family: "Courier New" } }
                            Rectangle { implicitWidth: 1; implicitHeight: 24; color: theme.colorSurfaceLight }
                            Column { Layout.alignment: Qt.AlignVCenter; Text { text: "Range";      color: theme.colorTextSub; font.pixelSize: 10 } Text { text: root.fsTotalSteps + " steps"; color: theme.colorText; font.pixelSize: 11; font.family: "Courier New" } }
                            Rectangle { implicitWidth: 1; implicitHeight: 24; color: theme.colorSurfaceLight }
                            Column { Layout.alignment: Qt.AlignVCenter; Text { text: "Step";       color: theme.colorTextSub; font.pixelSize: 10 } Text { text: root.fsStepSize + " steps"; color: theme.colorText; font.pixelSize: 11; font.family: "Courier New" } }
                        }
                    }
                    }
                } // End Tab 0

                // Tab 1: Tile scan
                TouchScrollView {
                    id: tileScanScroll
                    Layout.fillWidth: true; Layout.fillHeight: true
                    clip: true
                    contentWidth: availableWidth
                    ScrollBar.vertical.policy: ScrollBar.AsNeeded

                    ColumnLayout {
                        width: tileScanScroll.availableWidth
                        spacing: 14

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 14

                        // Left: Settings
                        ColumnLayout {
                            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 10

                            // Grid Card
                            Rectangle {
                                Layout.fillWidth: true; implicitHeight: 130
                                color: theme.colorSurface; radius: 8; border.color: theme.colorBorder
                                ColumnLayout {
                                    anchors.fill: parent; anchors.margins: 14; spacing: 10
                                    Text { text: "GRID"; color: theme.colorTextSub; font.pixelSize: 10; font.weight: Font.Medium; font.letterSpacing: 0.7 }

                                    RowLayout {
                                        Layout.fillWidth: true; spacing: 14

                                        ColumnLayout {
                                            Layout.fillWidth: true; spacing: 3
                                            Text { text: "Columns"; color: theme.colorTextSub; font.pixelSize: 10 }
                                            Stepper {
                                                value: root.tsCols; minVal: 1; maxVal: 20; step: 1
                                                onValueChanged: root.tsCols = value
                                            }
                                        }
                                        ColumnLayout {
                                            Layout.fillWidth: true; spacing: 3
                                            Text { text: "Rows"; color: theme.colorTextSub; font.pixelSize: 10 }
                                            Stepper {
                                                value: root.tsRows; minVal: 1; maxVal: 20; step: 1
                                                onValueChanged: root.tsRows = value
                                            }
                                        }
                                        ColumnLayout {
                                            Layout.fillWidth: true; spacing: 3
                                            Text { text: "Total tiles"; color: theme.colorTextSub; font.pixelSize: 10 }
                                            Rectangle {
                                                Layout.fillWidth: true; Layout.preferredHeight: 26; radius: 5
                                                color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.08)
                                                Text {
                                                    text: root.tsTileCount + ""
                                                    color: theme.colorAccent; font.pixelSize: 11; font.family: "Courier New"
                                                    anchors.centerIn: parent
                                                }
                                            }
                                        }
                                    }

                                    SliderRow {
                                        id: tsOverlapSlider
                                        label: "Overlap"; from: 0; to: 50; value: root.tsOverlapPct; decimals: 0; unit: "%"
                                        onValueChanged: { var v = Math.round(value); if (v !== root.tsOverlapPct) root.tsOverlapPct = v }
                                    }
                                }
                            }

                            // Scan Pattern Card
                            Rectangle {
                                Layout.fillWidth: true; implicitHeight: 110
                                color: theme.colorSurface; radius: 8; border.color: theme.colorBorder
                                ColumnLayout {
                                    anchors.fill: parent; anchors.margins: 14; spacing: 8
                                    Text { text: "SCAN PATTERN"; color: theme.colorTextSub; font.pixelSize: 10; font.weight: Font.Medium; font.letterSpacing: 0.7 }
                                    RowLayout {
                                        Layout.fillWidth: true; spacing: 6
                                        Rectangle {
                                            Layout.fillWidth: true; Layout.preferredHeight: 26; radius: 5
                                            color: root.tsPattern === "serpentine"
                                                   ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12)
                                                   : theme.bgSecondary
                                            border.color: root.tsPattern === "serpentine"
                                                          ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.3)
                                                          : "transparent"
                                            Text {
                                                text: "Serpentine"
                                                color: root.tsPattern === "serpentine" ? theme.colorAccent : theme.colorTextSub
                                                font.pixelSize: 10; font.weight: root.tsPattern === "serpentine" ? Font.Medium : Font.Normal
                                                anchors.centerIn: parent
                                            }
                                            MouseArea { anchors.fill: parent; onClicked: root.tsPattern = "serpentine" }
                                        }
                                        Rectangle {
                                            Layout.fillWidth: true; Layout.preferredHeight: 26; radius: 5
                                            color: root.tsPattern === "raster"
                                                   ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12)
                                                   : theme.bgSecondary
                                            border.color: root.tsPattern === "raster"
                                                          ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.3)
                                                          : "transparent"
                                            Text {
                                                text: "Raster"
                                                color: root.tsPattern === "raster" ? theme.colorAccent : theme.colorTextSub
                                                font.pixelSize: 10; font.weight: root.tsPattern === "raster" ? Font.Medium : Font.Normal
                                                anchors.centerIn: parent
                                            }
                                            MouseArea { anchors.fill: parent; onClicked: root.tsPattern = "raster" }
                                        }
                                    }
                                    SliderRow {
                                        id: tsSettleSlider
                                        label: "Settle delay"; from: 1000; to: 3000; value: root.tsSettleMs; decimals: 0; unit: "ms"
                                        onValueChanged: { var v = Math.round(value); if (v !== root.tsSettleMs) root.tsSettleMs = v }
                                    }
                                    Item { Layout.preferredHeight: 4 }
                                }
                            }

                            // Per-Tile Options Card
                            Rectangle {
                                Layout.fillWidth: true; implicitHeight: 125
                                color: theme.colorSurface; radius: 8; border.color: theme.colorBorder
                                ColumnLayout {
                                    anchors.fill: parent; anchors.margins: 14; spacing: 10
                                    Text { text: "PER-TILE OPTIONS"; color: theme.colorTextSub; font.pixelSize: 10; font.weight: Font.Medium; font.letterSpacing: 0.7 }
                                    ToggleRow { label: "Autofocus each tile";  enabled: !root.tsRecordVideo; checked: root.tsAutofocusEach;  onCheckedChanged: root.tsAutofocusEach  = checked }
                                    ToggleRow { label: "Stitch after scan";     enabled: !root.tsRecordVideo; checked: root.tsStitchAfter;    onCheckedChanged: root.tsStitchAfter    = checked }
                                    ToggleRow { label: "Record as video";       checked: root.tsRecordVideo;    onCheckedChanged: root.tsRecordVideo    = checked }
                                    Item { Layout.fillHeight: true }
                                }
                            }
                        }

                        // Right: Scan Preview
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            color: theme.colorSurface; radius: 8; border.color: theme.colorBorder
                            ColumnLayout {
                                anchors.fill: parent; anchors.margins: 14; spacing: 6
                                Text { text: "SCAN PREVIEW"; color: theme.colorTextSub; font.pixelSize: 10; font.weight: Font.Medium; font.letterSpacing: 0.7; Layout.alignment: Qt.AlignHCenter }

                                Item {
                                    Layout.fillWidth: true; Layout.fillHeight: true

                                    Canvas {
                                        id: tileScanCanvas
                                        anchors.fill: parent; anchors.margins: 4

                                        property int    tilesCols:    root.tsCols
                                        property int    tilesRows:    root.tsRows
                                        property string tilesPattern: root.tsPattern
                                        property real   tilesOverlap: root.tsOverlapPct / 100.0

                                        onTilesColsChanged:    requestPaint()
                                        onTilesRowsChanged:    requestPaint()
                                        onTilesPatternChanged: requestPaint()
                                        onTilesOverlapChanged: requestPaint()
                                        onWidthChanged:        requestPaint()
                                        onHeightChanged:       requestPaint()

                                        onPaint: {
                                            var ctx = getContext("2d")
                                            ctx.clearRect(0, 0, width, height)
                                            if (width <= 0 || height <= 0) return

                                            var cols = tilesCols
                                            var rows = tilesRows
                                            var ovlp = tilesOverlap
                                            var cellW = Math.floor((width - 2) / cols)
                                            var cellH = Math.floor((height - 2) / rows)
                                            var offsetX = Math.floor((width - cellW * cols) / 2)
                                            var offsetY = Math.floor((height - cellH * rows) / 2)
                                            var pad = 3

                                            var r, c, i, col, row

                                            // Draw cell fills and borders
                                            ctx.beginPath()
                                            for (r = 0; r < rows; r++) {
                                                for (c = 0; c < cols; c++) {
                                                    ctx.rect(offsetX + c * cellW + pad, offsetY + r * cellH + pad, cellW - pad * 2, cellH - pad * 2)
                                                }
                                            }
                                            ctx.fillStyle = Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.06); ctx.fill()
                                            ctx.strokeStyle = Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.20); ctx.lineWidth = 1; ctx.stroke()

                                            // Draw overlap regions
                                            if (ovlp > 0) {
                                                var ovlpW = cellW * ovlp
                                                var ovlpH = cellH * ovlp
                                                ctx.beginPath()
                                                // Vertical strips at every column boundary
                                                for (c = 1; c < cols; c++) {
                                                    ctx.rect(offsetX + c * cellW - ovlpW / 2,
                                                             offsetY + pad,
                                                             ovlpW,
                                                             rows * cellH - pad * 2)
                                                }
                                                // Horizontal strips at every row boundary
                                                for (r = 1; r < rows; r++) {
                                                    ctx.rect(offsetX + pad,
                                                             offsetY + r * cellH - ovlpH / 2,
                                                             cols * cellW - pad * 2,
                                                             ovlpH)
                                                }
                                                ctx.fillStyle = Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.18); ctx.fill()
                                            }

                                            // Draw tile numbers. Centered horizontally, upper third vertically
                                            for (r = 0; r < rows; r++) {
                                                for (c = 0; c < cols; c++) {
                                                    var nx = offsetX + c * cellW + pad
                                                    var ny = offsetY + r * cellH + pad
                                                    var nw = cellW - pad * 2
                                                    var nh = cellH - pad * 2
                                                    ctx.fillStyle = Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.75)
                                                    ctx.font = "bold 9px sans-serif"
                                                    ctx.textAlign = "center"; ctx.textBaseline = "middle"
                                                    ctx.fillText(r * cols + c + 1, nx + nw / 2, ny + nh * 0.30)
                                                }
                                            }

                                            var path = App.automation.tileOrder(cols, rows, tilesPattern)

                                            ctx.strokeStyle = theme.colorWarning; ctx.lineWidth = 1.5
                                            ctx.setLineDash([4, 3])
                                            ctx.beginPath()
                                            for (i = 0; i < path.length; i++) {
                                                var cx = offsetX + path[i].col * cellW + cellW / 2
                                                var cy = offsetY + path[i].row * cellH + cellH / 2
                                                if (i === 0) ctx.moveTo(cx, cy); else ctx.lineTo(cx, cy)
                                            }
                                            ctx.stroke(); ctx.setLineDash([])

                                            for (i = 0; i < path.length; i++) {
                                                var dcx = offsetX + path[i].col * cellW + cellW / 2
                                                var dcy = offsetY + path[i].row * cellH + cellH / 2
                                                ctx.fillStyle = theme.colorWarning
                                                ctx.beginPath(); ctx.arc(dcx, dcy, 2.5, 0, Math.PI * 2); ctx.fill()
                                            }
                                        }
                                    }
                                }

                                Text {
                                    text: (root.tsPattern === "serpentine" ? "Serpentine" : "Raster") + " · " + root.tsCols + "×" + root.tsRows + " · " + root.tsTileCount + " tiles"
                                    color: theme.colorTextSub; font.pixelSize: 9; Layout.alignment: Qt.AlignHCenter
                                }
                            }
                        }
                    }

                    // Bottom Info Bar
                    Rectangle {
                        Layout.fillWidth: true; Layout.preferredHeight: 50
                        color: theme.colorSurface; radius: 6; border.color: theme.colorBorder
                        RowLayout {
                            anchors.left: parent.left; anchors.right: parent.right
                            anchors.top: parent.top; anchors.bottom: parent.bottom
                            anchors.leftMargin: 14; anchors.rightMargin: 14
                            anchors.topMargin: 8; anchors.bottomMargin: 8
                            spacing: 16
                            Column { Layout.alignment: Qt.AlignVCenter; Text { text: "Tiles";       color: theme.colorTextSub; font.pixelSize: 10 } Text { text: root.tsTileCount + ""; color: theme.colorText; font.pixelSize: 11; font.family: "Courier New" } }
                            Rectangle { implicitWidth: 1; implicitHeight: 24; color: theme.colorSurfaceLight }
                            Column { Layout.alignment: Qt.AlignVCenter; Text { text: "Est. time";   color: theme.colorTextSub; font.pixelSize: 10 } Text { text: "~" + root.tsEstimateSeconds + " s"; color: theme.colorText; font.pixelSize: 11; font.family: "Courier New" } }
                            Rectangle { implicitWidth: 1; implicitHeight: 24; color: theme.colorSurfaceLight }
                            Column { Layout.alignment: Qt.AlignVCenter; Text { text: "Grid";        color: theme.colorTextSub; font.pixelSize: 10 } Text { text: root.tsCols + " × " + root.tsRows; color: theme.colorText; font.pixelSize: 11; font.family: "Courier New" } }
                            Rectangle { implicitWidth: 1; implicitHeight: 24; color: theme.colorSurfaceLight }
                            Column { Layout.alignment: Qt.AlignVCenter; Text { text: "Overlap";     color: theme.colorTextSub; font.pixelSize: 10 } Text { text: root.tsOverlapPct + "%"; color: theme.colorText; font.pixelSize: 11; font.family: "Courier New" } }
                        }
                    }
                    }
                } // End Tab 1

            } // StackLayout
        } // ColumnLayout (left)

        // Right Sidebar
        Rectangle {
            Layout.preferredWidth: 200; Layout.fillHeight: true
            color: theme.colorSurface
            Rectangle { width: 1; height: parent.height; color: theme.colorBorder }

            ColumnLayout {
                anchors.fill: parent; spacing: 0

                // Header
                Rectangle {
                    Layout.fillWidth: true; implicitHeight: 38; color: "transparent"
                    Text { text: "TASK QUEUE"; color: theme.colorTextSub; font.pixelSize: 10; font.weight: Font.Medium; font.letterSpacing: 0.8; anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 14 }
                }

                // Running task card
                Rectangle {
                    Layout.fillWidth: true; Layout.leftMargin: 10; Layout.rightMargin: 10
                    implicitHeight: App.automation.busy ? 110 : 0
                    visible: App.automation.busy
                    radius: 6; color: theme.colorSurfaceLight

                    ColumnLayout {
                        anchors.fill: parent; anchors.margins: 10; spacing: 6

                        RowLayout {
                            Layout.fillWidth: true
                            Text { text: App.automation.taskName; color: theme.colorText; font.pixelSize: 11 }
                            Item { Layout.fillWidth: true }
                            Text {
                                text: App.automation.cancelling ? "Stopping…"
                                    : App.automation.paused    ? "Paused"
                                    :                            "Running"
                                color: App.automation.cancelling ? theme.colorDanger
                                     : App.automation.paused    ? theme.colorWarning
                                     :                            theme.colorAccent
                                font.pixelSize: 10; font.weight: Font.Medium
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true; implicitHeight: 4; radius: 2; color: theme.colorBg
                            Rectangle {
                                width: parent.width * App.automation.taskProgress
                                height: 4; radius: 2; color: theme.colorAccent
                                Behavior on width { NumberAnimation { duration: 200 } }
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            Text { text: App.automation.taskFrameCurrent + " / " + App.automation.taskFrameTotal; color: theme.colorTextSub; font.pixelSize: 10 }
                            Item { Layout.fillWidth: true }
                            Text { text: App.automation.taskTimeLeft; color: theme.colorTextSub; font.pixelSize: 10 }
                        }

                        RowLayout {
                            Layout.fillWidth: true; spacing: 6

                            Rectangle {
                                Layout.fillWidth: true; implicitHeight: 24; radius: 6
                                color: Qt.rgba(239/255, 159/255, 39/255, App.automation.paused ? 0.2 : 0.1)
                                Text { text: App.automation.paused ? "Resume" : "Pause"; color: theme.colorWarning; font.pixelSize: 11; anchors.centerIn: parent }
                                MouseArea {
                                    anchors.fill: parent
                                    onClicked: App.automation.paused ? App.automation.resumeTask() : App.automation.pauseTask()
                                }
                            }
                            Rectangle {
                                Layout.fillWidth: true; implicitHeight: 24; radius: 6
                                color: Qt.rgba(226/255, 75/255, 74/255, 0.1)
                                Text { text: "Cancel"; color: theme.colorDanger; font.pixelSize: 11; anchors.centerIn: parent }
                                MouseArea { anchors.fill: parent; onClicked: App.automation.cancelTask() }
                            }
                        }
                    }
                }

                Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: theme.colorBorder; Layout.leftMargin: 14; Layout.rightMargin: 14; Layout.topMargin: 8 }

                // "Completed" header
                Rectangle {
                    Layout.fillWidth: true; implicitHeight: 38; color: "transparent"
                    Text { text: "COMPLETED"; color: theme.colorTextSub; font.pixelSize: 10; font.weight: Font.Medium; font.letterSpacing: 0.8; anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 14 }
                }

                // Completed list
                TouchScrollView {
                    Layout.fillWidth: true; Layout.fillHeight: true; clip: true; contentWidth: availableWidth
                    ColumnLayout {
                        width: parent.width; spacing: 4
                        Repeater {
                            model: App.automation.completedTasks
                            delegate: Rectangle {
                                id: completedDelegate
                                required property var modelData
                                Layout.fillWidth: true; Layout.leftMargin: 10; Layout.rightMargin: 10
                                implicitHeight: 40; radius: 5; color: theme.bgSecondary
                                ColumnLayout {
                                    anchors.fill: parent; anchors.margins: 8; spacing: 2
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Text { text: completedDelegate.modelData.name; color: theme.colorTextSub; font.pixelSize: 11 }
                                        Item { Layout.fillWidth: true }
                                        Text { text: completedDelegate.modelData.time; color: theme.colorTextSub; font.pixelSize: 10; opacity: 0.8 }
                                    }
                                    Text { text: completedDelegate.modelData.detail; color: theme.colorTextSub; font.pixelSize: 10; opacity: 0.8 }
                                }
                            }
                        }
                    }
                }

                // Start button
                Rectangle {
                    Layout.fillWidth: true; implicitHeight: 52
                    color: "transparent"
                    Rectangle { width: parent.width; height: 1; color: theme.colorBorder }

                    Rectangle {
                        anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 10; anchors.topMargin: 8; anchors.bottomMargin: 8; radius: 6
                        color: App.automation.busy
                               ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.05)
                               : Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12)
                        Row {
                            anchors.centerIn: parent; spacing: 6
                            Icon { code: App.automation.busy ? "\uf04d" : "\uf04b"; iconSize: 10; color: theme.colorAccent; anchors.verticalCenter: parent.verticalCenter }
                            Text { text: App.automation.busy ? "Running…" : "Start task"; color: theme.colorAccent; font.weight: Font.Medium; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                        }
                        MouseArea {
                            anchors.fill: parent
                            enabled: !App.automation.busy
                            onClicked: {
                                if (root.currentSubTab === 0) {
                                    App.automation.startFocusStackAbsolute(root.fsZStart, root.fsZEnd, root.fsStepSize, root.fsSettleMs, root.fsBlending)
                                } else {
                                    App.automation.startTileScan(root.tsCols, root.tsRows, root.tsOverlapPct / 100.0, root.tsPattern, root.tsAutofocusEach, root.tsRecordVideo, root.tsStitchAfter, root.tsSettleMs)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
