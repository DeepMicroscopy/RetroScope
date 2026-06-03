pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts

RowLayout {
    id: root

    property var  model: []
    property var  currentValue: undefined
    property bool itemFillWidth: true
    property int  itemHeight: 30
    property int  itemRadius: 6
    property int  fontSize: 12
    property string fontFamily: ""
    property int  itemHorizontalPadding: 22

    signal selected(var value)

    spacing: 4

    Theme { id: theme }

    function _label(item) {
        return (typeof item === "object" && item !== null && "label" in item) ? item.label : item
    }
    function _value(item) {
        return (typeof item === "object" && item !== null && "value" in item) ? item.value : item
    }

    Repeater {
        model: root.model
        delegate: Rectangle {
            id: cell
            required property var modelData

            readonly property var itemLabel: root._label(modelData)
            readonly property var itemValue: root._value(modelData)
            readonly property bool active: itemValue === root.currentValue

            Layout.fillWidth: root.itemFillWidth
            implicitWidth: root.itemFillWidth ? 0 : (cellLabel.implicitWidth + root.itemHorizontalPadding)
            implicitHeight: root.itemHeight
            radius: root.itemRadius
            color: active
                   ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.10)
                   : theme.colorSurfaceLight
            border.color: active
                          ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.28)
                          : "transparent"
            border.width: 1

            Text {
                id: cellLabel
                anchors.centerIn: parent
                text: cell.itemLabel
                color: cell.active ? theme.colorAccent : theme.colorTextSub
                font.pixelSize: root.fontSize
                font.weight: cell.active ? Font.Medium : Font.Normal
                font.family: root.fontFamily.length > 0 ? root.fontFamily : font.family
            }

            TapHandler {
                onTapped: root.selected(cell.itemValue)
            }
        }
    }
}
