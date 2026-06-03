import QtQuick
import QtQuick.Layouts

RowLayout {
    id: root

    property bool checked: false
    property string label: ""

    Layout.fillWidth: true
    opacity: enabled ? 1.0 : 0.45

    Theme {
        id: theme
    }

    Text {
        text: root.label
        color: theme.colorTextSub
        font.pixelSize: 11
        Layout.fillWidth: true
    }

    Rectangle {
        implicitWidth: 32
        implicitHeight: 18
        radius: 9
        color: root.checked ? theme.colorAccent : theme.colorSurfaceLight
        border.color: root.checked ? theme.colorAccent : theme.colorBorder

        Rectangle {
            width: 14
            height: 14
            radius: 7
            color: root.checked ? "#ffffff" : "#888888"
            x: root.checked ? parent.width - width - 2 : 2
            anchors.verticalCenter: parent.verticalCenter

            Behavior on x {
                NumberAnimation { duration: 150 }
            }
        }

        TapHandler {
            enabled: root.enabled
            onTapped: root.checked = !root.checked
        }
    }
}
