import QtQuick
import QtQuick.Layouts

RowLayout {
    id: root

    property int value: 1
    property int minVal: 1
    property int maxVal: 200
    property int step: 1
    property string unit: ""
    property bool readOnly: false

    spacing: 4

    Theme {
        id: theme
    }

    Rectangle {
        implicitWidth: 22
        implicitHeight: 22
        radius: 5
        color: theme.colorSurfaceLight
        border.color: theme.colorBorder
        opacity: root.readOnly ? 0.45 : 1.0

        Text {
            text: "-"
            anchors.centerIn: parent
            color: theme.colorTextSub
            font.pixelSize: 13
        }

        MouseArea {
            anchors.fill: parent
            enabled: !root.readOnly
            onClicked: if (root.value > root.minVal) root.value -= root.step
        }
    }

    Text {
        text: root.value + (root.unit !== "" ? " " + root.unit : "")
        color: theme.colorText
        font.pixelSize: 11
        font.family: "Courier New"
        Layout.minimumWidth: 42
        horizontalAlignment: Text.AlignHCenter
    }

    Rectangle {
        implicitWidth: 22
        implicitHeight: 22
        radius: 5
        color: theme.colorSurfaceLight
        border.color: theme.colorBorder
        opacity: root.readOnly ? 0.45 : 1.0

        Text {
            text: "+"
            anchors.centerIn: parent
            color: theme.colorTextSub
            font.pixelSize: 13
        }

        MouseArea {
            anchors.fill: parent
            enabled: !root.readOnly
            onClicked: if (root.value < root.maxVal) root.value += root.step
        }
    }
}
