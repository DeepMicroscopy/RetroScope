import QtQuick
import QtQuick.Controls

Flickable {
    id: root

    clip: true
    interactive: true
    acceptedButtons: Qt.LeftButton
    boundsBehavior: Flickable.StopAtBounds
    flickableDirection: Flickable.VerticalFlick

    readonly property real availableWidth: Math.max(0, width)
    readonly property real availableHeight: height

    function contentExtent() {
        var extent = 0
        var children = root.contentItem.children
        for (var i = 0; i < children.length; ++i) {
            var child = children[i]
            if (!child || child === verticalBar || child === horizontalBar)
                continue
            var childHeight = child.implicitHeight > 0 ? child.implicitHeight : child.height
            extent = Math.max(extent, child.y + childHeight)
        }
        return extent
    }

    contentWidth: availableWidth
    contentHeight: Math.max(height, contentExtent())

    ScrollBar.vertical: ScrollBar {
        id: verticalBar
        policy: ScrollBar.AsNeeded
        interactive: true
    }

    ScrollBar.horizontal: ScrollBar {
        id: horizontalBar
        policy: ScrollBar.AlwaysOff
        interactive: false
    }
}
