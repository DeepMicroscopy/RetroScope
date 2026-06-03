import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property string label: ""
    property color textColor: theme.colorAccent
    property color bgColor: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.1)
    property color borderColor: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.22)

    signal tapped()

    Layout.fillWidth: true
    height: 28
    radius: 6
    color: bgColor
    border.color: borderColor
    border.width: 1

    Theme {
        id: theme
    }

    Text {
        anchors.centerIn: parent
        text: root.label
        color: root.textColor
        font.pixelSize: 11
        font.weight: Font.Medium
    }

    TapHandler {
        onTapped: root.tapped()
    }
}
