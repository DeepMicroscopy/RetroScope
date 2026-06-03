import QtQuick

Rectangle {
    id: root

    property bool checked: false

    signal toggled(bool value)

    width: 32
    height: 18
    radius: 9
    color: checked ? theme.colorAccent : theme.colorBorder

    Theme {
        id: theme
    }

    Rectangle {
        width: 14
        height: 14
        radius: 7
        color: root.checked ? "#ffffff" : theme.colorSurface
        anchors.verticalCenter: parent.verticalCenter
        x: root.checked ? parent.width - width - 2 : 2

        Behavior on x {
            NumberAnimation { duration: 150 }
        }
    }

    TapHandler {
        onTapped: {
            root.checked = !root.checked
            root.toggled(root.checked)
        }
    }
}
