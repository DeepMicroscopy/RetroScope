pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import RetroScope 1.0

Rectangle {
    id: root

    property string value: ""
    property bool mono: false

    signal committed(string text)

    Layout.fillWidth: true
    height: 28
    radius: 4
    color: theme.colorSurfaceLight
    border.color: input.activeFocus ? theme.colorAccent : theme.colorBorder
    border.width: 1

    Theme {
        id: theme
    }

    TextInput {
        id: input

        anchors.fill: parent
        anchors.margins: 8
        text: root.value
        color: theme.colorText
        font.pixelSize: 11
        font.family: root.mono ? "Courier New" : font.family
        selectByMouse: true
        clip: true
        onActiveFocusChanged: {
            if (activeFocus)
                Qt.callLater(function() { App.system.showInputPanel() })
        }
        onEditingFinished: root.committed(text)
    }
}
