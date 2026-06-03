import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property string label: ""

    signal tapped()

    Layout.fillWidth: true
    Layout.preferredHeight: 34
    radius: 6
    color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.10)
    border.color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.22)
    border.width: 1

    Theme {
        id: theme
    }

    Text {
        anchors.centerIn: parent
        text: root.label
        color: theme.colorAccent
        font.pixelSize: 12
        font.weight: Font.Medium
        font.family: "Courier New"
    }

    MouseArea {
        anchors.fill: parent
        onClicked: root.tapped()
    }
}
