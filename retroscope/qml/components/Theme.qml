pragma ComponentBehavior: Bound
import QtQuick
import RetroScope 1.0

QtObject {
    readonly property bool dark: App.overlay.darkTheme

    readonly property color colorBg:          dark ? "#1a1a1a" : "#f5f5f5"
    readonly property color colorSurface:     dark ? "#242424" : "#ffffff"
    readonly property color colorSurfaceLight:    dark ? "#2e2e2e" : "#ebebeb"
    readonly property color colorBorder:      dark ? "#3a3a3a" : "#d0d0d0"
    readonly property color colorText:        dark ? "#f0f0f0" : "#1a1a1a"
    readonly property color colorTextSub:     dark ? "#a0a0a0" : "#555555"
    readonly property color colorAccent:      dark ? "#A970E8" : "#592178"
    readonly property color colorAccentLight: dark ? "#C7A4FF" : "#7a3aaa"
    readonly property color colorAccentFill:  dark ? "#7A3AAA" : "#592178"
    readonly property color colorDanger:        "#E24B4A"
    readonly property color colorWarning:       "#EF9F27"
    readonly property color colorSuccess:       "#33aa55"
    readonly property color colorMeasureGreen:  "#5DCAA5"
    readonly property color colorMeasureBlue:   "#85B7EB"

    readonly property color bgSelected: Qt.rgba(colorAccent.r, colorAccent.g, colorAccent.b, 0.12)
    readonly property color bgSecondary: dark ? Qt.rgba(255, 255, 255, 0.03) : Qt.rgba(0, 0, 0, 0.03)
    readonly property color floatingButtonBg: dark ? Qt.rgba(colorSurface.r, colorSurface.g, colorSurface.b, 0.88) : Qt.rgba(1, 1, 1, 0.8)
    readonly property color floatingButtonBorder: dark ? Qt.rgba(1, 1, 1, 0.16) : Qt.rgba(0, 0, 0, 0.1)
}
