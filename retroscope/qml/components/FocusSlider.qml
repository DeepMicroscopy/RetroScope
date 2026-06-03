pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "."
import RetroScope 1.0

Item {
    id: root
    property int zPos: 0

    Theme {
        id: theme
    }
    
    readonly property color bgTrack: theme.dark ? "#252528" : "#e0e0e0"
    readonly property color bgButton: theme.dark ? Qt.rgba(1, 1, 1, 0.05) : Qt.rgba(0, 0, 0, 0.05)
    
    // Z runs 0 (endstop / minimal focus, bottom) -> _range (top).
    readonly property int _range: 100000
    // Prevent division by zero and limit ratio to [0,1]
    property real zRatio: Math.max(0, Math.min(1, zPos / _range))

    RowLayout {
        anchors.fill: parent
        spacing: 12

        // Left side: Z vertical indicator
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            Rectangle {
                anchors.fill: parent
                color: root.bgTrack
                radius: 6
                clip: true

                // Gradient fill underneath indicator line
                Rectangle {
                    anchors.bottom: parent.bottom
                    anchors.left: parent.left
                    anchors.right: parent.right
                    height: parent.height * root.zRatio
                    topLeftRadius: 0
                    topRightRadius: 0
                    bottomLeftRadius: parent.radius
                    bottomRightRadius: parent.radius

                    gradient: Gradient {
                        GradientStop { position: 0.0; color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.08) }
                        GradientStop { position: 1.0; color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.02) }
                    }
                }

                // Focus line
                Rectangle {
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: parent.height * root.zRatio
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.leftMargin: parent.radius
                    anchors.rightMargin: parent.radius
                    height: 2
                    radius: 1
                    color: theme.colorAccent
                    opacity: 0.6
                }

                // Triangle pointer
                Rectangle {
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: parent.height * root.zRatio - 1
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 14
                    height: 4
                    radius: 2
                    color: theme.colorAccent
                }
            }

            // Labels for top/bottom
            Text {
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.margins: 6
                text: "100000"
                color: theme.colorTextSub
                font.pixelSize: 9
            }
            Text {
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.margins: 6
                text: "0"
                color: theme.colorTextSub
                font.pixelSize: 9
            }
        }

        // Right side: Controls
        Column {
            Layout.alignment: Qt.AlignVCenter
            spacing: 4

            Rectangle {
                width: 36; height: 28; radius: 6
                color: root.bgButton
                Icon { anchors.centerIn: parent; code: "\uf077"; iconSize: 12; color: theme.colorAccent }
                TapHandler { onTapped: App.motion.moveZ_rel(500) }
            }
            Rectangle {
                width: 36; height: 28; radius: 6
                color: root.bgButton
                Icon { anchors.centerIn: parent; code: "\uf078"; iconSize: 12; color: theme.colorAccent }
                TapHandler { onTapped: App.motion.moveZ_rel(-500) }
            }
            Rectangle {
                width: 36; height: 28; radius: 6
                color: App.autofocus.busy
                       ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.3)
                       : Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.1)
                Text {
                    anchors.centerIn: parent
                    text: App.autofocus.busy
                          ? Math.round(App.autofocus.progress * 100) + "%"
                          : "AF"
                    color: theme.colorAccent
                    font.pixelSize: 10
                    font.weight: Font.Medium
                }
                TapHandler {
                    onTapped: App.autofocus.toggleAutofocus()
                }
            }
        }
    }
}
