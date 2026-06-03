import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property string label: ""
    property bool active: false

    signal tapped()

    Layout.fillWidth: true
    height: 26
    radius: 5
    color: active ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12) : theme.bgSecondary
    border.color: active ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.3) : "transparent"
    border.width: 1

    Theme {
        id: theme
    }

    Text {
        text: root.label
        color: root.active ? theme.colorAccent : theme.colorTextSub
        font.pixelSize: 10
        font.weight: root.active ? Font.Medium : Font.Normal
        anchors.centerIn: parent
    }

    TapHandler {
        onTapped: root.tapped()
    }
}
