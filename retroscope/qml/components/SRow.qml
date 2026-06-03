import QtQuick
import QtQuick.Layouts

RowLayout {
    id: root

    property string label: ""
    property string value: ""
    property bool mono: false
    property bool elideLeft: false

    Layout.fillWidth: true
    spacing: 8

    Theme {
        id: theme
    }

    Text {
        text: root.label
        color: theme.colorTextSub
        font.pixelSize: 11
        Layout.fillWidth: !root.elideLeft
        Layout.preferredWidth: root.elideLeft ? implicitWidth : -1
    }

    Text {
        text: root.value
        color: theme.colorText
        font.pixelSize: 11
        font.family: root.mono ? "Courier New" : font.family
        elide: root.elideLeft ? Text.ElideLeft : Text.ElideRight
        visible: root.value !== ""
        Layout.fillWidth: root.elideLeft
        Layout.preferredWidth: (!root.elideLeft && visible) ? implicitWidth : -1
    }
}
