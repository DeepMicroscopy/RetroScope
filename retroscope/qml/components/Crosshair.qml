import QtQuick

Canvas {
    id: root
    property color lineColor:    "#592178"
    property real  lineWidth:    1
    property real  armLength:    40   // px each "arm" extends from center
    property real  circleRadius: 3    // radius of center circle (outline only)
    property real  gapSize:      3    // gap between arm tip and circle edge

    onLineColorChanged:    requestPaint()
    onLineWidthChanged:    requestPaint()
    onArmLengthChanged:    requestPaint()
    onCircleRadiusChanged: requestPaint()
    onGapSizeChanged:      requestPaint()
    onWidthChanged:        requestPaint()
    onHeightChanged:       requestPaint()

    onPaint: {
        var ctx = getContext("2d")
        ctx.clearRect(0, 0, width, height)
        ctx.strokeStyle = lineColor
        ctx.lineWidth   = lineWidth
        ctx.globalAlpha = 0.85

        var cx    = width  / 2
        var cy    = height / 2
        var inner = circleRadius + gapSize              // "arm" end (near circle)
        var outer = circleRadius + gapSize + armLength  // "arm" start (far end)

        // Left "arm"
        ctx.beginPath()
        ctx.moveTo(cx - outer, cy)
        ctx.lineTo(cx - inner, cy)
        ctx.stroke()

        // Right "arm"
        ctx.beginPath()
        ctx.moveTo(cx + inner, cy)
        ctx.lineTo(cx + outer, cy)
        ctx.stroke()

        // Top "arm"
        ctx.beginPath()
        ctx.moveTo(cx, cy - outer)
        ctx.lineTo(cx, cy - inner)
        ctx.stroke()

        // Bottom "arm"
        ctx.beginPath()
        ctx.moveTo(cx, cy + inner)
        ctx.lineTo(cx, cy + outer)
        ctx.stroke()

        // Center circle: Outline only, no fill
        ctx.beginPath()
        ctx.arc(cx, cy, circleRadius, 0, Math.PI * 2)
        ctx.stroke()
    }
}
