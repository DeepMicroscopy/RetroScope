pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "components"
import RetroScope 1.0

// Calibration wizard
Dialog {
    id: calibWizard

    Theme {
        id: theme
    }

    property string _wizTs: "0"
    property real _wizFocusQuality: 0.0

    FrameTapBoost {
        id: wizardFrameTapBoost
    }

    function showInputPanel() {
        Qt.callLater(function() { App.system.showInputPanel() })
    }

    Connections {
        target: App
        function onFrameAvailable() {
            if (calibWizard.visible && (calibWizard.step === 1 || calibWizard.step === 3 || calibWizard.step === 4 || calibWizard.step === 5 || calibWizard.step === 6))
                calibWizard._wizTs = Date.now().toString()
        }
        function onFocus_quality_updated(pct) {
            if (calibWizard.visible) calibWizard._wizFocusQuality = pct
        }
    }
    modal: true
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: 600
    closePolicy: Popup.CloseOnEscape

    // Scale measurement state
    property int  step: 0
    readonly property int totalSteps: 8
    property real px1x: 0; property real px1y: 0
    property real px2x: 0; property real px2y: 0
    property int  pointsSet: 0
    property real pixelDist: 0
    property real realUm: 0
    property real calibResult: 0

    property int  wizDofSteps:   1
    property int  wizStackStep:  1
    property int  wizBacklashX:  0
    property int  wizBacklashY:  0
    property int  wizBacklashZ:  0
    property string stageAxis: "x"
    property int stageMoveSteps: 100
    property real stagePx1x: 0; property real stagePx1y: 0
    property real stagePx2x: 0; property real stagePx2y: 0
    property int stagePointsSet: 0
    property real stagePixelDist: 0
    property real stageObservedPx: 0
    property real stageUmPerPixel: 0
    property real stageComputedUmPerStep: 0
    property bool stageCalibrated: false
    property string backlashAxis: "x"
    
    // dofUpperZ / dofLowerZ start as INT_MIN until marked with wizard.
    property int  dofUpperZ:     -2147483648
    property int  dofLowerZ:     -2147483648
    readonly property bool dofUpperSet: dofUpperZ !== -2147483648
    readonly property bool dofLowerSet: dofLowerZ !== -2147483648
    readonly property int  dofMeasuredSteps: (dofUpperSet && dofLowerSet) ? Math.abs(dofUpperZ - dofLowerZ) : 0

    function initState() {
        step = 0; pointsSet = 0
        px1x = 0; px1y = 0; px2x = 0; px2y = 0
        realUm = 0; calibResult = 0; pixelDist = 0
        _realInput.text = ""
        // load current values so wizard reflects actual calibration
        wizDofSteps   = App.objective.activeDofSteps
        wizStackStep  = App.objective.activeFocusStackStep
        wizBacklashX  = App.objective.activeBacklashX
        wizBacklashY  = App.objective.activeBacklashY
        wizBacklashZ  = App.objective.activeBacklashZ
        stageAxis = "x"
        stageMoveSteps = 100
        stageUmPerPixel = App.objective.activeUmPerPixel
        stageComputedUmPerStep = 0
        resetStageScalePoints()
        stageObservedPx = 0
        stageCalibrated = false
        backlashAxis = "x"
        resetDofMarks()
    }

    function resetDofMarks() {
        dofUpperZ = -2147483648
        dofLowerZ = -2147483648
    }

    function resetStageScalePoints() {
        stagePx1x = 0; stagePx1y = 0
        stagePx2x = 0; stagePx2y = 0
        stagePointsSet = 0
        stagePixelDist = 0
        stageObservedPx = 0
        stageComputedUmPerStep = 0
        stageCalibrated = false
    }

    function markDofUpper() {
        dofUpperZ = App.motion.posZ
        if (dofLowerSet) wizDofSteps = Math.max(1, dofMeasuredSteps)
    }

    function markDofLower() {
        dofLowerZ = App.motion.posZ
        if (dofUpperSet) wizDofSteps = Math.max(1, dofMeasuredSteps)
    }

    function imageNaturalWidth(img) {
        return Math.max(1, img.sourceSize.width > 1 ? img.sourceSize.width : (img.implicitWidth > 1 ? img.implicitWidth : 1280))
    }

    function imageNaturalHeight(img) {
        return Math.max(1, img.sourceSize.height > 1 ? img.sourceSize.height : (img.implicitHeight > 1 ? img.implicitHeight : 720))
    }

    function imagePointToNormalized(img, x, y) {
        var paintedW = Math.max(1, img.paintedWidth)
        var paintedH = Math.max(1, img.paintedHeight)
        var offsetX = (img.width - paintedW) / 2
        var offsetY = (img.height - paintedH) / 2
        var nx = (x - offsetX) / paintedW
        var ny = (y - offsetY) / paintedH
        return { x: nx, y: ny, valid: nx >= 0 && nx <= 1 && ny >= 0 && ny <= 1 }
    }

    function normalizedToCanvas(img, nx, ny) {
        var paintedW = Math.max(1, img.paintedWidth)
        var paintedH = Math.max(1, img.paintedHeight)
        return {
            x: (img.width - paintedW) / 2 + nx * paintedW,
            y: (img.height - paintedH) / 2 + ny * paintedH
        }
    }

    function normalizedPixelDistance(img, x1, y1, x2, y2) {
        var dx = (x2 - x1) * imageNaturalWidth(img)
        var dy = (y2 - y1) * imageNaturalHeight(img)
        return Math.sqrt(dx * dx + dy * dy)
    }

    function normalizedStageAxisDistance(img, axis, x1, y1, x2, y2) {
        var dx = Math.abs(x2 - x1) * imageNaturalWidth(img)
        var dy = Math.abs(y2 - y1) * imageNaturalHeight(img)
        return axis === "y" ? dy : dx
    }

    function markStageScalePoint(img, x, y) {
        var point = imagePointToNormalized(img, x, y)
        if (!point.valid)
            return
        if (stagePointsSet >= 2) {
            stagePx1x = point.x; stagePx1y = point.y
            stagePx2x = 0; stagePx2y = 0
            stagePixelDist = 0; stagePointsSet = 1
            stageCalibrated = false
        } else if (stagePointsSet < 1) {
            stagePx1x = point.x; stagePx1y = point.y
            stagePointsSet = 1
            stageCalibrated = false
        } else {
            stagePx2x = point.x; stagePx2y = point.y
            stagePixelDist = normalizedStageAxisDistance(
                img,
                stageAxis,
                stagePx1x, stagePx1y,
                stagePx2x, stagePx2y
            )
            stagePointsSet = 2
            stageCalibrated = false
        }
    }

    onOpened: {
        wizardFrameTapBoost.start()
        initState()
        calibWizard.forceActiveFocus()
    }
    onClosed: { wizardFrameTapBoost.stop(); App.calibration.setDofCalibrationActive(false) }
    onStepChanged: {
        // Use a fixed Z step per encoder tick in step 4
        App.calibration.setDofCalibrationActive(step === 4)
        if (step === 4) resetDofMarks()
    }

    background: Rectangle { color: theme.colorSurface; radius: 10; border.color: theme.colorBorder; border.width: 1 }
    padding: 20

    contentItem: StackLayout {
        currentIndex: calibWizard.step

        // Step 0: Welcome
        ColumnLayout {
            spacing: 14
            Text { text: "Calibration wizard"; color: theme.colorText; font.pixelSize: 15; font.weight: Font.Medium }
            WizardDots { total: calibWizard.totalSteps; current: calibWizard.step }
            Text { text: "Active objective: " + App.objective.activeDisplayName; color: theme.colorTextSub; font.pixelSize: 11 }
            Text {
                text: "This wizard measures the active objective once, then derives the other objective profiles from magnification and numerical aperture:\n\n1. Scale (µm per pixel)\n2. Stage scale\n3. Depth of field\n4. Focus stack step\n5. Backlash X, Y & Z"
                color: theme.colorTextSub; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true
            }
            Item { Layout.fillHeight: true }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Rectangle {
                    implicitWidth: _s0c.implicitWidth + 24; implicitHeight: 32; radius: 6
                    color: theme.colorSurfaceLight; border.color: theme.colorBorder; border.width: 1
                    Text { id: _s0c; anchors.centerIn: parent; text: "Cancel"; color: theme.colorTextSub; font.pixelSize: 12 }
                    TapHandler { onTapped: calibWizard.close() }
                }
                Rectangle {
                    implicitWidth: _s0n.implicitWidth + 24; implicitHeight: 32; radius: 6
                    color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12)
                    Row {
                        id: _s0n
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "Next"; color: theme.colorAccent; font.pixelSize: 12; font.weight: Font.Medium; anchors.verticalCenter: parent.verticalCenter }
                        Icon { code: "\uf054"; iconSize: 10; color: theme.colorAccent; anchors.verticalCenter: parent.verticalCenter }
                    }
                    TapHandler { onTapped: calibWizard.step = 1 }
                }
            }
        }

        // Step 1: Tap two points on live frame
        ColumnLayout {
            spacing: 8
            Text { text: "Scale: Tap two reference points"; color: theme.colorText; font.pixelSize: 14; font.weight: Font.Medium }
            WizardDots { total: calibWizard.totalSteps; current: calibWizard.step }
            Text {
                text: calibWizard.pointsSet === 0 ? "Tap the first point on the live frame below"
                    : calibWizard.pointsSet === 1 ? "Tap the second point"
                    : "Distance: " + calibWizard.pixelDist.toFixed(1) + " px. Tap to start over"
                color: theme.colorTextSub; font.pixelSize: 11
            }
            Rectangle {
                Layout.fillWidth: true; implicitHeight: 290
                color: "black"; radius: 4; clip: true
                Image {
                    id: _scaleImage
                    anchors.fill: parent
                    source: "image://camera/frame?" + calibWizard._wizTs
                    cache: false; fillMode: Image.PreserveAspectFit; smooth: true
                    horizontalAlignment: Image.AlignHCenter; verticalAlignment: Image.AlignVCenter
                }
                Canvas {
                    id: _wizCanvas
                    anchors.fill: parent
                    property int pointsSet: calibWizard.pointsSet
                    property real p1x: calibWizard.px1x; property real p1y: calibWizard.px1y
                    property real p2x: calibWizard.px2x; property real p2y: calibWizard.px2y
                    onPointsSetChanged: requestPaint()
                    onP1xChanged: requestPaint(); onP1yChanged: requestPaint()
                    onP2xChanged: requestPaint(); onP2yChanged: requestPaint()
                    onPaint: {
                        var ctx = getContext("2d")
                        ctx.clearRect(0, 0, width, height)
                        ctx.strokeStyle = "#5DCAA5"; ctx.lineWidth = 2
                        if (pointsSet >= 1) {
                            var p1 = calibWizard.normalizedToCanvas(_scaleImage, p1x, p1y)
                            ctx.beginPath(); ctx.arc(p1.x, p1.y, 6, 0, Math.PI*2); ctx.stroke()
                            ctx.lineWidth = 1; ctx.strokeStyle = "rgba(93,202,165,0.5)"
                            ctx.beginPath(); ctx.moveTo(p1.x-14,p1.y); ctx.lineTo(p1.x+14,p1.y); ctx.stroke()
                            ctx.beginPath(); ctx.moveTo(p1.x,p1.y-14); ctx.lineTo(p1.x,p1.y+14); ctx.stroke()
                            ctx.lineWidth = 2; ctx.strokeStyle = "#5DCAA5"
                        }
                        if (pointsSet >= 2) {
                            var p2 = calibWizard.normalizedToCanvas(_scaleImage, p2x, p2y)
                            ctx.beginPath(); ctx.arc(p2.x, p2.y, 6, 0, Math.PI*2); ctx.stroke()
                            ctx.lineWidth = 1; ctx.strokeStyle = "rgba(93,202,165,0.5)"
                            ctx.beginPath(); ctx.moveTo(p2.x-14,p2.y); ctx.lineTo(p2.x+14,p2.y); ctx.stroke()
                            ctx.beginPath(); ctx.moveTo(p2.x,p2.y-14); ctx.lineTo(p2.x,p2.y+14); ctx.stroke()
                            ctx.lineWidth = 1.5; ctx.strokeStyle = "#5DCAA5"; ctx.setLineDash([6,4])
                            var p1Line = calibWizard.normalizedToCanvas(_scaleImage, p1x, p1y)
                            ctx.beginPath(); ctx.moveTo(p1Line.x,p1Line.y); ctx.lineTo(p2.x,p2.y); ctx.stroke()
                            ctx.setLineDash([])
                        }
                    }
                    TapHandler {
                        onTapped: function(event) {
                            var point = calibWizard.imagePointToNormalized(_scaleImage, event.position.x, event.position.y)
                            if (!point.valid)
                                return
                            var fx = point.x
                            var fy = point.y
                            if (calibWizard.pointsSet >= 2) {
                                calibWizard.px1x = fx; calibWizard.px1y = fy
                                calibWizard.px2x = 0; calibWizard.px2y = 0
                                calibWizard.pixelDist = 0; calibWizard.pointsSet = 1
                            } else if (calibWizard.pointsSet < 1) {
                                calibWizard.px1x = fx; calibWizard.px1y = fy; calibWizard.pointsSet = 1
                            } else {
                                calibWizard.px2x = fx; calibWizard.px2y = fy
                                calibWizard.pixelDist = calibWizard.normalizedPixelDistance(
                                    _scaleImage,
                                    calibWizard.px1x, calibWizard.px1y,
                                    calibWizard.px2x, calibWizard.px2y
                                )
                                calibWizard.pointsSet = 2
                            }
                        }
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                Rectangle {
                    implicitWidth: _s1b.implicitWidth + 24; implicitHeight: 32; radius: 6
                    color: theme.colorSurfaceLight; border.color: theme.colorBorder; border.width: 1
                    Row {
                        id: _s1b
                        anchors.centerIn: parent
                        spacing: 6
                        Icon { code: "\uf053"; iconSize: 10; color: theme.colorTextSub; anchors.verticalCenter: parent.verticalCenter }
                        Text { text: "Back"; color: theme.colorTextSub; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                    }
                    TapHandler { onTapped: { calibWizard.step = 0; calibWizard.pointsSet = 0 } }
                }
                Item { Layout.fillWidth: true }
                Rectangle {
                    implicitWidth: _s1n.implicitWidth + 24; implicitHeight: 32; radius: 6
                    opacity: calibWizard.pointsSet === 2 ? 1.0 : 0.4
                    color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12)
                    Row {
                        id: _s1n
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "Next"; color: theme.colorAccent; font.pixelSize: 12; font.weight: Font.Medium; anchors.verticalCenter: parent.verticalCenter }
                        Icon { code: "\uf054"; iconSize: 10; color: theme.colorAccent; anchors.verticalCenter: parent.verticalCenter }
                    }
                    TapHandler { enabled: calibWizard.pointsSet === 2; onTapped: calibWizard.step = 2 }
                }
            }
        }

        // Step 2: Enter distance, confirm scale
        ColumnLayout {
            spacing: 12
            Text { text: "Scale: Enter real-world distance"; color: theme.colorText; font.pixelSize: 14; font.weight: Font.Medium }
            WizardDots { total: calibWizard.totalSteps; current: calibWizard.step }
            Text { text: "Measured pixel distance: " + calibWizard.pixelDist.toFixed(1) + " px"; color: theme.colorTextSub; font.pixelSize: 11 }
            RowLayout {
                spacing: 10
                Text { text: "Real distance (µm):"; color: theme.colorText; font.pixelSize: 12; Layout.alignment: Qt.AlignVCenter }
                Rectangle {
                    implicitWidth: 140; implicitHeight: 32; radius: 5
                    color: theme.colorSurfaceLight
                    border.color: _realInput.activeFocus ? theme.colorAccent : theme.colorBorder; border.width: 1
                    TextInput {
                        id: _realInput
                        anchors.fill: parent; anchors.margins: 8
                        color: theme.colorText; font.pixelSize: 12
                        inputMethodHints: Qt.ImhFormattedNumbersOnly
                        onActiveFocusChanged: if (activeFocus) calibWizard.showInputPanel()
                        onTextChanged: {
                            var v = parseFloat(text)
                            if (!isNaN(v) && v > 0 && calibWizard.pixelDist > 0) {
                                calibWizard.realUm = v
                                calibWizard.calibResult = v / calibWizard.pixelDist
                            } else { calibWizard.calibResult = 0 }
                        }
                    }
                }
            }
            Text {
                visible: calibWizard.calibResult > 0
                text: "->  " + calibWizard.calibResult.toFixed(4) + " µm/px on this objective, other profiles will be scaled by magnification."
                color: "#5DCAA5"; font.pixelSize: 12; font.weight: Font.Medium
            }
            Text {
                text: "Stage scale is measured in the next step with a live camera reference."
                color: theme.colorTextSub; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true
            }
            Item { Layout.fillHeight: true }
            RowLayout {
                Layout.fillWidth: true
                Rectangle {
                    implicitWidth: _s2b.implicitWidth + 24; implicitHeight: 32; radius: 6
                    color: theme.colorSurfaceLight; border.color: theme.colorBorder; border.width: 1
                    Row {
                        id: _s2b
                        anchors.centerIn: parent
                        spacing: 6
                        Icon { code: "\uf053"; iconSize: 10; color: theme.colorTextSub; anchors.verticalCenter: parent.verticalCenter }
                        Text { text: "Back"; color: theme.colorTextSub; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                    }
                    TapHandler { onTapped: calibWizard.step = 1 }
                }
                Item { Layout.fillWidth: true }
                Rectangle {
                    implicitWidth: _s2sk.implicitWidth + 24; implicitHeight: 32; radius: 6
                    color: theme.colorSurfaceLight; border.color: theme.colorBorder; border.width: 1
                    Text { id: _s2sk; anchors.centerIn: parent; text: "Skip"; color: theme.colorTextSub; font.pixelSize: 12 }
                    TapHandler { onTapped: { calibWizard.stageUmPerPixel = App.objective.activeUmPerPixel; calibWizard.step = 3 } }
                }
                Rectangle {
                    implicitWidth: _s2n.implicitWidth + 24; implicitHeight: 32; radius: 6
                    opacity: calibWizard.calibResult > 0 ? 1.0 : 0.4
                    color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12)
                    Row {
                        id: _s2n
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "Apply & Next"; color: theme.colorAccent; font.pixelSize: 12; font.weight: Font.Medium; anchors.verticalCenter: parent.verticalCenter }
                        Icon { code: "\uf054"; iconSize: 10; color: theme.colorAccent; anchors.verticalCenter: parent.verticalCenter }
                    }
                    TapHandler {
                        enabled: calibWizard.calibResult > 0
                        onTapped: {
                            App.objective.setUmPerPixel(calibWizard.calibResult)
                            calibWizard.stageUmPerPixel = calibWizard.calibResult
                            calibWizard.step = 3
                        }
                    }
                }
            }
        }

        // Step 3: Stage scale
        ColumnLayout {
            spacing: 8
            Text { text: "Stage scale"; color: theme.colorText; font.pixelSize: 14; font.weight: Font.Medium }
            WizardDots { total: calibWizard.totalSteps; current: calibWizard.step }
            Text {
                text: calibWizard.stagePointsSet === 0 ? "Choose X or Y, tap a recognizable feature, move the stage, then tap the same feature again."
                    : calibWizard.stagePointsSet === 1 ? "Move " + calibWizard.stageAxis.toUpperCase() + " by " + calibWizard.stageMoveSteps + " steps, then tap the same feature again."
                    : "Measured " + calibWizard.stageAxis.toUpperCase() + " shift: " + calibWizard.stagePixelDist.toFixed(1) + " px"
                color: theme.colorTextSub; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true
            }
            RowLayout {
                Layout.fillWidth: true; spacing: 8
                Text { text: "Axis"; color: theme.colorText; font.pixelSize: 12; Layout.alignment: Qt.AlignVCenter }
                Repeater {
                    model: ["x", "y"]
                    delegate: Rectangle {
                        id: stageAxisDelegate
                        required property string modelData
                        implicitWidth: 34; implicitHeight: 26; radius: 5
                        color: calibWizard.stageAxis === stageAxisDelegate.modelData ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.16) : theme.colorSurfaceLight
                        border.color: calibWizard.stageAxis === stageAxisDelegate.modelData ? theme.colorAccent : theme.colorBorder; border.width: 1
                        Text { anchors.centerIn: parent; text: stageAxisDelegate.modelData.toUpperCase(); color: theme.colorText; font.pixelSize: 11 }
                        TapHandler {
                            onTapped: {
                                calibWizard.stageAxis = stageAxisDelegate.modelData
                                calibWizard.resetStageScalePoints()
                            }
                        }
                    }
                }
                Item { Layout.fillWidth: true }
                Text { text: "Move"; color: theme.colorTextSub; font.pixelSize: 11; Layout.alignment: Qt.AlignVCenter }
                Repeater {
                    model: [100, 250, 500, 1000, 2500]
                    delegate: Rectangle {
                        id: stageMoveDelegate
                        required property int modelData
                        implicitWidth: 42; implicitHeight: 26; radius: 5
                        color: calibWizard.stageMoveSteps === stageMoveDelegate.modelData ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.16) : theme.colorSurfaceLight
                        border.color: calibWizard.stageMoveSteps === stageMoveDelegate.modelData ? theme.colorAccent : theme.colorBorder; border.width: 1
                        Text { anchors.centerIn: parent; text: stageMoveDelegate.modelData; color: theme.colorText; font.pixelSize: 10 }
                        TapHandler { onTapped: calibWizard.stageMoveSteps = stageMoveDelegate.modelData }
                    }
                }
            }
            Rectangle {
                Layout.fillWidth: true; implicitHeight: 230
                color: "black"; radius: 4; clip: true
                Image {
                    id: _stageScaleImage
                    anchors.fill: parent
                    source: "image://camera/frame?" + calibWizard._wizTs
                    cache: false; fillMode: Image.PreserveAspectFit; smooth: true
                    horizontalAlignment: Image.AlignHCenter; verticalAlignment: Image.AlignVCenter
                }
                Canvas {
                    id: _stageScaleCanvas
                    anchors.fill: parent
                    property int pointsSet: calibWizard.stagePointsSet
                    property real p1x: calibWizard.stagePx1x; property real p1y: calibWizard.stagePx1y
                    property real p2x: calibWizard.stagePx2x; property real p2y: calibWizard.stagePx2y
                    onPointsSetChanged: requestPaint()
                    onP1xChanged: requestPaint(); onP1yChanged: requestPaint()
                    onP2xChanged: requestPaint(); onP2yChanged: requestPaint()
                    onPaint: {
                        var ctx = getContext("2d")
                        ctx.clearRect(0, 0, width, height)
                        ctx.strokeStyle = "#5DCAA5"; ctx.lineWidth = 2
                        if (pointsSet >= 1) {
                            var p1 = calibWizard.normalizedToCanvas(_stageScaleImage, p1x, p1y)
                            ctx.beginPath(); ctx.arc(p1.x, p1.y, 6, 0, Math.PI*2); ctx.stroke()
                            ctx.lineWidth = 1; ctx.strokeStyle = "rgba(93,202,165,0.5)"
                            ctx.beginPath(); ctx.moveTo(p1.x-14,p1.y); ctx.lineTo(p1.x+14,p1.y); ctx.stroke()
                            ctx.beginPath(); ctx.moveTo(p1.x,p1.y-14); ctx.lineTo(p1.x,p1.y+14); ctx.stroke()
                            ctx.lineWidth = 2; ctx.strokeStyle = "#5DCAA5"
                        }
                        if (pointsSet >= 2) {
                            var p2 = calibWizard.normalizedToCanvas(_stageScaleImage, p2x, p2y)
                            ctx.beginPath(); ctx.arc(p2.x, p2.y, 6, 0, Math.PI*2); ctx.stroke()
                            ctx.lineWidth = 1.5; ctx.setLineDash([6,4])
                            var p1Line = calibWizard.normalizedToCanvas(_stageScaleImage, p1x, p1y)
                            ctx.beginPath(); ctx.moveTo(p1Line.x,p1Line.y); ctx.lineTo(p2.x,p2.y); ctx.stroke()
                            ctx.setLineDash([])
                        }
                    }
                    TapHandler { onTapped: function(event) { calibWizard.markStageScalePoint(_stageScaleImage, event.position.x, event.position.y) } }
                }
            }
            RowLayout {
                Layout.fillWidth: true; spacing: 8
                Rectangle {
                    implicitWidth: 70; implicitHeight: 30; radius: 6
                    color: theme.colorSurfaceLight; border.color: theme.colorBorder; border.width: 1
                    Text { anchors.centerIn: parent; text: "-" + calibWizard.stageMoveSteps; color: theme.colorTextSub; font.pixelSize: 11 }
                    TapHandler { onTapped: App.calibration.jogStageAxis(calibWizard.stageAxis, -calibWizard.stageMoveSteps) }
                }
                Rectangle {
                    implicitWidth: 70; implicitHeight: 30; radius: 6
                    color: theme.colorSurfaceLight; border.color: theme.colorBorder; border.width: 1
                    Text { anchors.centerIn: parent; text: "+" + calibWizard.stageMoveSteps; color: theme.colorTextSub; font.pixelSize: 11 }
                    TapHandler { onTapped: App.calibration.jogStageAxis(calibWizard.stageAxis, calibWizard.stageMoveSteps) }
                }
                Text {
                    text: calibWizard.stageCalibrated
                        ? "Saved " + calibWizard.stageAxis.toUpperCase() + ": " + calibWizard.stageComputedUmPerStep.toFixed(4) + " µm/st"
                        : (calibWizard.stagePixelDist > 0 ? calibWizard.stagePixelDist.toFixed(1) + " px @ " + calibWizard.stageUmPerPixel.toFixed(4) + " µm/px" : "")
                    color: theme.colorTextSub; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight
                }
                Rectangle {
                    implicitWidth: _stageApplyLbl.implicitWidth + 20; implicitHeight: 30; radius: 6
                    opacity: calibWizard.stagePixelDist > 0 ? 1.0 : 0.45
                    color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12)
                    Text { id: _stageApplyLbl; anchors.centerIn: parent; text: "Save " + calibWizard.stageAxis.toUpperCase(); color: theme.colorAccent; font.pixelSize: 11; font.weight: Font.Medium }
                    TapHandler {
                        enabled: calibWizard.stagePixelDist > 0
                        onTapped: {
                            calibWizard.stageObservedPx = calibWizard.stagePixelDist
                            calibWizard.stageComputedUmPerStep = calibWizard.stageObservedPx * calibWizard.stageUmPerPixel / Math.max(1, Math.abs(calibWizard.stageMoveSteps))
                            calibWizard.stageCalibrated = App.calibration.setStageAxisCalibrationWithScale(
                                calibWizard.stageAxis,
                                calibWizard.stageMoveSteps,
                                calibWizard.stageObservedPx,
                                calibWizard.stageUmPerPixel
                            )
                        }
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                Rectangle {
                    implicitWidth: _s3b.implicitWidth + 24; implicitHeight: 32; radius: 6
                    color: theme.colorSurfaceLight; border.color: theme.colorBorder; border.width: 1
                    Row {
                        id: _s3b
                        anchors.centerIn: parent
                        spacing: 6
                        Icon { code: "\uf053"; iconSize: 10; color: theme.colorTextSub; anchors.verticalCenter: parent.verticalCenter }
                        Text { text: "Back"; color: theme.colorTextSub; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                    }
                    TapHandler { onTapped: calibWizard.step = 2 }
                }
                Item { Layout.fillWidth: true }
                Rectangle {
                    implicitWidth: _s3sk.implicitWidth + 24; implicitHeight: 32; radius: 6
                    color: theme.colorSurfaceLight; border.color: theme.colorBorder; border.width: 1
                    Text { id: _s3sk; anchors.centerIn: parent; text: "Skip"; color: theme.colorTextSub; font.pixelSize: 12 }
                    TapHandler { onTapped: calibWizard.step = 4 }
                }
                Rectangle {
                    implicitWidth: _s3n.implicitWidth + 24; implicitHeight: 32; radius: 6
                    color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12)
                    Row {
                        id: _s3n
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "Next"; color: theme.colorAccent; font.pixelSize: 12; font.weight: Font.Medium; anchors.verticalCenter: parent.verticalCenter }
                        Icon { code: "\uf054"; iconSize: 10; color: theme.colorAccent; anchors.verticalCenter: parent.verticalCenter }
                    }
                    TapHandler { onTapped: calibWizard.step = 4 }
                }
            }
        }

        // Step 4: Depth of field
        ColumnLayout {
            spacing: 8
            Text { text: "Depth of field"; color: theme.colorText; font.pixelSize: 14; font.weight: Font.Medium }
            WizardDots { total: calibWizard.totalSteps; current: calibWizard.step }
            Text {
                text: "Find peak sharpness with the encoder. Move up until focus quality drops to ~50%, tap Mark upper. Move back through peak and down until quality drops to ~50%, tap Mark lower. This measured DoF is saved in motor steps and the other profiles are scaled by numerical aperture."
                color: theme.colorTextSub; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true
            }
            // Live frame with focus quality bar
            Rectangle {
                Layout.fillWidth: true; implicitHeight: 200; color: "black"; radius: 4; clip: true
                Image {
                    anchors.fill: parent
                    source: "image://camera/frame?" + calibWizard._wizTs
                    cache: false; fillMode: Image.PreserveAspectFit; smooth: true
                    horizontalAlignment: Image.AlignHCenter; verticalAlignment: Image.AlignVCenter
                }
                Rectangle {
                    anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right
                    height: 30; color: Qt.rgba(0,0,0,0.6)
                    RowLayout {
                        anchors.fill: parent; anchors.margins: 8; spacing: 8
                        Text { text: "Focus quality"; color: "#909090"; font.pixelSize: 10 }
                        Rectangle {
                            Layout.fillWidth: true; Layout.preferredHeight: 6; radius: 3; color: Qt.rgba(1,1,1,0.12)
                            Rectangle {
                                width: parent.width * (calibWizard._wizFocusQuality / 100)
                                height: 6; radius: 3
                                color: calibWizard._wizFocusQuality > 60 ? theme.colorSuccess
                                     : calibWizard._wizFocusQuality > 30 ? theme.colorWarning : theme.colorDanger
                                Behavior on width { NumberAnimation { duration: 80 } }
                            }
                        }
                        Text {
                            text: calibWizard._wizFocusQuality.toFixed(0) + "%"
                            color: "white"; font.pixelSize: 10; font.family: "Courier New"
                        }
                    }
                }
            }
            SRow { label: "Current Z"; value: App.motion.posZ + " st"; mono: true }
            RowLayout {
                Layout.fillWidth: true; spacing: 8

                Rectangle {
                    Layout.fillWidth: true; implicitHeight: 36; radius: 6
                    color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12)
                    border.color: calibWizard.dofUpperSet ? theme.colorAccent : "transparent"; border.width: 1
                    ColumnLayout {
                        anchors.centerIn: parent; spacing: 0
                        Text { text: calibWizard.dofUpperSet ? "Upper: " + calibWizard.dofUpperZ + " st" : "Mark upper edge"
                               color: theme.colorAccent; font.pixelSize: 12; font.weight: Font.Medium
                               horizontalAlignment: Text.AlignHCenter; Layout.alignment: Qt.AlignHCenter }
                    }
                    TapHandler { onTapped: calibWizard.markDofUpper() }
                }

                Rectangle {
                    Layout.fillWidth: true; implicitHeight: 36; radius: 6
                    color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12)
                    border.color: calibWizard.dofLowerSet ? theme.colorAccent : "transparent"; border.width: 1
                    ColumnLayout {
                        anchors.centerIn: parent; spacing: 0
                        Text { text: calibWizard.dofLowerSet ? "Lower: " + calibWizard.dofLowerZ + " st" : "Mark lower edge"
                               color: theme.colorAccent; font.pixelSize: 12; font.weight: Font.Medium
                               horizontalAlignment: Text.AlignHCenter; Layout.alignment: Qt.AlignHCenter }
                    }
                    TapHandler { onTapped: calibWizard.markDofLower() }
                }

                Rectangle {
                    implicitWidth: _resetDofMarks.implicitWidth + 20; implicitHeight: 36; radius: 6
                    color: theme.colorSurfaceLight; border.color: theme.colorBorder; border.width: 1
                    Text { id: _resetDofMarks; anchors.centerIn: parent; text: "Reset"; color: theme.colorTextSub; font.pixelSize: 11 }
                    TapHandler { onTapped: calibWizard.resetDofMarks() }
                }
            }

            SRow {
                label: "Depth of field"
                value: (calibWizard.dofUpperSet && calibWizard.dofLowerSet)
                       ? calibWizard.dofMeasuredSteps + " st"
                       : (calibWizard.wizDofSteps + " st  (current)")
                mono: true
            }

            RowLayout {
                Layout.fillWidth: true
                Rectangle {
                    implicitWidth: _s4b.implicitWidth + 24; implicitHeight: 32; radius: 6
                    color: theme.colorSurfaceLight; border.color: theme.colorBorder; border.width: 1
                    Row {
                        id: _s4b
                        anchors.centerIn: parent
                        spacing: 6
                        Icon { code: "\uf053"; iconSize: 10; color: theme.colorTextSub; anchors.verticalCenter: parent.verticalCenter }
                        Text { text: "Back"; color: theme.colorTextSub; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                    }
                    TapHandler { onTapped: calibWizard.step = 3 }
                }
                Item { Layout.fillWidth: true }
                Rectangle {
                    implicitWidth: _s4n.implicitWidth + 24; implicitHeight: 32; radius: 6
                    opacity: (calibWizard.dofUpperSet && calibWizard.dofLowerSet) ? 1.0 : 0.4
                    color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12)
                    Row {
                        id: _s4n
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "Apply & Next"; color: theme.colorAccent; font.pixelSize: 12; font.weight: Font.Medium; anchors.verticalCenter: parent.verticalCenter }
                        Icon { code: "\uf054"; iconSize: 10; color: theme.colorAccent; anchors.verticalCenter: parent.verticalCenter }
                    }
                    TapHandler {
                        enabled: calibWizard.dofUpperSet && calibWizard.dofLowerSet
                        onTapped: { App.objective.setDofSteps(calibWizard.wizDofSteps); calibWizard.step = 5 }
                    }
                }
            }
        }

        // Step 5: Focus stack step
        ColumnLayout {
            spacing: 8
            Text { text: "Focus stack step"; color: theme.colorText; font.pixelSize: 14; font.weight: Font.Medium }
            WizardDots { total: calibWizard.totalSteps; current: calibWizard.step }
            Text {
                text: "Distance between frames during a focus stack sweep. The chosen ratio is applied to the derived DoF of each objective."
                color: theme.colorTextSub; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true
            }
            // Small live frame for context
            Rectangle {
                Layout.fillWidth: true; implicitHeight: 160; color: "black"; radius: 4; clip: true
                Image {
                    anchors.fill: parent
                    source: "image://camera/frame?" + calibWizard._wizTs
                    cache: false; fillMode: Image.PreserveAspectFit; smooth: true
                    horizontalAlignment: Image.AlignHCenter; verticalAlignment: Image.AlignVCenter
                }
            }
            SRow { label: "Stack step"; value: calibWizard.wizStackStep + " st" }
            SSlider {
                Layout.fillWidth: true
                from: 1; to: 1000; stepSize: 1
                value: calibWizard.wizStackStep
                onValueEdited: function(v) { calibWizard.wizStackStep = Math.round(v) }
            }
            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                implicitWidth: _sugLbl.implicitWidth + 20; implicitHeight: 28; radius: 5
                color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.08)
                border.color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.25); border.width: 1
                Text {
                    id: _sugLbl; anchors.centerIn: parent
                    text: "Use suggested: " + Math.max(1, Math.round(calibWizard.wizDofSteps / 2)) + " st"
                    color: theme.colorAccent; font.pixelSize: 11
                }
                TapHandler { onTapped: calibWizard.wizStackStep = Math.max(1, Math.round(calibWizard.wizDofSteps / 2)) }
            }
            RowLayout {
                Layout.fillWidth: true
                Rectangle {
                    implicitWidth: _s5b.implicitWidth + 24; implicitHeight: 32; radius: 6
                    color: theme.colorSurfaceLight; border.color: theme.colorBorder; border.width: 1
                    Row {
                        id: _s5b
                        anchors.centerIn: parent
                        spacing: 6
                        Icon { code: "\uf053"; iconSize: 10; color: theme.colorTextSub; anchors.verticalCenter: parent.verticalCenter }
                        Text { text: "Back"; color: theme.colorTextSub; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                    }
                    TapHandler { onTapped: calibWizard.step = 4 }
                }
                Item { Layout.fillWidth: true }
                Rectangle {
                    implicitWidth: _s5n.implicitWidth + 24; implicitHeight: 32; radius: 6
                    color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12)
                    Row {
                        id: _s5n
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "Apply & Next"; color: theme.colorAccent; font.pixelSize: 12; font.weight: Font.Medium; anchors.verticalCenter: parent.verticalCenter }
                        Icon { code: "\uf054"; iconSize: 10; color: theme.colorAccent; anchors.verticalCenter: parent.verticalCenter }
                    }
                    TapHandler { onTapped: { App.objective.setFocusStackStep(calibWizard.wizStackStep); calibWizard.step = 6 } }
                }
            }
        }

        // Step 6: Backlash
        ColumnLayout {
            spacing: 8
            Text { text: "Backlash compensation"; color: theme.colorText; font.pixelSize: 14; font.weight: Font.Medium }
            WizardDots { total: calibWizard.totalSteps; current: calibWizard.step }
            Text {
                text: "Mechanical slack before movement starts. The accepted backlash values are applied to all objective profiles because backlash is mechanical."
                color: theme.colorTextSub; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true
            }
            // Live frame with crosshair
            Rectangle {
                Layout.fillWidth: true; implicitHeight: 190; color: "black"; radius: 4; clip: true
                Image {
                    anchors.fill: parent
                    source: "image://camera/frame?" + calibWizard._wizTs
                    cache: false; fillMode: Image.PreserveAspectFit; smooth: true
                    horizontalAlignment: Image.AlignHCenter; verticalAlignment: Image.AlignVCenter
                }
                Canvas {
                    anchors.fill: parent
                    Component.onCompleted: requestPaint()
                    onPaint: {
                        var ctx = getContext("2d")
                        ctx.clearRect(0, 0, width, height)
                        ctx.strokeStyle = Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.75); ctx.lineWidth = 1
                        ctx.beginPath(); ctx.moveTo(width/2, 0); ctx.lineTo(width/2, height); ctx.stroke()
                        ctx.beginPath(); ctx.moveTo(0, height/2); ctx.lineTo(width, height/2); ctx.stroke()
                        // centre dot
                        ctx.fillStyle = Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.9)
                        ctx.beginPath(); ctx.arc(width/2, height/2, 3, 0, Math.PI*2); ctx.fill()
                    }
                }
            }
            Rectangle {
                Layout.fillWidth: true; implicitHeight: 128; radius: 6
                color: theme.colorSurfaceLight; border.color: theme.colorBorder; border.width: 1
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 10; spacing: 6
                    RowLayout {
                        Layout.fillWidth: true; spacing: 6
                        Text { text: "Camera measurement"; color: theme.colorText; font.pixelSize: 12; font.weight: Font.Medium }
                        Item { Layout.fillWidth: true }
                        Repeater {
                            model: ["x", "y", "z"]
                            delegate: Rectangle {
                                id: backlashAxisDelegate
                                required property string modelData
                                implicitWidth: 32; implicitHeight: 24; radius: 5
                                color: calibWizard.backlashAxis === backlashAxisDelegate.modelData ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.16) : theme.colorSurface
                                border.color: calibWizard.backlashAxis === backlashAxisDelegate.modelData ? theme.colorAccent : theme.colorBorder; border.width: 1
                                Text { anchors.centerIn: parent; text: backlashAxisDelegate.modelData.toUpperCase(); color: theme.colorText; font.pixelSize: 11 }
                                TapHandler {
                                    onTapped: {
                                        calibWizard.backlashAxis = backlashAxisDelegate.modelData
                                        App.calibration.beginBacklashMeasurement(backlashAxisDelegate.modelData)
                                    }
                                }
                            }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true; spacing: 6
                        Repeater {
                            model: [-500, -250, -100, -50, 50, 100, 250, 500]
                            delegate: Rectangle {
                                id: backlashJogDelegate
                                required property int modelData
                                Layout.fillWidth: true; implicitHeight: 26; radius: 5
                                color: theme.colorSurface; border.color: theme.colorBorder; border.width: 1
                                Text { anchors.centerIn: parent; text: backlashJogDelegate.modelData > 0 ? "+" + backlashJogDelegate.modelData : backlashJogDelegate.modelData; color: theme.colorTextSub; font.pixelSize: 10 }
                                TapHandler { onTapped: App.calibration.jogBacklashAxis(calibWizard.backlashAxis, backlashJogDelegate.modelData) }
                            }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true; spacing: 6
                        Rectangle {
                            implicitWidth: _refLbl.implicitWidth + 18; implicitHeight: 26; radius: 5
                            color: theme.colorSurface; border.color: theme.colorBorder; border.width: 1
                            Text { id: _refLbl; anchors.centerIn: parent; text: "Set reference"; color: theme.colorTextSub; font.pixelSize: 11 }
                            TapHandler { onTapped: App.calibration.setBacklashReference() }
                        }
                        Rectangle {
                            implicitWidth: _measureLbl.implicitWidth + 18; implicitHeight: 26; radius: 5
                            color: theme.colorSurface; border.color: theme.colorBorder; border.width: 1
                            Text { id: _measureLbl; anchors.centerIn: parent; text: "Measure"; color: theme.colorTextSub; font.pixelSize: 11 }
                            TapHandler { onTapped: App.calibration.measureBacklashOffset() }
                        }
                        Text {
                            text: "Δ " + App.calibration.backlashOffsetXPx.toFixed(1) + ", " + App.calibration.backlashOffsetYPx.toFixed(1) + " px · " + Math.round(App.calibration.backlashMatchScore * 100) + "%"
                            color: theme.colorTextSub; font.pixelSize: 10; Layout.fillWidth: true; elide: Text.ElideRight
                        }
                        Rectangle {
                            implicitWidth: _acceptLbl.implicitWidth + 18; implicitHeight: 26; radius: 5
                            opacity: App.calibration.backlashReverseSteps > 0 ? 1.0 : 0.45
                            color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12)
                            Text { id: _acceptLbl; anchors.centerIn: parent; text: "Accept " + App.calibration.backlashReverseSteps + " st"; color: theme.colorAccent; font.pixelSize: 11; font.weight: Font.Medium }
                            TapHandler {
                                enabled: App.calibration.backlashReverseSteps > 0
                                onTapped: {
                                    App.calibration.acceptBacklashSteps(calibWizard.backlashAxis, App.calibration.backlashReverseSteps)
                                    calibWizard.wizBacklashX = App.objective.activeBacklashX
                                    calibWizard.wizBacklashY = App.objective.activeBacklashY
                                    calibWizard.wizBacklashZ = App.objective.activeBacklashZ
                                }
                            }
                        }
                    }
                }
            }
            // Final values (these get applied to all objectives)
            RowLayout {
                Layout.fillWidth: true; spacing: 8
                Text { text: "Final values"; color: theme.colorText; font.pixelSize: 12; Layout.fillWidth: true; Layout.alignment: Qt.AlignVCenter }
                Repeater {
                    model: [
                        { label: "X", prop: "wizBacklashX" },
                        { label: "Y", prop: "wizBacklashY" },
                        { label: "Z", prop: "wizBacklashZ" }
                    ]
                    delegate: RowLayout {
                        id: finalAxisDelegate
                        required property var modelData
                        spacing: 4
                        Layout.alignment: Qt.AlignVCenter
                        function _get() {
                            if (modelData.prop === "wizBacklashX") return calibWizard.wizBacklashX
                            if (modelData.prop === "wizBacklashY") return calibWizard.wizBacklashY
                            return calibWizard.wizBacklashZ
                        }
                        function _set(v) {
                            // 5000 as generous ceiling, calibration (should) not exceed that
                            v = Math.max(0, Math.min(5000, v))
                            if (modelData.prop === "wizBacklashX") calibWizard.wizBacklashX = v
                            else if (modelData.prop === "wizBacklashY") calibWizard.wizBacklashY = v
                            else calibWizard.wizBacklashZ = v
                        }
                        Text { text: finalAxisDelegate.modelData.label; color: theme.colorTextSub; font.pixelSize: 11; Layout.alignment: Qt.AlignVCenter }
                        Rectangle {
                            implicitWidth: 26; implicitHeight: 26; radius: 5
                            color: theme.colorSurfaceLight; border.color: theme.colorBorder; border.width: 1
                            Text { anchors.centerIn: parent; text: "−"; color: theme.colorTextSub; font.pixelSize: 14 }
                            TapHandler { onTapped: finalAxisDelegate._set(finalAxisDelegate._get() - 5) }
                        }
                        Text {
                            text: finalAxisDelegate._get() + " st"
                            color: theme.colorText; font.pixelSize: 12; font.family: "Courier New"
                            Layout.preferredWidth: 48; horizontalAlignment: Text.AlignHCenter
                        }
                        Rectangle {
                            implicitWidth: 26; implicitHeight: 26; radius: 5
                            color: theme.colorSurfaceLight; border.color: theme.colorBorder; border.width: 1
                            Text { anchors.centerIn: parent; text: "+"; color: theme.colorTextSub; font.pixelSize: 14 }
                            TapHandler { onTapped: finalAxisDelegate._set(finalAxisDelegate._get() + 5) }
                        }
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                Rectangle {
                    implicitWidth: _s6b.implicitWidth + 24; implicitHeight: 32; radius: 6
                    color: theme.colorSurfaceLight; border.color: theme.colorBorder; border.width: 1
                    Row {
                        id: _s6b
                        anchors.centerIn: parent
                        spacing: 6
                        Icon { code: "\uf053"; iconSize: 10; color: theme.colorTextSub; anchors.verticalCenter: parent.verticalCenter }
                        Text { text: "Back"; color: theme.colorTextSub; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                    }
                    TapHandler { onTapped: calibWizard.step = 5 }
                }
                Item { Layout.fillWidth: true }
                Rectangle {
                    implicitWidth: _s6n.implicitWidth + 24; implicitHeight: 32; radius: 6
                    color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12)
                    Row {
                        id: _s6n
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "Apply & Next"; color: theme.colorAccent; font.pixelSize: 12; font.weight: Font.Medium; anchors.verticalCenter: parent.verticalCenter }
                        Icon { code: "\uf054"; iconSize: 10; color: theme.colorAccent; anchors.verticalCenter: parent.verticalCenter }
                    }
                    TapHandler {
                        onTapped: {
                            App.objective.setBacklashX(calibWizard.wizBacklashX)
                            App.objective.setBacklashY(calibWizard.wizBacklashY)
                            App.objective.setBacklashZ(calibWizard.wizBacklashZ)
                            calibWizard.step = 7
                        }
                    }
                }
            }
        }

        // Step 7: Summary
        ColumnLayout {
            spacing: 10
            Text { text: "Calibration complete"; color: theme.colorText; font.pixelSize: 14; font.weight: Font.Medium }
            WizardDots { total: calibWizard.totalSteps; current: calibWizard.step }
            Text { text: "Measured from " + App.objective.activeDisplayName + ". All objective profiles were updated."; color: theme.colorTextSub; font.pixelSize: 11 }
            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: theme.colorBorder; Layout.topMargin: 4; Layout.bottomMargin: 4 }
            SRow { label: "Scale";          value: App.objective.activeUmPerPixel.toFixed(4) + " µm/px"; mono: true }
            SRow { label: "Depth of field"; value: App.objective.activeDofSteps + " st";                 mono: true }
            SRow { label: "Stack step";     value: App.objective.activeFocusStackStep + " st";           mono: true }
            SRow { label: "Backlash X";     value: App.objective.activeBacklashX  + " steps";            mono: true }
            SRow { label: "Backlash Y";     value: App.objective.activeBacklashY  + " steps";            mono: true }
            SRow { label: "Backlash Z";     value: App.objective.activeBacklashZ  + " steps";            mono: true }
            Item { Layout.fillHeight: true }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Rectangle {
                    implicitWidth: _s7cl.implicitWidth + 24; implicitHeight: 32; radius: 6
                    color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12)
                    Text { id: _s7cl; anchors.centerIn: parent; text: "Done"; color: theme.colorAccent; font.pixelSize: 12; font.weight: Font.Medium }
                    TapHandler { onTapped: calibWizard.close() }
                }
            }
        }
    }
}
