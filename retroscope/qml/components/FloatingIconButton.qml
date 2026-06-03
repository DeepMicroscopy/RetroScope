import QtQuick
import QtQuick.Controls

Rectangle {
    id: root

    property string iconCode: "\uf548"
    property string toolTip: ""
    property bool active: false

    signal tapped()

    width: 32
    height: 32
    radius: 8
    color: active ? theme.colorAccentFill : theme.floatingButtonBg
    border.color: active ? theme.colorAccentFill : theme.floatingButtonBorder
    border.width: 1

    Theme {
        id: theme
    }

    Icon {
        anchors.centerIn: parent
        code: root.iconCode
        iconSize: 14
        color: root.active ? "#ffffff" : theme.colorText
    }

    ToolTip.visible: hover.hovered && root.toolTip !== ""
    ToolTip.text: root.toolTip

    HoverHandler {
        id: hover
    }

    TapHandler {
        onTapped: root.tapped()
    }
}
