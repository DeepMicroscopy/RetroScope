import QtQuick
import QtQuick.Controls
import "."

Rectangle {
    id: root
    width: label.implicitWidth + 24
    height: 30
    radius: 15
    color: theme.colorAccentFill
    opacity: 0

    Theme {
        id: theme
    }

    function show() {
        anim.restart()
    }

    Label {
        id: label
        anchors.centerIn: parent
        text: "QML Reloaded"
        color: "white"
        font.pixelSize: 12
        font.weight: Font.Medium
    }

    SequentialAnimation {
        id: anim
        NumberAnimation { target: root; property: "opacity"; to: 0.9; duration: 150 }
        PauseAnimation { duration: 2000 }
        NumberAnimation { target: root; property: "opacity"; to: 0; duration: 400 }
    }
}
