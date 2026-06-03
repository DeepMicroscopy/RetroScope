import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property string label: ""
    property color btnColor: theme.colorTextSub
    property color btnBg: theme.colorSurfaceLight
    property color borderColor: "transparent"
    property int borderWidth: 0
    property bool fillWidth: true
    property int controlHeight: 28

    signal tapped()

    Layout.fillWidth: fillWidth
    implicitWidth: labelText.implicitWidth + 24
    height: controlHeight
    radius: 6
    color: btnBg
    border.color: borderColor
    border.width: borderWidth

    Theme {
        id: theme
    }

    Text {
        id: labelText
        anchors.centerIn: parent
        text: root.label
        color: root.btnColor
        font.pixelSize: 11
    }

    TapHandler {
        onTapped: root.tapped()
    }
}
