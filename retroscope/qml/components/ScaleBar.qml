import QtQuick

Item {
    id: root
    property real umPerPixel: 1.0

    // Compute a "rounded" scale bar length in screen pixels and µm label
    readonly property var _niceUm: [1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000]
    readonly property real _targetPx: 100

    function _computeBar() {
        if (umPerPixel <= 0) return { px: 100, label: "?" }
        var rawUm = _targetPx * umPerPixel
        var bestUm = _niceUm[_niceUm.length - 1]
        for (var i = 0; i < _niceUm.length; i++) {
            if (_niceUm[i] >= rawUm * 0.5) {
                bestUm = _niceUm[i]
                break
            }
        }
        var px = bestUm / umPerPixel
        var label = bestUm >= 1000 ? (bestUm / 1000).toFixed(0) + " mm"
                                   : bestUm.toFixed(0) + " µm"
        return { px: px, label: label }
    }

    readonly property var _bar: _computeBar()

    implicitWidth:  _bar.px + barLabel.implicitWidth + 10
    implicitHeight: 8

    // Bar line
    Rectangle {
        id: barRect
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        width: root._bar.px
        height: 3
        color: "white"
        border.color: "#00000066"
    }

    // Left cap
    Rectangle {
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        width: 2; height: 8
        color: "white"
    }

    // Right cap
    Rectangle {
        anchors.left: parent.left
        anchors.leftMargin: root._bar.px - 2
        anchors.verticalCenter: parent.verticalCenter
        width: 2; height: 8
        color: "white"
    }

    // Label, to the right of the bar
    Text {
        id: barLabel
        anchors.left: barRect.right
        anchors.leftMargin: 6
        anchors.verticalCenter: barRect.verticalCenter
        text: root._bar.label
        color: "white"
        font.pixelSize: 11
        style: Text.Outline
        styleColor: "#00000088"
    }
}
