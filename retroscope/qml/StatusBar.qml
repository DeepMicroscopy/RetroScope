pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "components"
import RetroScope 1.0

// Status bar at the bottom of the app
Rectangle {
    id: root
    property int currentTab: 0
    property int automationTabIndex: 0
    property string measureSource: "live"

    signal automationTabSelected(int index)
    signal measureSourceSelected(string source)

    Theme { id: theme }

    color: theme.colorSurface

    function galleryTypeLabel(t) {
        if (t === "all") return "All"
        if (t === "snapshot") return "Captures"
        if (t === "video") return "Videos"
        if (t === "stack") return "Stacks"
        if (t === "stitch") return "Scans"
        return t
    }

    border.color: theme.colorBorder
    border.width: 1

    StackLayout {
        anchors.fill: parent
        currentIndex: root.currentTab

        // 0: Live View
        Item {
            // Left side items
            Row {
                anchors.left: parent.left
                anchors.leftMargin: 16
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10

                // Logo mark
                Image {
                    source: "icons/logo.svg"
                    width: 16; height: 16
                    sourceSize.width: 32; sourceSize.height: 32
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.verticalCenterOffset: -1
                }

                // Live text
                Text {
                    text: "Live"
                    color: theme.colorText
                    font.pixelSize: 12
                    font.weight: Font.Medium
                    anchors.verticalCenter: parent.verticalCenter
                }

                // Resolution info
                Text {
                    text: (App.cameraResolution || App.settings.cameraResolution).replace("x", " x ")
                          + " @ " + (App.cameraFps > 0 ? App.cameraFps.toFixed(0) : "-") + " fps"
                    color: theme.colorTextSub
                    font.pixelSize: 11
                    anchors.verticalCenter: parent.verticalCenter
                }

            }

            // Right side items
            Row {
                anchors.right: parent.right
                anchors.rightMargin: 16
                anchors.verticalCenter: parent.verticalCenter
                spacing: 14

                // Mock badge
                Row {
                    spacing: 8
                    anchors.verticalCenter: parent.verticalCenter
                    
                    Rectangle {
                        visible: App.isMockMode
                        width: mockLabel.implicitWidth + 10
                        height: 18
                        radius: 4
                        color: theme.colorAccentFill
                        opacity: 0.8
                        Label {
                            id: mockLabel
                            anchors.centerIn: parent
                            text: "MOCK"
                            color: "white"
                            font.pixelSize: 10
                            font.weight: Font.Bold
                        }
                    }
                }

                Row {
                    spacing: 6
                    anchors.verticalCenter: parent.verticalCenter

                    Rectangle {
                        width: 8; height: 8; radius: 4
                        anchors.verticalCenter: parent.verticalCenter
                        color: App.status.endstopTriggered ? theme.colorDanger : "transparent"
                        border.color: App.status.endstopTriggered ? theme.colorDanger : theme.colorBorder
                        border.width: 1
                        ToolTip.visible: endstopHover.hovered
                        ToolTip.text: App.status.endstopTriggered ? "Endstop triggered" : "Endstop clear"
                        HoverHandler { id: endstopHover }
                    }

                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        width: objText.implicitWidth + 20
                        height: 20
                        radius: 10
                        color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12)

                        Text {
                            id: objText
                            anchors.centerIn: parent
                            text: App.objective.activeDisplayName
                            color: theme.colorAccent
                            font.pixelSize: 11
                            font.weight: Font.Medium
                        }
                    }
                }

                // XYZ coords
                Row {
                    spacing: 12
                    anchors.verticalCenter: parent.verticalCenter

                    Row {
                        spacing: 4
                        Text { text: "X"; color: theme.colorTextSub; font.pixelSize: 11; font.family: "Courier New" }
                        Text { text: App.motion.posX; color: theme.colorText; font.pixelSize: 11; font.family: "Courier New" }
                    }

                    RowLayout {
                        Text { text: "Y"; color: theme.colorTextSub; font.pixelSize: 11; font.family: "Courier New" }
                        Text { text: App.motion.posY; color: theme.colorText; font.pixelSize: 11; font.family: "Courier New" }
                    }

                    RowLayout {
                        Text { text: "Z"; color: theme.colorTextSub; font.pixelSize: 11; font.family: "Courier New" }
                        Text { text: App.motion.posZ; color: theme.colorText; font.pixelSize: 11; font.family: "Courier New" }
                    }
                }
            }
        }

        // 1: Gallery View
        Item {
            Row {
                anchors.left: parent.left
                anchors.leftMargin: 16
                anchors.verticalCenter: parent.verticalCenter
                spacing: 8

                Image { source: "icons/logo.svg"; width: 16; height: 16; sourceSize.width: 32; sourceSize.height: 32; fillMode: Image.PreserveAspectFit; smooth: true; anchors.verticalCenter: parent.verticalCenter; anchors.verticalCenterOffset: -1 }
                Text { text: "Gallery"; color: theme.colorText; font.pixelSize: 12; font.weight: Font.Medium; anchors.verticalCenter: parent.verticalCenter }
                Rectangle { width: 1; height: 14; color: theme.colorBorder; anchors.verticalCenter: parent.verticalCenter }
                Text { text: App.gallery.captureCount + " captures"; color: theme.colorTextSub; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                Text { text: App.gallery.totalSizeLabel; color: theme.colorTextSub; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
            }

            Row {
                anchors.right: parent.right
                anchors.rightMargin: 16
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10

                Row {
                    spacing: 4
                    Repeater {
                        model: App.gallery.filterOptions
                        delegate: Rectangle {
                            required property var modelData
                            property bool active: App.gallery.filterType === modelData
                            height: 24
                            width: filterText.implicitWidth + 16
                            radius: 6
                            color: active
                                   ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12)
                                   : Qt.rgba(1, 1, 1, 0.04)
                            border.color: active
                                          ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.35)
                                          : "transparent"
                            border.width: active ? 1 : 0

                            Text {
                                id: filterText
                                anchors.centerIn: parent
                                text: root.galleryTypeLabel(parent.modelData)
                                color: parent.active ? theme.colorAccent : theme.colorTextSub
                                font.pixelSize: 11
                                font.weight: parent.active ? Font.Medium : Font.Normal
                            }
                            TapHandler { onTapped: App.gallery.setFilterType(parent.modelData) }
                        }
                    }
                }

                Row {
                    spacing: 3
                    Rectangle {
                        width: 24; height: 24; radius: 6
                        color: App.gallery.viewMode === "grid"
                               ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12)
                               : Qt.rgba(1, 1, 1, 0.04)
                        Icon {
                            anchors.centerIn: parent
                            code: "\uf00a"; iconSize: 12
                            color: App.gallery.viewMode === "grid" ? theme.colorAccent : theme.colorTextSub
                        }
                        TapHandler { onTapped: App.gallery.setViewMode("grid") }
                    }
                    Rectangle {
                        width: 24; height: 24; radius: 6
                        color: App.gallery.viewMode === "list"
                               ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12)
                               : Qt.rgba(1, 1, 1, 0.04)
                        Icon {
                            anchors.centerIn: parent
                            code: "\uf03a"; iconSize: 12
                            color: App.gallery.viewMode === "list" ? theme.colorAccent : theme.colorTextSub
                        }
                        TapHandler { onTapped: App.gallery.setViewMode("list") }
                    }
                }
            }
        }

        // 2: Automation View
        Item {
            // Left: dot + label + separator + objective
            Row {
                anchors.left: parent.left; anchors.leftMargin: 16; anchors.verticalCenter: parent.verticalCenter
                spacing: 10
                Image { source: "icons/logo.svg"; width: 16; height: 16; sourceSize.width: 32; sourceSize.height: 32; fillMode: Image.PreserveAspectFit; smooth: true; anchors.verticalCenter: parent.verticalCenter; anchors.verticalCenterOffset: -1 }
                Text { text: "Automation"; color: theme.colorText; font.pixelSize: 12; font.weight: Font.Medium; anchors.verticalCenter: parent.verticalCenter }
                Rectangle { width: 1; height: 14; color: theme.colorBorder; anchors.verticalCenter: parent.verticalCenter }
                Text { text: "Objective: " + App.objective.activeDisplayName; color: theme.colorTextSub; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
            }

            // Right: Focus stack / Tile scan pill tabs
            Row {
                anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter
                spacing: 3

                Repeater {
                    model: ["Focus stack", "Tile scan"]
                    delegate: Rectangle {
                        id: autoTab
                        required property string modelData
                        required property int index
                        property bool active: root.automationTabIndex === autoTab.index
                        width: autoTabLbl.implicitWidth + 24; height: 26; radius: 7
                        color: active ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.1) : "transparent"
                        border.color: active
                                          ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.35)
                                          : "transparent"
                        border.width: active ? 1 : 0
                        Text {
                            id: autoTabLbl
                            text: autoTab.modelData
                            color: autoTab.active ? theme.colorAccent : theme.colorTextSub
                            font.pixelSize: 12; font.weight: autoTab.active ? Font.Medium : Font.Normal
                            anchors.centerIn: parent
                        }
                        MouseArea {
                            anchors.fill: parent
                            onClicked: root.automationTabSelected(autoTab.index)
                        }
                    }
                }
            }
        }

        // 3: Measure View
        Item {
            id: measureStatus
            readonly property string msrc: root.measureSource

            // Left side: dot + Measure + separator + source label + ([Live] | [From gallery])
            Row {
                anchors.left: parent.left
                anchors.leftMargin: 16
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10

                Image { source: "icons/logo.svg"; width: 16; height: 16; sourceSize.width: 32; sourceSize.height: 32; fillMode: Image.PreserveAspectFit; smooth: true; anchors.verticalCenter: parent.verticalCenter; anchors.verticalCenterOffset: -1 }
                Text { text: "Measure"; color: theme.colorText; font.pixelSize: 12; font.weight: Font.Medium; anchors.verticalCenter: parent.verticalCenter }
                Rectangle { width: 1; height: 14; color: theme.colorBorder; anchors.verticalCenter: parent.verticalCenter }
                Text {
                    text: "Source:"
                    color: theme.colorTextSub; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter
                }

                Row {
                    spacing: 3
                    anchors.verticalCenter: parent.verticalCenter

                    Rectangle {
                        property bool active: measureStatus.msrc === "live"
                        width: liveLabel.implicitWidth + 20; height: 22; radius: 5
                        color: active ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.1) : Qt.rgba(1, 1, 1, 0.04)
                        border.color: active ? Qt.rgba(theme.colorAccent.r,theme.colorAccent.g,theme.colorAccent.b,0.3) : "transparent"; border.width: 1
                        Text {
                            id: liveLabel; anchors.centerIn: parent
                            text: "Live"; color: parent.active ? theme.colorAccent : theme.colorTextSub
                            font.pixelSize: 10; font.weight: parent.active ? Font.Medium : Font.Normal
                        }
                        MouseArea {
                            anchors.fill: parent
                            onClicked: root.measureSourceSelected("live")
                        }
                    }

                    Rectangle {
                        property bool active: measureStatus.msrc === "gallery"
                        width: galLabel.implicitWidth + 20; height: 22; radius: 5
                        color: active ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.1) : Qt.rgba(1, 1, 1, 0.04)
                        border.color: active ? Qt.rgba(theme.colorAccent.r,theme.colorAccent.g,theme.colorAccent.b,0.3) : "transparent"; border.width: 1
                        Text {
                            id: galLabel; anchors.centerIn: parent
                            text: "From gallery"; color: parent.active ? theme.colorAccent : theme.colorTextSub
                            font.pixelSize: 10; font.weight: parent.active ? Font.Medium : Font.Normal
                        }
                        MouseArea {
                            anchors.fill: parent
                            onClicked: root.measureSourceSelected("gallery")
                        }
                    }
                }
            }

            // Right side: Scale + separator + objective
            Row {
                anchors.right: parent.right
                anchors.rightMargin: 16
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10

                Row {
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 0
                    Text { text: "Scale: "; color: theme.colorTextSub; font.pixelSize: 11 }
                    Text { text: App.objective.umPerPixel.toFixed(3) + " µm/px"; color: theme.colorAccent; font.pixelSize: 11 }
                }

                Rectangle { width: 1; height: 14; color: theme.colorBorder; anchors.verticalCenter: parent.verticalCenter }

                Text {
                    text: App.objective.activeDisplayName + " objective"
                    color: theme.colorTextSub; font.pixelSize: 11
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
        }

        // 4: Settings View
        Item {
            Row {
                anchors.left: parent.left; anchors.leftMargin: 16; anchors.verticalCenter: parent.verticalCenter; spacing: 10
                Image { source: "icons/logo.svg"; width: 16; height: 16; sourceSize.width: 32; sourceSize.height: 32; fillMode: Image.PreserveAspectFit; smooth: true; anchors.verticalCenter: parent.verticalCenter; anchors.verticalCenterOffset: -1 }
                Text { text: "Settings"; color: theme.colorText; font.pixelSize: 12; font.weight: Font.Medium; anchors.verticalCenter: parent.verticalCenter }
            }
        }
    }
}
