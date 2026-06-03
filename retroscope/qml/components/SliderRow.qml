import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root

    property string label: ""
    property real value: 0
    property real from: 0
    property real to: 1
    property int decimals: 0
    property string unit: ""
    property bool readOnly: false
    property real stepSize: 1

    Layout.fillWidth: true
    spacing: 3

    function setValue(v) {
        root.value = v
        slider.value = v
    }

    Theme {
        id: theme
    }

    RowLayout {
        Layout.fillWidth: true

        Text {
            text: root.label
            color: theme.colorTextSub
            font.pixelSize: 11
            Layout.fillWidth: true
        }

        Text {
            text: root.value.toFixed(root.decimals) + (root.unit !== "" ? " " + root.unit : "")
            color: theme.colorTextSub
            font.pixelSize: 11
            font.family: "Courier New"
        }
    }

    SSlider {
        id: slider

        Layout.fillWidth: true
        from: root.from
        to: root.to
        value: root.value
        stepSize: root.stepSize
        enabled: !root.readOnly
        onValueEdited: function(v) { root.value = root.decimals === 0 ? Math.round(v) : v }
    }
}
