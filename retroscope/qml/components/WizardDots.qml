pragma ComponentBehavior: Bound
import QtQuick

Row {
    id: root

    property int total: 1
    property int current: 0

    spacing: 6

    Theme {
        id: theme
    }

    Repeater {
        model: root.total

        Rectangle {
            id: dot
            required property int index
            width: 7
            height: 7
            radius: 3.5
            color: dot.index <= root.current
                   ? theme.colorAccent
                   : Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.2)
        }
    }
}
