import QtQuick

Text {
    property string code: ""
    property real   iconSize: 16

    FontLoader {
        id: faSolid
        source: "../fonts/Font Awesome 7 Free-Solid-900.otf"
    }

    text:                  code
    font.family:           faSolid.name !== "" ? faSolid.name : "Font Awesome 7 Free"
    font.styleName:        "Solid"
    font.pixelSize:        iconSize
    horizontalAlignment:   Text.AlignHCenter
    verticalAlignment:     Text.AlignVCenter
    renderType:            Text.NativeRendering
}
