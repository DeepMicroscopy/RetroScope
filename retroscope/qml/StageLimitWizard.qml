pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "components"
import RetroScope 1.0

// Stage limit calibration wizard
Dialog {
    id: stageLimitWizard

    Theme {
        id: theme
    }
    modal: true
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: 520
    visible: App.motion.stageLimitWizardActive
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    onClosed: App.motion.closeStageLimitWizard()

    function dismissWizard() {
        App.motion.closeStageLimitWizard()
        stageLimitWizard.close()
    }

    background: Rectangle { color: theme.colorSurface; radius: 10; border.color: theme.colorBorder; border.width: 1 }
    padding: 20

    contentItem: StackLayout {
        currentIndex: App.motion.stageLimitWizardStep

        ColumnLayout {
            spacing: 14
            Text { text: "Stage limits"; color: theme.colorText; font.pixelSize: 15; font.weight: Font.Medium }
            WizardDots { total: 4; current: App.motion.stageLimitWizardStep }
            SRow { label: "Z endstop"; value: App.status.endstopTriggered ? "Triggered" : "Clear"; mono: true }
            Text {
                text: "Move Z until the endstop is triggered. The home position can only be set from that state."
                color: theme.colorTextSub; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true
            }
            Item { Layout.fillHeight: true }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Item { Layout.fillWidth: true }
                Rectangle {
                    Layout.preferredWidth: _stageCancel0.implicitWidth + 24; Layout.preferredHeight: 28; radius: 6; color: theme.colorSurfaceLight
                    Text { id: _stageCancel0; anchors.centerIn: parent; text: "Cancel"; color: theme.colorTextSub; font.pixelSize: 11 }
                    MouseArea { anchors.fill: parent; preventStealing: true; onClicked: stageLimitWizard.dismissWizard() }
                }
                SBtn {
                    label: "Next"
                    fillWidth: false
                    enabled: App.status.endstopTriggered
                    opacity: enabled ? 1.0 : 0.45
                    btnColor: enabled ? theme.colorAccent : theme.colorTextSub
                    btnBg: enabled ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12) : theme.colorSurfaceLight
                    onTapped: if (enabled) App.motion.setStageLimitWizardStep(1)
                }
            }
        }

        ColumnLayout {
            spacing: 14
            Text { text: "Top-left home"; color: theme.colorText; font.pixelSize: 15; font.weight: Font.Medium }
            WizardDots { total: 4; current: App.motion.stageLimitWizardStep }
            SRow { label: "Current"; value: "X " + App.motion.posX + "  Y " + App.motion.posY + "  Z " + App.motion.posZ; mono: true }
            SRow { label: "Z endstop"; value: App.status.endstopTriggered ? "Triggered" : "Clear"; mono: true }
            Text {
                text: "Move XY to the physical top-left corner, then set firmware home to 0,0,0. Saved bookmarks keep their old coordinates."
                color: theme.colorTextSub; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true
            }
            Item { Layout.fillHeight: true }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Item { Layout.fillWidth: true }
                Rectangle {
                    Layout.preferredWidth: _stageCancel1.implicitWidth + 24; Layout.preferredHeight: 28; radius: 6; color: theme.colorSurfaceLight
                    Text { id: _stageCancel1; anchors.centerIn: parent; text: "Cancel"; color: theme.colorTextSub; font.pixelSize: 11 }
                    MouseArea { anchors.fill: parent; preventStealing: true; onClicked: stageLimitWizard.dismissWizard() }
                }
                SBtn { label: "Back"; fillWidth: false; onTapped: App.motion.setStageLimitWizardStep(0) }
                SBtn {
                    label: "Set home"
                    fillWidth: false
                    btnColor: theme.colorAccent
                    btnBg: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12)
                    onTapped: App.motion.confirmHomeZero()
                }
            }
        }

        ColumnLayout {
            spacing: 14
            Text { text: "Bottom-right limit"; color: theme.colorText; font.pixelSize: 15; font.weight: Font.Medium }
            WizardDots { total: 4; current: App.motion.stageLimitWizardStep }
            SRow { label: "Current"; value: "X " + App.motion.posX + "  Y " + App.motion.posY + "  Z " + App.motion.posZ; mono: true }
            Text {
                text: "Move XY to the physical bottom-right corner, then save the current XY position as the opposite limit."
                color: theme.colorTextSub; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true
            }
            Item { Layout.fillHeight: true }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Item { Layout.fillWidth: true }
                Rectangle {
                    Layout.preferredWidth: _stageCancel2.implicitWidth + 24; Layout.preferredHeight: 28; radius: 6; color: theme.colorSurfaceLight
                    Text { id: _stageCancel2; anchors.centerIn: parent; text: "Cancel"; color: theme.colorTextSub; font.pixelSize: 11 }
                    MouseArea { anchors.fill: parent; preventStealing: true; onClicked: stageLimitWizard.dismissWizard() }
                }
                SBtn { label: "Back"; fillWidth: false; onTapped: App.motion.setStageLimitWizardStep(1) }
                SBtn {
                    label: "Save limit"
                    fillWidth: false
                    btnColor: theme.colorAccent
                    btnBg: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12)
                    onTapped: App.motion.saveBottomRightLimit()
                }
            }
        }

        ColumnLayout {
            spacing: 14
            Text { text: "Limits saved"; color: theme.colorText; font.pixelSize: 15; font.weight: Font.Medium }
            WizardDots { total: 4; current: App.motion.stageLimitWizardStep }
            SRow { label: "X range"; value: App.motion.softLimitXMin + " to " + App.motion.softLimitXMax; mono: true }
            SRow { label: "Y range"; value: App.motion.softLimitYMin + " to " + App.motion.softLimitYMax; mono: true }
            SRow { label: "Soft limits"; value: App.motion.softLimitsEnabled ? "Enabled" : "Disabled" }
            Text {
                text: "The stage will now block manual and automated XY moves outside this rectangle."
                color: theme.colorTextSub; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true
            }
            Item { Layout.fillHeight: true }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Item { Layout.fillWidth: true }
                SBtn {
                    label: "Done"
                    fillWidth: false
                    btnColor: theme.colorAccent
                    btnBg: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12)
                    onTapped: stageLimitWizard.dismissWizard()
                }
            }
        }
    }
}
