import QtQuick
import Qt5Compat.GraphicalEffects

pragma ComponentBehavior: Bound

Item {
    id: root

    property alias source: preview.source
    property alias fillMode: preview.fillMode
    property bool imageVisible: true
    property int radius: 6
    property color backgroundColor: "black"
    property color borderColor: "transparent"
    property int borderWidth: 1
    property bool asynchronous: true
    property bool cache: false
    property int sourceMaxSize: 0
    default property alias content: overlayLayer.data

    Rectangle {
        anchors.fill: parent
        radius: root.radius
        color: root.backgroundColor
        border.color: root.borderColor
        border.width: root.borderWidth
    }

    Item {
        id: maskedContent
        anchors.fill: parent
        anchors.margins: root.borderWidth
        layer.enabled: true
        layer.effect: OpacityMask {
            maskSource: Rectangle {
                width: maskedContent.width
                height: maskedContent.height
                radius: Math.max(0, root.radius - root.borderWidth)
            }
        }

        Image {
            id: preview
            anchors.fill: parent
            fillMode: Image.PreserveAspectCrop
            visible: root.imageVisible
            asynchronous: root.asynchronous
            cache: root.cache
            sourceSize.width: root.sourceMaxSize
            sourceSize.height: root.sourceMaxSize
        }

        Item {
            id: overlayLayer
            anchors.fill: parent
        }
    }
}
