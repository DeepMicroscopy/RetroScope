import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    property real value: 50
    property real from: 0
    property real to: 100
    property real stepSize: 1
    property real _lastEditedValue: value

    signal valueEdited(real value)

    Layout.fillWidth: true
    implicitHeight: 20

    function commitValue(v) {
        if (Math.abs(_lastEditedValue - v) <= 0.001)
            return
        _lastEditedValue = v
        valueEdited(v)
    }

    onValueChanged: {
        _lastEditedValue = value
        if (Math.abs(slider.value - value) > 0.001)
            slider.value = value
    }

    Theme {
        id: theme
    }

    Slider {
        id: slider

        anchors.fill: parent
        from: root.from
        to: root.to
        stepSize: root.stepSize
        onMoved: root.commitValue(slider.value)
        onPressedChanged: if (!pressed) root.commitValue(slider.value)
        Component.onCompleted: {
            slider.value = root.value
            root._lastEditedValue = root.value
        }

        background: Rectangle {
            x: 7
            y: slider.height / 2 - 2
            width: slider.width - 14
            height: 4
            radius: 2
            color: theme.colorSurfaceLight

            Rectangle {
                width: slider.visualPosition * parent.width
                height: 4
                radius: 2
                color: slider.enabled ? theme.colorAccent : theme.colorTextSub
            }
        }

        handle: Rectangle {
            x: slider.visualPosition * (slider.width - 14)
            y: (slider.height - 14) / 2
            width: 14
            height: 14
            radius: 7
            color: slider.enabled ? theme.colorAccent : theme.colorTextSub
        }
    }
}
