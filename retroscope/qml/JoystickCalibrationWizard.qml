pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "components"
import RetroScope 1.0

// Joystick calibration wizard
Dialog {
    id: joystickWizard

    Theme {
        id: theme
    }
    modal: true
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: 480
    closePolicy: Popup.CloseOnEscape

    property int step: 0
    property int pendingDeadzonePct: 8
    property int originalDeadzonePct: 8
    property bool deadzoneCommitted: false

    function initState() {
        step = 0
        originalDeadzonePct = App.settings.joystickDeadzonePct
        pendingDeadzonePct = App.settings.joystickDeadzonePct
        deadzoneCommitted = false
        App.motion.setDeadzone(pendingDeadzonePct / 100.0)
    }
    onOpened: initState()
    onClosed: {
        if (!deadzoneCommitted)
            App.motion.setDeadzone(originalDeadzonePct / 100.0)
    }

    background: Rectangle { color: theme.colorSurface; radius: 10; border.color: theme.colorBorder; border.width: 1 }
    padding: 20

    contentItem: StackLayout {
        currentIndex: joystickWizard.step

        // Step 0: Intro
        ColumnLayout {
            spacing: 14
            Text { text: "Joystick calibration"; color: theme.colorText; font.pixelSize: 15; font.weight: Font.Medium }
            WizardDots { total: 4; current: joystickWizard.step }
            Text {
                text: "Current center:  X " + App.motion.joystickCenterX.toFixed(0) + "  Y " + App.motion.joystickCenterY.toFixed(0) +
                      "\nCurrent deadzone: " + (App.motion.deadzone * 100).toFixed(0) + " %"
                color: theme.colorTextSub; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true
            }
            Text {
                text: "This wizard re-calibrates the joystick center and deadzone.\nYou can skip either step if no change is needed."
                color: theme.colorTextSub; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true
            }
            Item { Layout.fillHeight: true }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Rectangle {
                    implicitWidth: _jw0c.implicitWidth + 24; implicitHeight: 32; radius: 6
                    color: theme.colorSurfaceLight; border.color: theme.colorBorder; border.width: 1
                    Text { id: _jw0c; anchors.centerIn: parent; text: "Cancel"; color: theme.colorTextSub; font.pixelSize: 12 }
                    TapHandler { onTapped: joystickWizard.close() }
                }
                Rectangle {
                    implicitWidth: _jw0n.implicitWidth + 24; implicitHeight: 32; radius: 6
                    color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12)
                    Row {
                        id: _jw0n
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "Next"; color: theme.colorAccent; font.pixelSize: 12; font.weight: Font.Medium; anchors.verticalCenter: parent.verticalCenter }
                        Icon { code: "\uf054"; iconSize: 10; color: theme.colorAccent; anchors.verticalCenter: parent.verticalCenter }
                    }
                    TapHandler { onTapped: joystickWizard.step = 1 }
                }
            }
        }

        // Step 1: Center calibration
        ColumnLayout {
            spacing: 14
            Text { text: "Center position"; color: theme.colorText; font.pixelSize: 15; font.weight: Font.Medium }
            WizardDots { total: 4; current: joystickWizard.step }
            Text {
                text: "Release the joystick so it rests at center, then press Calibrate.\nThe microscope samples 30 readings to find the neutral position."
                color: theme.colorTextSub; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true
            }
            Connections {
                target: App.motion
                function onJoystickCalDone() { joystickWizard.step = 2 }
            }
            Item { Layout.fillHeight: true }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Rectangle {
                    implicitWidth: _jw1sk.implicitWidth + 24; implicitHeight: 32; radius: 6
                    color: theme.colorSurfaceLight; border.color: theme.colorBorder; border.width: 1
                    Text { id: _jw1sk; anchors.centerIn: parent; text: "Skip"; color: theme.colorTextSub; font.pixelSize: 12 }
                    TapHandler { onTapped: joystickWizard.step = 2 }
                }
                Rectangle {
                    implicitWidth: _jw1n.implicitWidth + 24; implicitHeight: 32; radius: 6
                    color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12)
                    Text { id: _jw1n; anchors.centerIn: parent; text: "Calibrate"; color: theme.colorAccent; font.pixelSize: 12; font.weight: Font.Medium }
                    TapHandler { onTapped: App.motion.startJoystickCal() }
                }
            }
        }

        // Step 2: Deadzone
        ColumnLayout {
            spacing: 10
            Text { text: "Deadzone"; color: theme.colorText; font.pixelSize: 15; font.weight: Font.Medium }
            WizardDots { total: 4; current: joystickWizard.step }

            // Joystick visualizer
            Item {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: 160; Layout.preferredHeight: 160
                clip: true

                // Outer circle (full range)
                Rectangle {
                    anchors.fill: parent; radius: width / 2
                    color: theme.colorSurfaceLight; border.color: theme.colorBorder; border.width: 1
                }
                // Crosshairs
                Rectangle { width: 1; height: parent.height; anchors.centerIn: parent; color: theme.colorBorder; opacity: 0.4 }
                Rectangle { width: parent.width; height: 1; anchors.centerIn: parent; color: theme.colorBorder; opacity: 0.4 }
                // Deadzone ring (updates live as slider moves)
                Rectangle {
                    property real r: Math.max(0, Math.min(1, joystickWizard.pendingDeadzonePct / 100.0)) * (parent.width / 2 - 2)
                    width: r * 2; height: r * 2; radius: r
                    anchors.centerIn: parent
                    color: "transparent"
                    border.color: theme.colorAccent; border.width: 1.5
                    opacity: 0.7
                }
                // Joystick position dot
                Rectangle {
                    property real nx: App.motion.joystickNormX
                    property real ny: App.motion.joystickNormY
                    property real maxOffset: parent.width / 2 - width / 2 - 2
                    width: 6; height: 6; radius: 3
                    color: theme.colorAccent
                    x: parent.width / 2 - width / 2 + Math.max(-1, Math.min(1, nx)) * maxOffset
                    y: parent.height / 2 - height / 2 + Math.max(-1, Math.min(1, ny)) * maxOffset
                }
            }
            Text {
                text: "Live: X " + App.motion.joystickNormX.toFixed(2) + "  Y " + App.motion.joystickNormY.toFixed(2)
                color: theme.colorTextSub; font.pixelSize: 11
                Layout.alignment: Qt.AlignHCenter
            }

            // Slider row
            RowLayout {
                Layout.fillWidth: true; spacing: 8
                Text { text: "1 %"; color: theme.colorTextSub; font.pixelSize: 11 }
                SSlider {
                    value: joystickWizard.pendingDeadzonePct; from: 1; to: 50; stepSize: 1
                    onValueEdited: function(v) {
                        joystickWizard.pendingDeadzonePct = v
                        App.motion.setDeadzone(v / 100.0)
                    }
                }
                Text { text: "50 %"; color: theme.colorTextSub; font.pixelSize: 11 }
            }
            Text {
                text: "Deadzone: " + joystickWizard.pendingDeadzonePct + " %"
                color: theme.colorTextSub; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.WordWrap
            }

            Item { Layout.fillHeight: true }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Rectangle {
                    implicitWidth: _jw2sk.implicitWidth + 24; implicitHeight: 32; radius: 6
                    color: theme.colorSurfaceLight; border.color: theme.colorBorder; border.width: 1
                    Text { id: _jw2sk; anchors.centerIn: parent; text: "Skip"; color: theme.colorTextSub; font.pixelSize: 12 }
                    TapHandler {
                        onTapped: {
                            joystickWizard.pendingDeadzonePct = joystickWizard.originalDeadzonePct
                            App.motion.setDeadzone(joystickWizard.originalDeadzonePct / 100.0)
                            joystickWizard.step = 3
                        }
                    }
                }
                Rectangle {
                    implicitWidth: _jw2n.implicitWidth + 24; implicitHeight: 32; radius: 6
                    color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12)
                    Row {
                        id: _jw2n
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "Apply"; color: theme.colorAccent; font.pixelSize: 12; font.weight: Font.Medium; anchors.verticalCenter: parent.verticalCenter }
                        Icon { code: "\uf054"; iconSize: 10; color: theme.colorAccent; anchors.verticalCenter: parent.verticalCenter }
                    }
                    TapHandler {
                        onTapped: {
                            joystickWizard.deadzoneCommitted = true
                            App.settings.setJoystickDeadzonePct(joystickWizard.pendingDeadzonePct)
                            joystickWizard.step = 3
                        }
                    }
                }
            }
        }

        // Step 3: Done
        ColumnLayout {
            spacing: 14
            Text { text: "Calibration complete"; color: theme.colorText; font.pixelSize: 15; font.weight: Font.Medium }
            WizardDots { total: 4; current: joystickWizard.step }
            Text {
                text: "Center:  X " + App.motion.joystickCenterX.toFixed(0) + "  Y " + App.motion.joystickCenterY.toFixed(0) +
                      "\nDeadzone: " + App.settings.joystickDeadzonePct + " %"
                color: theme.colorTextSub; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true
            }
            Text {
                text: "Move the joystick to confirm it responds correctly."
                color: theme.colorTextSub; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true
            }
            Item { Layout.fillHeight: true }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Rectangle {
                    implicitWidth: _jw3d.implicitWidth + 24; implicitHeight: 32; radius: 6
                    color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12)
                    Text { id: _jw3d; anchors.centerIn: parent; text: "Done"; color: theme.colorAccent; font.pixelSize: 12; font.weight: Font.Medium }
                    TapHandler { onTapped: joystickWizard.close() }
                }
            }
        }
    }
}
