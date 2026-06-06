pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "components"
import RetroScope 1.0

Rectangle {
    id: root

    focus: true

    Theme { id: localTheme }

    readonly property bool  dark:          localTheme.dark
    readonly property color colorBg:       localTheme.colorBg
    readonly property color colorSurface:  localTheme.colorSurface
    readonly property color colorSurfaceLight: localTheme.colorSurfaceLight
    readonly property color colorBorder:   localTheme.colorBorder
    readonly property color colorText:     localTheme.colorText
    readonly property color colorTextSub:  localTheme.colorTextSub
    readonly property color colorAccent:   localTheme.colorAccent
    readonly property color colorAccentFill: localTheme.colorAccentFill
    readonly property color colorDanger:   localTheme.colorDanger
    readonly property color colorWarning:  localTheme.colorWarning
    readonly property color colorSuccess:  localTheme.colorSuccess

    color: colorBg

    property int  currentPage: 0
    property int  motorJogStep: 100
    function showInputPanel() {
        Qt.callLater(function() { App.system.showInputPanel() })
    }

    function dismissInputPanel() {
        root.forceActiveFocus()
    }

    function openObjectiveCalibrationWizard() {
        dismissInputPanel()
        Qt.callLater(function() { calibWizard.open() })
    }

    // Confirm dialog
    Dialog {
        id: confirmDialog
        property string actionId: ""
        property alias promptText: confirmLabel.text
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: 320
        modal: true
        padding: 0
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle { color: root.colorSurface; border.color: root.colorBorder; border.width: 1; radius: 8 }

        contentItem: ColumnLayout {
            spacing: 0

            Rectangle {
                Layout.fillWidth: true; Layout.preferredHeight: 42
                color: root.colorSurfaceLight; radius: 8
                Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: root.colorBorder }
                Text { anchors { left: parent.left; leftMargin: 16; verticalCenter: parent.verticalCenter }
                       text: "Confirm"; color: root.colorText; font.pixelSize: 13; font.weight: Font.Medium }
            }

            Text {
                id: confirmLabel
                Layout.fillWidth: true; Layout.margins: 16
                wrapMode: Text.WordWrap
                color: root.colorText; font.pixelSize: 12
            }

            Rectangle {
                Layout.fillWidth: true; Layout.preferredHeight: 52
                color: root.colorSurfaceLight; radius: 8
                Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: root.colorBorder }
                Row {
                    anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter; spacing: 8
                    Rectangle {
                        implicitWidth: _cancelLbl.implicitWidth + 28; implicitHeight: 34; radius: 6
                        color: root.colorSurfaceLight; border.color: root.colorBorder; border.width: 1
                        Text { id: _cancelLbl; anchors.centerIn: parent; text: "Cancel"; color: root.colorTextSub; font.pixelSize: 12 }
                        TapHandler { onTapped: confirmDialog.reject() }
                    }
                    Rectangle {
                        implicitWidth: _okLbl.implicitWidth + 28; implicitHeight: 34; radius: 6
                        color: Qt.rgba(root.colorAccent.r, root.colorAccent.g, root.colorAccent.b, 0.12)
                        Text { id: _okLbl; anchors.centerIn: parent; text: "OK"; color: root.colorAccent; font.pixelSize: 12; font.weight: Font.Medium }
                        TapHandler { onTapped: confirmDialog.accept() }
                    }
                }
            }
        }
        onAccepted: {
            if      (actionId === "restart")       App.system.restartApp()
            else if (actionId === "shutdown")      App.system.shutdownPi()
            else if (actionId === "quit")          App.system.quitApp()
            else if (actionId === "update")        App.update.applyUpdate()
            else if (actionId === "clearCaptures") App.settings.clearAllCaptures()
            else if (actionId === "resetDefaults") {
                App.settings.resetToDefaults()
                Qt.callLater(function() { App.system.restartApp() })
            }
            else if (actionId === "deenergizeMotors") App.motion.deenergizeMotors()
        }
    }

    ObjectiveCalibrationWizard {
        id: calibWizard
    }

    JoystickCalibrationWizard {
        id: joystickWizard
    }

    StageLimitWizard {
        id: stageLimitWizard
    }

    // Main layout
    RowLayout {
        anchors.fill: parent; spacing: 0

        SettingsNavigation {
            currentPage: root.currentPage
            onPageSelected: function(page) { root.currentPage = page }
        }

        // Pages 
        StackLayout {
            Layout.fillWidth: true; Layout.fillHeight: true
            currentIndex: root.currentPage

            // Page 0: Objectives
            TouchScrollView {
                clip: true; contentWidth: availableWidth
                ColumnLayout {
                    x: 20; y: 16; width: parent.width - 40; spacing: 12

                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "Objective profiles"; color: root.colorText; font.pixelSize: 14; font.weight: Font.Medium; Layout.fillWidth: true }
                        Rectangle {
                            Layout.preferredHeight: 28; Layout.preferredWidth: _cwLbl.implicitWidth + 24; radius: 6
                            color: Qt.rgba(root.colorAccent.r,root.colorAccent.g,root.colorAccent.b,0.10)
                            Text { id: _cwLbl; anchors.centerIn: parent; text: "Calibration wizard..."; color: root.colorAccent; font.pixelSize: 11 }
                            TapHandler { onTapped: root.openObjectiveCalibrationWizard() }
                        }
                        Rectangle {
                            Layout.preferredHeight: 28; Layout.preferredWidth: _rdLbl.implicitWidth + 24; radius: 6
                            color: Qt.rgba(root.colorDanger.r,root.colorDanger.g,root.colorDanger.b,0.08)
                            Text { id: _rdLbl; anchors.centerIn: parent; text: "Reset defaults"; color: root.colorDanger; font.pixelSize: 11 }
                            TapHandler { onTapped: { confirmDialog.actionId = "resetDefaults"; confirmDialog.promptText = "Reset all settings to factory defaults and restart the app?"; confirmDialog.open() } }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true; spacing: 4
                        Repeater {
                            model: App.objective.objectiveNames
                            delegate: Rectangle {
                                id: objectiveSelectorDelegate
                                required property int index
                                required property string modelData

                                Layout.fillWidth: true; height: 30; radius: 6
                                property bool active: App.objective.activeObjective === objectiveSelectorDelegate.modelData
                                property string displayName: App.objective.objectiveDisplayNames[objectiveSelectorDelegate.index] ?? objectiveSelectorDelegate.modelData
                                color: active ? Qt.rgba(root.colorAccent.r,root.colorAccent.g,root.colorAccent.b,0.12) : root.colorSurfaceLight
                                border.color: active ? Qt.rgba(root.colorAccent.r,root.colorAccent.g,root.colorAccent.b,0.3) : "transparent"; border.width: 1
                                Text { anchors.centerIn: parent; text: parent.displayName; font.pixelSize: 12; font.weight: parent.active ? Font.Medium : Font.Normal; color: parent.active ? root.colorAccent : root.colorTextSub }
                                TapHandler { onTapped: App.objective.select(objectiveSelectorDelegate.modelData) }
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true; spacing: 12; Layout.alignment: Qt.AlignTop
                        SCard {
                            id: _nameCard
                            title: "NAME"
                            Layout.alignment: Qt.AlignTop
                            // Track which slot is currently shown
                            property string _slot: ""
                            function saveProfileFieldsForSlot(slot) {
                                var t = _nameInput.text.trim()
                                if (t !== "" && slot !== "")
                                    App.objective.renameObjective(slot, t)
                                var na = parseFloat(_naInput.text)
                                if (!isNaN(na) && na > 0 && slot !== "")
                                    App.objective.setNumericalApertureFor(slot, na)
                            }
                            Component.onCompleted: {
                                _slot = App.objective.activeObjective
                                _nameInput.text = App.objective.activeDisplayName
                                _naInput.text = App.objective.activeNumericalAperture.toFixed(2)
                            }
                            Connections {
                                target: App.objective
                                function onObjective_changed(newSlot) {
                                    // Save whatever is typed BEFORE the view updates
                                    _nameCard.saveProfileFieldsForSlot(_nameCard._slot)
                                    // Now update to the new objective name
                                    _nameCard._slot = newSlot
                                    _nameInput.text = App.objective.activeDisplayName
                                    _naInput.text = App.objective.activeNumericalAperture.toFixed(2)
                                }
                            }
                            Text { text: "Display name"; color: root.colorTextSub; font.pixelSize: 10 }
                            Rectangle {
                                Layout.fillWidth: true; Layout.preferredHeight: 28; radius: 4
                                color: root.colorSurfaceLight
                                border.color: _nameInput.activeFocus ? root.colorAccent : root.colorBorder
                                border.width: 1
                                TextInput {
                                    id: _nameInput
                                    anchors.fill: parent; anchors.margins: 8
                                    color: root.colorText; font.pixelSize: 11
                                    selectByMouse: true; clip: true
                                    onActiveFocusChanged: if (activeFocus) root.showInputPanel()
                                    // Save on Enter / de-focus
                                    onEditingFinished: {
                                        var t = text.trim()
                                        if (t !== "" && _nameCard._slot !== "")
                                            App.objective.renameObjective(_nameCard._slot, t)
                                    }
                                }
                            }
                            Text { text: "Numerical aperture"; color: root.colorTextSub; font.pixelSize: 10; Layout.topMargin: 4 }
                            Rectangle {
                                Layout.fillWidth: true; Layout.preferredHeight: 28; radius: 4
                                color: root.colorSurfaceLight
                                border.color: _naInput.activeFocus ? root.colorAccent : root.colorBorder
                                border.width: 1
                                TextInput {
                                    id: _naInput
                                    anchors.fill: parent; anchors.margins: 8
                                    color: root.colorText; font.pixelSize: 11
                                    selectByMouse: true; clip: true
                                    inputMethodHints: Qt.ImhFormattedNumbersOnly
                                    onActiveFocusChanged: if (activeFocus) root.showInputPanel()
                                    onEditingFinished: {
                                        var na = parseFloat(text)
                                        if (!isNaN(na) && na > 0)
                                            App.objective.setNumericalAperture(na)
                                        text = App.objective.activeNumericalAperture.toFixed(2)
                                    }
                                }
                            }
                        }
                        SCard {
                            title: "CALIBRATION"
                            Layout.alignment: Qt.AlignTop
                            SRow { label: "Numerical aperture"; value: App.objective.activeNumericalAperture.toFixed(2); mono: true }
                            SRow { label: "Scale (µm/px)";  value: App.objective.activeUmPerPixel.toFixed(4); mono: true }
                            SRow { label: "Stage X";         value: App.calibration.stageUmPerStepX.toFixed(6) + " µm/st"; mono: true }
                            SRow { label: "Stage Y";         value: App.calibration.stageUmPerStepY.toFixed(6) + " µm/st"; mono: true }
                            SRow { label: "Depth of field"; value: App.objective.activeDofSteps + " st"; mono: true }
                            SRow { label: "Stack step";     value: App.objective.activeFocusStackStep + " st"; mono: true }
                            SRow { label: "Backlash X";     value: App.objective.activeBacklashX + " st"; mono: true }
                            SRow { label: "Backlash Y";     value: App.objective.activeBacklashY + " st"; mono: true }
                            SRow { label: "Backlash Z";     value: App.objective.activeBacklashZ + " st"; mono: true }
                        }
                    }

                    // Detection settings
                    SCard {
                        title: "OBJECTIVE CHANGE DETECTION"
                        SRow {
                            label: "Enable detection"
                            SToggle { checked: App.objDetector.enabled; onToggled: function(v) { App.objDetector.setEnabled(v) } }
                        }
                        SRow {
                            label: "Autofocus after switch"; Layout.topMargin: 4
                            SToggle { checked: App.objDetector.autofocusOnSwitch; onToggled: function(v) { App.objDetector.setAutofocusOnSwitch(v) } }
                        }
                        Text { text: "THRESHOLDS"; color: root.colorTextSub; font.pixelSize: 10; font.weight: Font.Medium; font.letterSpacing: 0.7; Layout.topMargin: 8 }
                        SRow { label: "Dark level"; value: App.objDetector.darkThresholdPct.toFixed(0) + "% of avg" }
                        SSlider { value: App.objDetector.darkThresholdPct; from: 5; to: 40; stepSize: 1; onValueEdited: function(v) { App.objDetector.setDarkThresholdPct(v) } }
                        SRow { label: "Min dark duration"; value: App.objDetector.darkDurationMs + " ms"; Layout.topMargin: 4 }
                        SSlider { value: App.objDetector.darkDurationMs; from: 50; to: 800; stepSize: 50; onValueEdited: function(v) { App.objDetector.setDarkDurationMs(v) } }
                        SRow { label: "Recovery level"; value: App.objDetector.recoveryThresholdPct.toFixed(0) + "% of avg"; Layout.topMargin: 4 }
                        SSlider { value: App.objDetector.recoveryThresholdPct; from: 20; to: 70; stepSize: 5; onValueEdited: function(v) { App.objDetector.setRecoveryThresholdPct(v) } }
                    }
                    Item { Layout.preferredHeight: 32 }
                }
            }

            // Page 1: Input
            TouchScrollView {
                clip: true; contentWidth: availableWidth
                ColumnLayout {
                    x: 20; y: 16; width: parent.width - 40; spacing: 12
                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "Input configuration"; color: root.colorText; font.pixelSize: 14; font.weight: Font.Medium; Layout.fillWidth: true }
                        Rectangle {
                            implicitHeight: 28; radius: 6; implicitWidth: _joyWizLbl.implicitWidth + 24
                            color: Qt.rgba(root.colorAccent.r,root.colorAccent.g,root.colorAccent.b,0.10)
                            Text { id: _joyWizLbl; anchors.centerIn: parent; text: "Joystick wizard…"; color: root.colorAccent; font.pixelSize: 11 }
                            TapHandler { onTapped: joystickWizard.open() }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true; spacing: 12; Layout.alignment: Qt.AlignTop
                        SCard {
                            title: "DEADZONE + AXES"
                            SRow { label: "Deadzone"; value: App.settings.joystickDeadzonePct + "%" }
                            SSlider { value: App.settings.joystickDeadzonePct; from: 0; to: 50; stepSize: 1; onValueEdited: function(v) { App.settings.setJoystickDeadzonePct(v) } }
                            SRow { label: "Sensitivity"; value: App.settings.joystickSensitivityPct + "%" }
                            SSlider { value: App.settings.joystickSensitivityPct; from: 10; to: 300; stepSize: 5; onValueEdited: function(v) { App.settings.setJoystickSensitivityPct(v) } }
                            Text { text: "AXIS MAPPING"; color: root.colorTextSub; font.pixelSize: 10; font.weight: Font.Medium; font.letterSpacing: 0; Layout.topMargin: 6 }
                            SRow { label: "Swap X/Y axes"; SToggle { checked: App.settings.joystickSwapXY; onToggled: function(v) { App.settings.setJoystickSwapXY(v) } } }
                            SRow { label: "Invert X axis"; SToggle { checked: App.settings.joystickInvertX; onToggled: function(v) { App.settings.setJoystickInvertX(v) } } }
                            SRow { label: "Invert Y axis"; SToggle { checked: App.settings.joystickInvertY; onToggled: function(v) { App.settings.setJoystickInvertY(v) } } }
                        }
                        SCard {
                            title: "RESPONSE CURVE"
                            // Live curve preview. Note: Partially AI-generated
                            Canvas {
                                id: _curveCvs
                                Layout.fillWidth: true; height: 84
                                property string _cv: App.settings.joystickCurve
                                property int    _ex: App.settings.joystickExpoStrength
                                property bool   _dk: root.dark
                                on_CvChanged:   requestPaint()
                                on_ExChanged:   requestPaint()
                                on_DkChanged:   requestPaint()
                                onWidthChanged: requestPaint()
                                Component.onCompleted: requestPaint()
                                onPaint: {
                                    var ctx = getContext("2d")
                                    ctx.clearRect(0, 0, width, height)
                                    if (width < 4 || height < 4) return
                                    var pad = 8, w = width - 2*pad, h = height - 2*pad
                                    var dk = _dk
                                    // Background
                                    ctx.fillStyle = dk ? "rgba(46,46,46,1)" : "rgba(235,235,235,1)"
                                    ctx.fillRect(0, 0, width, height)
                                    // Grid
                                    ctx.strokeStyle = dk ? "rgba(255,255,255,0.07)" : "rgba(0,0,0,0.07)"
                                    ctx.lineWidth = 1; ctx.setLineDash([2,3])
                                    for (var i = 1; i < 4; i++) {
                                        ctx.beginPath(); ctx.moveTo(pad + w*i/4, pad); ctx.lineTo(pad + w*i/4, pad+h); ctx.stroke()
                                        ctx.beginPath(); ctx.moveTo(pad, pad + h*i/4); ctx.lineTo(pad+w, pad + h*i/4); ctx.stroke()
                                    }
                                    ctx.setLineDash([])
                                    // Linear reference (dashed, subtle)
                                    ctx.strokeStyle = dk ? "rgba(255,255,255,0.14)" : "rgba(0,0,0,0.12)"
                                    ctx.lineWidth = 1; ctx.setLineDash([3,3])
                                    ctx.beginPath(); ctx.moveTo(pad, pad+h); ctx.lineTo(pad+w, pad); ctx.stroke()
                                    ctx.setLineDash([])
                                    // Curve
                                    ctx.strokeStyle = root.colorAccent; ctx.lineWidth = 2
                                    ctx.beginPath()
                                    var curve = _cv, expo = _ex / 100.0, steps = 60
                                    for (var j = 0; j <= steps; j++) {
                                        var t = j / steps, s
                                        if (curve === "linear")       s = t
                                        else if (curve === "exponential") s = Math.pow(t, 1.0 + expo * 2.0)
                                        else                          s = t*t*(3.0 - 2.0*t)
                                        var px = pad + t*w, py = pad + (1.0 - s)*h
                                        if (j === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py)
                                    }
                                    ctx.stroke()
                                }

                                Row {
                                    anchors.left: parent.left; anchors.top: parent.top
                                    anchors.leftMargin: 9; anchors.topMargin: 9
                                    spacing: 2
                                    Text {
                                        text: "Speed"
                                        color: _curveCvs._dk ? Qt.rgba(1,1,1,0.32) : Qt.rgba(0,0,0,0.30)
                                        font.pixelSize: 8
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                    Icon {
                                        code: "\uf077"; iconSize: 8
                                        color: _curveCvs._dk ? Qt.rgba(1,1,1,0.32) : Qt.rgba(0,0,0,0.30)
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                }
                                Row {
                                    anchors.right: parent.right; anchors.bottom: parent.bottom
                                    anchors.rightMargin: 9; anchors.bottomMargin: 9
                                    spacing: 2
                                    Text {
                                        text: "Deflection"
                                        color: _curveCvs._dk ? Qt.rgba(1,1,1,0.32) : Qt.rgba(0,0,0,0.30)
                                        font.pixelSize: 8
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                    Icon {
                                        code: "\uf054"; iconSize: 8
                                        color: _curveCvs._dk ? Qt.rgba(1,1,1,0.32) : Qt.rgba(0,0,0,0.30)
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                }
                            }
                            // Curve selector
                            RowLayout {
                                Layout.fillWidth: true; spacing: 4
                                Repeater {
                                    model: [
                                        { label: "Linear",      curveKey: "linear"      },
                                        { label: "Exponential", curveKey: "exponential" },
                                        { label: "S-curve",     curveKey: "scurve"      }
                                    ]
                                    delegate: Rectangle {
                                        id: joystickCurveDelegate
                                        required property var modelData

                                        Layout.fillWidth: true; height: 26; radius: 5
                                        property bool active: App.settings.joystickCurve === joystickCurveDelegate.modelData.curveKey
                                        color: active ? Qt.rgba(root.colorAccent.r,root.colorAccent.g,root.colorAccent.b,0.1) : root.colorSurfaceLight
                                        border.color: active ? Qt.rgba(root.colorAccent.r,root.colorAccent.g,root.colorAccent.b,0.25) : "transparent"; border.width: 1
                                        Text { anchors.centerIn: parent; text: joystickCurveDelegate.modelData.label; font.pixelSize: 11; font.weight: parent.active ? Font.Medium : Font.Normal; color: parent.active ? root.colorAccent : root.colorTextSub }
                                        TapHandler { onTapped: App.settings.setJoystickCurve(joystickCurveDelegate.modelData.curveKey) }
                                    }
                                }
                            }
                            SRow { visible: App.settings.joystickCurve === "exponential"; label: "Expo strength"; value: App.settings.joystickExpoStrength + "%"; Layout.topMargin: 4 }
                            SSlider { visible: App.settings.joystickCurve === "exponential"; value: App.settings.joystickExpoStrength; from: 0; to: 100; stepSize: 1; onValueEdited: function(v) { App.settings.setJoystickExpoStrength(v) } }
                        }
                    }

                    SCard {
                        title: "MOTION"
                        Layout.fillWidth: true

                        SRow { label: "Pan speed"; value: App.settings.maxPanSpeedPxPerSec + " px/s" }
                        SSlider {
                            value: App.settings.maxPanSpeedPxPerSec; from: 10; to: 4000; stepSize: 10
                            onValueEdited: function(v) { App.settings.setMaxPanSpeedPxPerSec(Math.round(v)) }
                        }

                        SRow { label: "Z encoder sensitivity"; value: App.settings.zEncoderSensitivityPct + "%"; Layout.topMargin: 8 }
                        SSlider {
                            value: App.settings.zEncoderSensitivityPct; from: 25; to: 400; stepSize: 5
                            onValueEdited: function(v) { App.settings.setZEncoderSensitivityPct(v) }
                        }

                        SRow { label: "Z encoder step multiplier"; value: App.settings.zEncoderStepMultiplier.toFixed(2) + "×"; Layout.topMargin: 8 }
                        SSlider {
                            value: App.settings.zEncoderStepMultiplier; from: 0.25; to: 4.0; stepSize: 0.05
                            onValueEdited: function(v) { App.settings.setZEncoderStepMultiplier(v) }
                        }
                        Text {
                            text: "1 click = " + Math.max(1, Math.round(App.objective.activeFocusStackStep * App.settings.zEncoderStepMultiplier)) + " steps for the active objective."
                            color: root.colorTextSub; font.pixelSize: 10; Layout.fillWidth: true; Layout.topMargin: 2
                        }
                    }

                    Item { Layout.preferredHeight: 32 }
                }
            }

            // Page 2: Motors
            TouchScrollView {
                clip: true; contentWidth: availableWidth
                ColumnLayout {
                    x: 20; y: 16; width: parent.width - 40; spacing: 12
                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "Motor controls"; color: root.colorText; font.pixelSize: 14; font.weight: Font.Medium; Layout.fillWidth: true }
                        Rectangle {
                            Layout.preferredHeight: 28; radius: 6
                            Layout.preferredWidth: _deenLbl.implicitWidth + 24
                            color: Qt.rgba(root.colorDanger.r,root.colorDanger.g,root.colorDanger.b,0.08)
                            Text { id: _deenLbl; anchors.centerIn: parent; text: "Deenergize motors"; color: root.colorDanger; font.pixelSize: 11 }
                            TapHandler { onTapped: { confirmDialog.actionId = "deenergizeMotors"; confirmDialog.promptText = "Release motor current? The stage may drift and any running scan/autofocus will be disrupted."; confirmDialog.open() } }
                        }
                    }

                    SCard {
                        title: "XYZ AXIS CONTROLS"
                        SRow { label: "Position"; value: "X " + App.motion.posX + "  Y " + App.motion.posY + "  Z " + App.motion.posZ; mono: true }
                        SRow { label: "Jog step"; value: root.motorJogStep + " steps"; Layout.topMargin: 4 }
                        RowLayout {
                            Layout.fillWidth: true; spacing: 4
                            Repeater {
                                model: [10, 100, 500, 1000]
                                delegate: Rectangle {
                                    id: jogStepDelegate
                                    required property int modelData

                                    Layout.fillWidth: true; Layout.preferredHeight: 28; radius: 5
                                    property bool active: root.motorJogStep === jogStepDelegate.modelData
                                    color: active ? Qt.rgba(root.colorAccent.r, root.colorAccent.g, root.colorAccent.b, 0.12) : root.colorSurfaceLight
                                    border.color: active ? Qt.rgba(root.colorAccent.r, root.colorAccent.g, root.colorAccent.b, 0.28) : "transparent"
                                    border.width: 1
                                    Text {
                                        anchors.centerIn: parent
                                        text: jogStepDelegate.modelData
                                        color: parent.active ? root.colorAccent : root.colorTextSub
                                        font.pixelSize: 11
                                        font.weight: parent.active ? Font.Medium : Font.Normal
                                        font.family: "Courier New"
                                    }
                                    MouseArea { anchors.fill: parent; onClicked: root.motorJogStep = jogStepDelegate.modelData }
                                }
                            }
                        }
                        GridLayout {
                            Layout.fillWidth: true; Layout.topMargin: 6
                            columns: 3; columnSpacing: 8; rowSpacing: 6
                            Text { text: "X"; color: root.colorTextSub; font.pixelSize: 10; font.weight: Font.Medium; horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true }
                            Text { text: "Y"; color: root.colorTextSub; font.pixelSize: 10; font.weight: Font.Medium; horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true }
                            Text { text: "Z"; color: root.colorTextSub; font.pixelSize: 10; font.weight: Font.Medium; horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true }
                            SJogButton { label: "X-"; onTapped: App.motion.moveRelXY(-root.motorJogStep, 0) }
                            SJogButton { label: "Y-"; onTapped: App.motion.moveRelXY(0, -root.motorJogStep) }
                            SJogButton { label: "Z-"; onTapped: App.motion.moveZ_rel(-root.motorJogStep) }
                            SJogButton { label: "X+"; onTapped: App.motion.moveRelXY(root.motorJogStep, 0) }
                            SJogButton { label: "Y+"; onTapped: App.motion.moveRelXY(0, root.motorJogStep) }
                            SJogButton { label: "Z+"; onTapped: App.motion.moveZ_rel(root.motorJogStep) }
                        }
                    }
                    SCard {
                        title: "SANGABOARD TIMING"
                        SRow { label: "Status"; value: App.status.sangaboardConnected ? "Connected" : "Disconnected" }
                        SRow { label: "Step time"; value: App.settings.sangaboardStepTimeUs + " µs"; Layout.topMargin: 4 }
                        SSlider {
                            value: App.settings.sangaboardStepTimeUs; from: 50; to: 10000; stepSize: 50
                            onValueEdited: function(v) { App.settings.setSangaboardStepTimeUs(Math.round(v / 50) * 50) }
                        }
                        SRow { label: "Ramp time"; value: (App.settings.sangaboardRampTimeUs / 1000).toFixed(0) + " ms"; Layout.topMargin: 8 }
                        SSlider {
                            value: App.settings.sangaboardRampTimeUs; from: 0; to: 500000; stepSize: 5000
                            onValueEdited: function(v) { App.settings.setSangaboardRampTimeUs(Math.round(v / 5000) * 5000) }
                        }
                    }
                    SCard {
                        title: "STAGE SOFT LIMITS"
                        SRow { label: "Status"; value: App.motion.softLimitsCalibrated ? (App.motion.softLimitsEnabled ? "Enabled" : "Disabled") : "Not calibrated" }
                        SRow { label: "Current"; value: "X " + App.motion.posX + "  Y " + App.motion.posY + "  Z " + App.motion.posZ; mono: true }
                        SRow {
                            label: "X range"
                            value: App.motion.softLimitsCalibrated ? (App.motion.softLimitXMin + " to " + App.motion.softLimitXMax) : "-"
                            mono: true
                        }
                        SRow {
                            label: "Y range"
                            value: App.motion.softLimitsCalibrated ? (App.motion.softLimitYMin + " to " + App.motion.softLimitYMax) : "-"
                            mono: true
                        }
                        SRow {
                            label: "Enable soft limits"
                            SToggle {
                                enabled: App.motion.softLimitsCalibrated
                                opacity: enabled ? 1.0 : 0.45
                                checked: App.motion.softLimitsEnabled
                                onToggled: function(v) { App.motion.setSoftLimitsEnabled(v) }
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true; spacing: 8; Layout.topMargin: 4
                            SBtn {
                                label: "Calibrate..."
                                btnColor: root.colorAccent
                                btnBg: Qt.rgba(root.colorAccent.r, root.colorAccent.g, root.colorAccent.b, 0.12)
                                onTapped: {
                                    App.motion.startStageLimitWizard()
                                }
                            }
                            SBtn {
                                label: "Clear"
                                enabled: App.motion.softLimitsCalibrated
                                opacity: enabled ? 1.0 : 0.45
                                btnColor: root.colorDanger
                                btnBg: Qt.rgba(root.colorDanger.r, root.colorDanger.g, root.colorDanger.b, 0.08)
                                onTapped: if (enabled) App.motion.clearSoftLimits()
                            }
                        }
                    }
                    Item { Layout.preferredHeight: 32 }
                }
            }

            // Page 3: GPIO buttons
            TouchScrollView {
                clip: true; contentWidth: availableWidth
                ColumnLayout {
                    x: 20; y: 16; width: parent.width - 40; spacing: 8
                    Text { text: "GPIO button mapping"; color: root.colorText; font.pixelSize: 14; font.weight: Font.Medium }

                    Repeater {
                        model: App.buttons.mappingModel
                        delegate: Rectangle {
                            id: _btnRow
                            Layout.fillWidth: true; height: 52; radius: 8
                            color: root.colorSurface; border.color: root.colorBorder; border.width: 1
                            required property int index
                            required property var modelData
                            property int btnIndex: _btnRow.index

                            Connections {
                                target: App.buttons
                                function onButton_pressed(idx) {
                                    if (idx === _btnRow.btnIndex) _flashAnim.restart()
                                }
                            }

                            RowLayout {
                                anchors.fill: parent; anchors.margins: 10; spacing: 10
                                Rectangle {
                                    id: _badge
                                    Layout.preferredWidth: 36; Layout.preferredHeight: 36; radius: 8
                                    color: Qt.rgba(root.colorAccent.r,root.colorAccent.g,root.colorAccent.b,0.08)
                                    Text { anchors.centerIn: parent; text: String.fromCharCode(65 + _btnRow.btnIndex); color: root.colorAccent; font.pixelSize: 16; font.weight: Font.Medium }

                                    SequentialAnimation {
                                        id: _flashAnim
                                        ColorAnimation { target: _badge; property: "color"; to: root.colorAccent; duration: 60 }
                                        ColorAnimation { target: _badge; property: "color"; to: Qt.rgba(root.colorAccent.r,root.colorAccent.g,root.colorAccent.b,0.08); duration: 300 }
                                    }
                                }
                                Text { text: "Action"; color: root.colorTextSub; font.pixelSize: 11 }
                                ComboBox {
                                    id: _cb
                                    Layout.fillWidth: true
                                    model: App.buttons.availableActionLabels
                                    currentIndex: App.buttons.availableActionIds.indexOf(_btnRow.modelData)
                                    // Use _btnRow.btnIndex to identify which button, actionId for which action
                                    onActivated: function(actionIdx) {
                                        App.buttons.setAction(_btnRow.btnIndex, App.buttons.availableActionIds[actionIdx])
                                    }
                                    font.pixelSize: 11
                                    contentItem: Text {
                                        leftPadding: 10; text: _cb.displayText; color: root.colorText; font.pixelSize: 11; verticalAlignment: Text.AlignVCenter
                                    }
                                    background: Rectangle { color: root.colorSurfaceLight; radius: 5; border.color: root.colorBorder; border.width: 1 }
                                    popup: Popup {
                                        y: _cb.height + 2; width: _cb.width; padding: 4
                                        background: Rectangle { color: root.colorSurface; border.color: root.colorBorder; border.width: 1; radius: 6 }
                                        contentItem: ListView {
                                            clip: true
                                            acceptedButtons: Qt.LeftButton
                                            implicitHeight: Math.min(contentHeight, 220)
                                            model: _cb.model
                                            ScrollIndicator.vertical: ScrollIndicator {}
                                            delegate: ItemDelegate {
                                                id: actionDelegate
                                                required property int index
                                                required property string modelData
                                                width: _cb.width - 8; height: 32
                                                highlighted: _cb.highlightedIndex === actionDelegate.index
                                                contentItem: Text {
                                                    text: actionDelegate.modelData; color: root.colorText; font.pixelSize: 11
                                                    verticalAlignment: Text.AlignVCenter; leftPadding: 6
                                                }
                                                background: Rectangle {
                                                    color: actionDelegate.highlighted ? Qt.rgba(root.colorAccent.r,root.colorAccent.g,root.colorAccent.b,0.08) : "transparent"
                                                    radius: 4
                                                }
                                                onClicked: {
                                                    _cb.currentIndex = actionDelegate.index
                                                    _cb.popup.close()
                                                    App.buttons.setAction(_btnRow.btnIndex, App.buttons.availableActionIds[actionDelegate.index])
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                    Item { Layout.preferredHeight: 32 }
                }
            }

            // Page 4: Camera
            TouchScrollView {
                clip: true; contentWidth: availableWidth
                ColumnLayout {
                    x: 20; y: 16; width: parent.width - 40; spacing: 12
                    Text { text: "Camera"; color: root.colorText; font.pixelSize: 14; font.weight: Font.Medium }

                    RowLayout {
                        Layout.fillWidth: true; spacing: 12; Layout.alignment: Qt.AlignTop

                        // Left col: Device + Status
                        ColumnLayout {
                            Layout.fillWidth: true; Layout.alignment: Qt.AlignTop; spacing: 12
                            SCard {
                                title: "DEVICE"
                                SRow { label: "V4L2 device" }
                                STextInput { value: App.settings.cameraDevice; mono: true; onCommitted: function(t) { App.settings.setCameraDevice(t) } }
                                Text { text: "ANALYSIS RESOLUTION"; color: root.colorTextSub; font.pixelSize: 10; font.weight: Font.Medium; font.letterSpacing: 0.7; Layout.topMargin: 6 }
                                Row {
                                    spacing: 3
                                    Repeater {
                                        model: App.cameraResolutionOptions.length > 0
                                               ? App.cameraResolutionOptions
                                               : ["1280x720","960x540","640x360"]
                                        delegate: Rectangle {
                                            id: resolutionDelegate
                                            required property string modelData

                                            property string normalized: String(resolutionDelegate.modelData).replace("×","x")
                                            property bool active: App.settings.cameraResolution === normalized
                                            height: 22; radius: 4; width: _rt.implicitWidth + 14
                                            color: active ? Qt.rgba(root.colorAccent.r,root.colorAccent.g,root.colorAccent.b,0.1) : root.colorSurfaceLight
                                            border.color: active ? Qt.rgba(root.colorAccent.r,root.colorAccent.g,root.colorAccent.b,0.25) : "transparent"; border.width: active ? 1 : 0
                                            Text { id: _rt; anchors.centerIn: parent; text: parent.normalized.replace("x","×"); font.pixelSize: 10; font.weight: parent.active ? Font.Medium : Font.Normal; color: parent.active ? root.colorAccent : root.colorTextSub }
                                            TapHandler { onTapped: App.settings.setCameraResolution(parent.normalized) }
                                        }
                                    }
                                }
                                Text { text: "ANALYSIS RATE"; color: root.colorTextSub; font.pixelSize: 10; font.weight: Font.Medium; font.letterSpacing: 0.7; Layout.topMargin: 6 }
                                Row {
                                    spacing: 3
                                    Repeater {
                                        model: App.cameraFpsOptions.length > 0 ? App.cameraFpsOptions : [10, 8, 4, 2]
                                        delegate: Rectangle {
                                            id: fpsDelegate
                                            required property var modelData

                                            property int fpsValue: Number(fpsDelegate.modelData)
                                            property bool active: App.settings.cameraFps === fpsValue
                                            height: 22; radius: 4; width: _ft.implicitWidth + 14
                                            color: active ? Qt.rgba(root.colorAccent.r,root.colorAccent.g,root.colorAccent.b,0.1) : root.colorSurfaceLight
                                            border.color: active ? Qt.rgba(root.colorAccent.r,root.colorAccent.g,root.colorAccent.b,0.25) : "transparent"; border.width: active ? 1 : 0
                                            Text { id: _ft; anchors.centerIn: parent; text: parent.fpsValue + " fps"; font.pixelSize: 10; font.weight: parent.active ? Font.Medium : Font.Normal; color: parent.active ? root.colorAccent : root.colorTextSub }
                                            TapHandler { onTapped: App.settings.setCameraFps(parent.fpsValue) }
                                        }
                                    }
                                }
                            }
                            SCard {
                                title: "STATUS"
                                SRow { label: "Device";       value: App.settings.cameraDevice; mono: true }
                                SRow { label: "Preview";      value: (App.cameraResolution || "n/a") + "  @  " + (App.cameraFps > 0 ? App.cameraFps.toFixed(0) : "n/a") + " fps"; Layout.topMargin: 4 }
                                SRow { label: "Analysis";     value: App.settings.cameraResolution + "  @  " + App.settings.cameraFps + " fps"; Layout.topMargin: 4 }
                            }
                        }

                        // Right col: Capture
                        SCard {
                            title: "CAPTURE"
                            RowLayout {
                                Layout.fillWidth: true
                                Text { text: "Image format"; color: root.colorTextSub; font.pixelSize: 11; Layout.fillWidth: true }
                                Row {
                                    spacing: 3
                                    Repeater {
                                        model: ["OME-TIFF"]
                                        delegate: Rectangle {
                                            id: imageFormatDelegate
                                            required property string modelData

                                            property bool active: App.settings.cameraImageFormat === imageFormatDelegate.modelData
                                            height: 22; radius: 4; width: _fmtt.implicitWidth + 14
                                            color: active ? Qt.rgba(root.colorAccent.r,root.colorAccent.g,root.colorAccent.b,0.1) : root.colorSurfaceLight
                                            border.color: active ? Qt.rgba(root.colorAccent.r,root.colorAccent.g,root.colorAccent.b,0.25) : "transparent"; border.width: active ? 1 : 0
                                            Text { id: _fmtt; anchors.centerIn: parent; text: imageFormatDelegate.modelData; font.pixelSize: 10; font.weight: parent.active ? Font.Medium : Font.Normal; color: parent.active ? root.colorAccent : root.colorTextSub }
                                            TapHandler { onTapped: App.settings.setCameraImageFormat(imageFormatDelegate.modelData) }
                                        }
                                    }
                                }
                            }
                            Text { text: "NAMING PATTERN"; color: root.colorTextSub; font.pixelSize: 10; font.weight: Font.Medium; font.letterSpacing: 0.7; Layout.topMargin: 6 }
                            STextInput { value: App.settings.cameraNamingPattern; mono: true; onCommitted: function(t) { App.settings.setCameraNamingPattern(t) } }
                            Text { text: "Tokens: {date} {time} {obj} {seq}"; color: root.colorTextSub; font.pixelSize: 9; font.family: "Courier New" }
                            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: root.colorBorder; Layout.topMargin: 8; Layout.bottomMargin: 4 }
                            Text { text: "PERFORMANCE DEBUG"; color: root.colorTextSub; font.pixelSize: 10; font.weight: Font.Medium; font.letterSpacing: 0.7 }
                            SRow {
                                label: "Frame analysis"
                                SToggle {
                                    checked: App.settings.cameraFrameAnalysisEnabled
                                    onToggled: function(v) { App.settings.setCameraFrameAnalysisEnabled(v) }
                                }
                            }
                            SRow {
                                label: "Live video feed"
                                SToggle {
                                    checked: App.settings.cameraLiveVideoEnabled
                                    onToggled: function(v) { App.settings.setCameraLiveVideoEnabled(v) }
                                }
                            }
                        }
                    }

                    // Autofocus: All settings always visible
                    SCard {
                        title: "AUTOFOCUS"
                        Layout.fillWidth: true

                        Text {
                            text: "Speed preset"
                            color: root.colorTextSub
                            font.pixelSize: 11
                        }
                        SegmentedButtonGroup {
                            Layout.fillWidth: true
                            itemHeight: 28
                            itemRadius: 5
                            fontSize: 11
                            model: [
                                { label: "Fast",     value: "fast"     },
                                { label: "Balanced", value: "balanced" },
                                { label: "Slow",     value: "slow"     },
                                { label: "Custom",   value: "custom"   }
                            ]
                            currentValue: App.settings.autofocusSpeedPreset
                            onSelected: function(v) { App.settings.setAutofocusSpeedPreset(v) }
                        }

                        SRow {
                            label: "Min focus confidence"
                            value: App.settings.autofocusMinConfidence.toFixed(0)
                            Layout.topMargin: 8
                        }
                        SSlider {
                            value: App.settings.autofocusMinConfidence
                            from: 0; to: 1000; stepSize: 5
                            onValueEdited: function(v) { App.settings.setAutofocusMinConfidence(v) }
                        }
                        Text {
                            text: "Refuse to commit when best peak's raw variance is below this. 0 disables."
                            color: root.colorTextSub; font.pixelSize: 10; wrapMode: Text.WordWrap
                            Layout.fillWidth: true; Layout.topMargin: 2
                        }

                        SRow { label: "Settle delay"; value: App.settings.autofocusSettleMs + " ms"; Layout.topMargin: 8 }
                        SSlider {
                            value: App.settings.autofocusSettleMs
                            from: 1000; to: 3000; stepSize: 100
                            onValueEdited: function(v) { App.settings.setAutofocusSettleMs(v) }
                        }

                        SRow { label: "Move-start delay"; value: App.settings.autofocusMoveStartMs + " ms"; Layout.topMargin: 4 }
                        SSlider {
                            value: App.settings.autofocusMoveStartMs
                            from: 1000; to: 3000; stepSize: 100
                            onValueEdited: function(v) { App.settings.setAutofocusMoveStartMs(v) }
                        }

                        SRow { label: "Coarse positions"; value: App.settings.autofocusCoarsePositions; Layout.topMargin: 4 }
                        SSlider {
                            value: App.settings.autofocusCoarsePositions
                            from: 7; to: 41; stepSize: 2
                            onValueEdited: function(v) { App.settings.setAutofocusCoarsePositions(v) }
                        }

                        SRow { label: "Fine positions"; value: App.settings.autofocusFinePositions; Layout.topMargin: 4 }
                        SSlider {
                            value: App.settings.autofocusFinePositions
                            from: 5; to: 41; stepSize: 2
                            onValueEdited: function(v) { App.settings.setAutofocusFinePositions(v) }
                        }

                        SRow { label: "Samples per position"; value: App.settings.autofocusSamplesPerPosition; Layout.topMargin: 4 }
                        SSlider {
                            value: App.settings.autofocusSamplesPerPosition
                            from: 1; to: 5; stepSize: 1
                            onValueEdited: function(v) { App.settings.setAutofocusSamplesPerPosition(v) }
                        }
                    }

                    Item { Layout.preferredHeight: 32 }
                }
            }

            // Page 5: Storage
            TouchScrollView {
                id: _storagePage; clip: true; contentWidth: availableWidth
                onVisibleChanged: { if (visible) App.settings.refreshStorage() }
                ColumnLayout {
                    x: 20; y: 16; width: parent.width - 40; spacing: 12
                    Text { text: "Storage"; color: root.colorText; font.pixelSize: 14; font.weight: Font.Medium }

                    RowLayout {
                        Layout.fillWidth: true; spacing: 12; Layout.alignment: Qt.AlignTop
                        SCard {
                            Text { text: "SAVE LOCATION"; color: root.colorTextSub; font.pixelSize: 10; font.weight: Font.Medium; font.letterSpacing: 0.7 }
                            STextInput { value: App.settings.captureRoot; mono: true; onCommitted: function(t) { App.settings.setCaptureRoot(t) } }
                            Text { text: "New captures use this location immediately."; color: root.colorTextSub; font.pixelSize: 9 }
                        }
                        SCard {
                            title: "DISK USAGE"
                            Rectangle {
                                Layout.fillWidth: true; height: 12; radius: 6; color: root.colorSurfaceLight; clip: true
                                Rectangle { width: parent.width * App.settings.diskUsedFraction; height: 12; color: root.colorAccent; radius: 3 }
                            }
                            Text {
                                text: App.settings.diskUsedGb.toFixed(1) + " GB used of " + App.settings.diskTotalGb.toFixed(0) + " GB"
                                color: root.colorTextSub; font.pixelSize: 10
                            }
                            SRow { label: "Total captures"; value: App.settings.captureCount.toString() }
                            SBtn {
                                label: "Clear all captures"; btnColor: root.colorDanger
                                btnBg: Qt.rgba(root.colorDanger.r,root.colorDanger.g,root.colorDanger.b,0.08); Layout.topMargin: 4
                                onTapped: { confirmDialog.actionId = "clearCaptures"; confirmDialog.promptText = "Delete all captures? This cannot be undone."; confirmDialog.open() }
                            }
                        }
                    }
                    Item { Layout.preferredHeight: 32 }
                }
            }

            // Page 6: System
            TouchScrollView {
                clip: true; contentWidth: availableWidth
                ColumnLayout {
                    x: 20; y: 16; width: parent.width - 40; spacing: 12
                    Text { text: "System"; color: root.colorText; font.pixelSize: 14; font.weight: Font.Medium }

                    // Application (left) + Software updates (right)
                    RowLayout {
                        Layout.fillWidth: true; spacing: 12; Layout.alignment: Qt.AlignTop

                        // Left col: Application
                        SCard {
                            title: "APPLICATION"
                            SRow { label: "Dark mode"; SToggle { checked: App.overlay.darkTheme; onToggled: function(v) { App.overlay.setDarkTheme(v) } } }
                            Rectangle {
                                Layout.fillWidth: true; height: 36; radius: 6; Layout.topMargin: 6
                                color: Qt.rgba(root.colorWarning.r,root.colorWarning.g,root.colorWarning.b,0.08)
                                Row { anchors.centerIn: parent; spacing: 7
                                    Icon { code: "\uf021"; iconSize: 14; color: root.colorWarning; anchors.verticalCenter: parent.verticalCenter }
                                    Text { text: "Restart application"; color: root.colorWarning; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                                }
                                TapHandler { onTapped: { confirmDialog.actionId = "restart"; confirmDialog.promptText = "Restart the application?"; confirmDialog.open() } }
                            }
                            Rectangle {
                                Layout.fillWidth: true; height: 36; radius: 6; Layout.topMargin: 4
                                color: Qt.rgba(root.colorDanger.r,root.colorDanger.g,root.colorDanger.b,0.08)
                                opacity: App.system.isPi ? 1.0 : 0.4
                                Row { anchors.centerIn: parent; spacing: 7
                                    Icon { code: "\uf011"; iconSize: 14; color: root.colorDanger; anchors.verticalCenter: parent.verticalCenter }
                                    Text { text: App.system.isPi ? "Shutdown Pi" : "Shutdown Pi  (Pi only)"; color: root.colorDanger; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                                }
                                TapHandler { onTapped: { if (App.system.isPi) { confirmDialog.actionId = "shutdown"; confirmDialog.promptText = "Shut down the Raspberry Pi?"; confirmDialog.open() } } }
                            }
                            Rectangle {
                                Layout.fillWidth: true; height: 36; radius: 6; Layout.topMargin: 4
                                color: Qt.rgba(root.colorTextSub.r,root.colorTextSub.g,root.colorTextSub.b,0.06); border.color: root.colorBorder; border.width: 1
                                Text { anchors.centerIn: parent; text: "Quit application"; color: root.colorTextSub; font.pixelSize: 11 }
                                TapHandler { onTapped: { confirmDialog.actionId = "quit"; confirmDialog.promptText = "Quit the application?"; confirmDialog.open() } }
                            }
                        }

                        // Right col: Software updates
                        ColumnLayout {
                            Layout.fillWidth: true; Layout.alignment: Qt.AlignTop; spacing: 12

                            SCard {
                                title: "SOFTWARE UPDATES"
                                RowLayout {
                                    Layout.fillWidth: true; spacing: 14
                                    Rectangle {
                                        Layout.preferredWidth: 40; Layout.preferredHeight: 40; radius: 10
                                        color: Qt.rgba(root.colorAccent.r,root.colorAccent.g,root.colorAccent.b,0.08)
                                        Icon { anchors.centerIn: parent; code: App.update.updateAvailable ? "\uf019" : "\uf058"; iconSize: 18; color: root.colorAccent }
                                    }
                                    ColumnLayout {
                                        Layout.fillWidth: true; Layout.minimumWidth: 0; spacing: 2
                                        Text {
                                            Layout.fillWidth: true; Layout.minimumWidth: 0
                                            text: App.update.updateAvailable ? "Update available!" : "Up to date"
                                            color: root.colorText; font.pixelSize: 13
                                            elide: Text.ElideRight; maximumLineCount: 1
                                        }
                                        Text {
                                            Layout.fillWidth: true; Layout.minimumWidth: 0
                                            text: App.update.statusMessage !== "" ? App.update.statusMessage : ("Version " + App.update.currentVersion)
                                            color: root.colorTextSub; font.pixelSize: 11
                                            elide: Text.ElideRight; maximumLineCount: 1
                                        }
                                    }
                                    Rectangle {
                                        visible: App.update.updateAvailable && !App.update.applying
                                        Layout.preferredWidth: 96; Layout.preferredHeight: 30
                                        Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                                        radius: 6
                                        color: Qt.rgba(root.colorAccent.r,root.colorAccent.g,root.colorAccent.b,0.1)
                                        Text { id: _applyT; anchors.centerIn: parent; text: "Apply update"; color: root.colorAccent; font.pixelSize: 11 }
                                        TapHandler { onTapped: { confirmDialog.actionId = "update"; confirmDialog.promptText = "Apply update and restart?"; confirmDialog.open() } }
                                    }
                                    Rectangle {
                                        visible: !App.update.updateAvailable && !App.update.applying
                                        Layout.preferredWidth: 86; Layout.preferredHeight: 30
                                        Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                                        radius: 6
                                        color: Qt.rgba(root.colorAccent.r,root.colorAccent.g,root.colorAccent.b,0.1)
                                        Text { id: _checkT; anchors.centerIn: parent; text: App.update.checking ? "Checking…" : "Check now"; color: root.colorAccent; font.pixelSize: 11 }
                                        TapHandler { onTapped: if (!App.update.checking) App.update.checkForUpdates() }
                                    }
                                }
                            }

                            SCard {
                                title: "UPDATE OPTIONS"
                                SRow { label: "Restart after update"; SToggle { checked: App.settings.restartAfterUpdate; onToggled: function(v) { App.settings.setRestartAfterUpdate(v) } } }
                            }
                        }
                    }

                    Item { Layout.preferredHeight: 32 }
                }
            }

            // Page 7: About
            TouchScrollView {
                clip: true; contentWidth: availableWidth
                ColumnLayout {
                    x: 20; y: 16; width: parent.width - 40; spacing: 12
                    Text { text: "About"; color: root.colorText; font.pixelSize: 14; font.weight: Font.Medium }
                    RowLayout {
                        Layout.fillWidth: true; spacing: 12; Layout.alignment: Qt.AlignTop
                        SCard {
                            title: "SOFTWARE"
                            SRow { label: "Version";  value: App.update.currentVersion }
                            SRow { label: "Platform"; value: App.system.isPi ? "Raspberry Pi OS" : "macOS (mock)" }
                            SRow { label: "Python";   value: App.system.pythonVersion }
                            SRow { label: "PySide6";  value: App.system.pyside6Version }
                            SRow { label: "OpenCV";   value: App.system.opencvVersion }
                            SRow { label: "Mock mode"; value: App.isMockMode ? "Yes" : "No" }
                        }
                        SCard {
                            title: "HARDWARE"
                            SRow { label: "Board";      value: App.system.isPi ? "Raspberry Pi 4B" : "Mac (dev)" }
                            SRow { label: "Display";    value: Screen.width + "×" + Screen.height + (App.system.isPi ? " DSI" : "") }
                            SRow { label: "Sangaboard"; value: App.status.sangaboardConnected ? "Connected" : "Disconnected" }
                            SRow { label: "Camera";     value: App.settings.cameraDevice }
                            SRow { label: "Config"; value: App.system.configPath; mono: true; elideLeft: true }
                        }
                    }
                    Item { Layout.preferredHeight: 32 }
                }
            }

        } // StackLayout
    } // RowLayout
}
