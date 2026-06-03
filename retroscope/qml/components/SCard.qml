import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property string title: ""
    default property alias content: contentColumn.data

    Layout.fillWidth: true
    Layout.alignment: Qt.AlignTop
    implicitHeight: contentColumn.implicitHeight + (root.title !== "" ? 42 : 24)
    color: theme.colorSurface
    radius: 8
    border.color: theme.colorBorder
    border.width: 1

    Theme {
        id: theme
    }

    Text {
        visible: root.title !== ""
        text: root.title
        color: theme.colorTextSub
        font.pixelSize: 10
        font.weight: Font.Medium
        font.letterSpacing: 0.7
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.topMargin: 10
        anchors.leftMargin: 12
    }

    ColumnLayout {
        id: contentColumn

        anchors.fill: parent
        anchors.margins: 12
        anchors.topMargin: root.title !== "" ? 30 : 12
        spacing: 6
    }
}
