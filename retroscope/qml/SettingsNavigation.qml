pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "components"

// Navigation sidebar for settings dialog
Rectangle {
    id: root

    property int currentPage: 0

    signal pageSelected(int page)

    Layout.preferredWidth: 176
    Layout.fillHeight: true
    color: theme.colorSurfaceLight

    Theme {
        id: theme
    }

    Rectangle {
        width: 1
        height: parent.height
        anchors.right: parent.right
        color: theme.colorBorder
    }

    Component {
        id: navItem

        Rectangle {
            id: navItemRoot

            required property var modelData

            Layout.fillWidth: true
            height: 30

            property bool active: root.currentPage === navItemRoot.modelData.page

            color: active
                   ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.08)
                   : (hover.hovered ? Qt.rgba(0, 0, 0, theme.dark ? 0.0 : 0.03) : "transparent")

            Rectangle {
                width: 2
                height: parent.height
                color: parent.active ? theme.colorAccent : "transparent"
            }

            Row {
                anchors.left: parent.left
                anchors.leftMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                spacing: 7

                Icon {
                    code: navItemRoot.modelData.faCode
                    iconSize: 12
                    width: 14
                    color: navItemRoot.active ? theme.colorAccent : theme.colorTextSub
                    anchors.verticalCenter: parent.verticalCenter
                }

                Text {
                    text: navItemRoot.modelData.label
                    font.pixelSize: 12
                    color: navItemRoot.active ? theme.colorAccent : theme.colorTextSub
                    font.weight: navItemRoot.active ? Font.Medium : Font.Normal
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            HoverHandler {
                id: hover
            }

            TapHandler {
                onTapped: root.pageSelected(navItemRoot.modelData.page)
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Item { Layout.preferredHeight: 6 }

        // Navigation items for settings pages
        Repeater {
            model: [
                { label: "Objectives", page: 0, faCode: "\uf610" },
                { label: "Joystick", page: 1, faCode: "\uf276" },
                { label: "Motors", page: 2, faCode: "\ue0b7" },
                { label: "GPIO Buttons", page: 3, faCode: "\uf58d" },
                { label: "Camera", page: 4, faCode: "\uf030" },
                { label: "Storage", page: 5, faCode: "\uf0a0" }
            ]

            delegate: navItem
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: theme.colorBorder
            Layout.topMargin: 4
            Layout.bottomMargin: 4
            Layout.leftMargin: 8
            Layout.rightMargin: 8
        }

        Repeater {
            model: [
                { label: "System", page: 6, faCode: "\uf013" }
            ]

            delegate: navItem
        }

        Item { Layout.fillHeight: true }

        Repeater {
            model: [
                { label: "About", page: 7, faCode: "\uf05a" }
            ]

            delegate: navItem
        }

        Item { Layout.preferredHeight: 6 }
    }
}
