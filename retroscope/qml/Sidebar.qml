pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "components"
import RetroScope 1.0

// Sidebar on the right, containing objective selector, focus slider, histogram and backlash state.
Rectangle {
    id: root

    Theme { id: theme }

    color: theme.colorSurfaceLight

    property var histBins: []

    function normalizedSlack(slack, backlash) {
        var halfBand = Math.abs(Number(backlash)) / 2.0
        if (halfBand <= 0)
            return 0.0
        return Math.max(-1.0, Math.min(1.0, Number(slack) / halfBand))
    }

    function motionNumber(name) {
        var value = App.motion[name]
        return value === undefined ? 0.0 : Number(value)
    }

    Connections {
        target: App
        function onHistogram_updated(bins) { root.histBins = bins }
    }

    Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: theme.colorBorder }

    Flickable {
        id: sidebarFlick
        anchors.fill: parent
        contentWidth: width
        contentHeight: sidebarContent.implicitHeight
        clip: true
        interactive: true
        acceptedButtons: Qt.LeftButton
        flickableDirection: Flickable.VerticalFlick
        boundsBehavior: Flickable.StopAtBounds

        ScrollBar.vertical: ScrollBar {
            policy: ScrollBar.AsNeeded
            minimumSize: 0.05
        }

        ColumnLayout {
            id: sidebarContent
            width: sidebarFlick.width
            spacing: 0

            // Objective selector
            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 30
                Text {
                    text: "OBJECTIVE"
                    color: theme.colorTextSub
                    font.pixelSize: 10
                    font.weight: Font.Medium
                    font.letterSpacing: 0.8
                    anchors.bottom: parent.bottom
                    anchors.left: parent.left
                    anchors.leftMargin: 14
                    anchors.bottomMargin: 8
                }
            }

            SegmentedButtonGroup {
                Layout.fillWidth: true
                Layout.leftMargin: 10
                Layout.rightMargin: 10
                Layout.bottomMargin: 10
                itemHeight: 28
                itemRadius: 6
                fontSize: 12
                model: App.objective.objectiveNames.map(function(n, i) {
                    return { label: App.objective.objectiveDisplayNames[i] ?? n, value: n }
                })
                currentValue: App.objective.activeObjective
                onSelected: function(v) { App.objective.select(v) }
            }

            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: theme.colorBorder }

            // Focus
            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 34
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 14
                    anchors.rightMargin: 14
                    anchors.topMargin: 10
                    
                    Text {
                        text: "FOCUS"
                        color: theme.colorTextSub
                        font.pixelSize: 10
                        font.weight: Font.Medium
                        font.letterSpacing: 0.8
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: "Z " + App.motion.posZ
                        color: theme.colorTextSub
                        font.pixelSize: 10
                        font.family: "Courier New"
                    }
                }
            }

            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 110

                FocusSlider {
                    anchors.fill: parent
                    anchors.margins: 14
                    anchors.topMargin: 4
                    zPos: App.motion.posZ
                }
            }

            // Histogram
            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 30
                Text {
                    text: "HISTOGRAM"
                    color: theme.colorTextSub
                    font.pixelSize: 10
                    font.weight: Font.Medium
                    font.letterSpacing: 0.8
                    anchors.bottom: parent.bottom
                    anchors.left: parent.left
                    anchors.leftMargin: 14
                    anchors.bottomMargin: 8
                }
            }

            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 62

                Rectangle {
                    anchors.fill: parent
                    anchors.leftMargin: 14
                    anchors.rightMargin: 14
                    anchors.bottomMargin: 10
                    radius: 6
                    color: theme.dark ? "#252528" : "#e0e0e0"

                    Row {
                        anchors.fill: parent
                        anchors.margins: 4
                        anchors.bottomMargin: 2
                        spacing: 1

                        Repeater {
                            model: root.histBins.length > 0 ? root.histBins : Array(64).fill(0)
                            delegate: Item {
                                id: histBar
                                required property real modelData
                                width: (parent.width - 63) / 64
                                height: parent.height
                                Rectangle {
                                    width: parent.width
                                    height: parent.height * (histBar.modelData / 100.0)
                                    anchors.bottom: parent.bottom
                                    color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.2 + (histBar.modelData / 100.0)*0.4)
                                    radius: 1
                                }
                            }
                        }
                    }
                }
            }

            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: theme.colorBorder }

            // Backlash slack
            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 30
                Text {
                    text: "BACKLASH"
                    color: theme.colorTextSub
                    font.pixelSize: 10
                    font.weight: Font.Medium
                    font.letterSpacing: 0.8
                    anchors.bottom: parent.bottom
                    anchors.left: parent.left
                    anchors.leftMargin: 14
                    anchors.bottomMargin: 8
                }
            }

            Item {
                id: backlashViz
                Layout.fillWidth: true
                Layout.preferredHeight: 180

                property real xNorm: root.normalizedSlack(root.motionNumber("backlashSlackX"), App.objective.activeBacklashX)
                property real yNorm: root.normalizedSlack(root.motionNumber("backlashSlackY"), App.objective.activeBacklashY)
                property real zNorm: root.normalizedSlack(root.motionNumber("backlashSlackZ"), App.objective.activeBacklashZ)

                Row {
                    id: backlashRow
                    anchors.fill: parent
                    anchors.leftMargin: 14
                    anchors.rightMargin: 14
                    anchors.bottomMargin: 10
                    spacing: 10

                    Item {
                        id: xyBand
                        width: Math.max(1, Math.min(backlashRow.width - zBand.width - backlashRow.spacing, backlashRow.height))
                        height: width

                        Rectangle {
                            anchors.fill: parent
                            radius: 6
                            color: theme.dark ? "#252528" : "#e0e0e0"
                            border.color: theme.dark ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0, 0, 0, 0.08)
                            border.width: 1
                        }

                        Rectangle {
                            width: 1
                            height: parent.height - 14
                            anchors.centerIn: parent
                            color: theme.dark ? Qt.rgba(1, 1, 1, 0.10) : Qt.rgba(0, 0, 0, 0.12)
                        }

                        Rectangle {
                            width: parent.width - 14
                            height: 1
                            anchors.centerIn: parent
                            color: theme.dark ? Qt.rgba(1, 1, 1, 0.10) : Qt.rgba(0, 0, 0, 0.12)
                        }

                        Rectangle {
                            id: xyDot
                            width: 9
                            height: 9
                            radius: 4.5
                            color: theme.colorAccent
                            border.color: theme.dark ? Qt.rgba(0, 0, 0, 0.35) : Qt.rgba(1, 1, 1, 0.8)
                            border.width: 1
                            x: (xyBand.width - width) / 2 + backlashViz.xNorm * ((xyBand.width - width - 14) / 2)
                            y: (xyBand.height - height) / 2 + backlashViz.yNorm * ((xyBand.height - height - 14) / 2)

                            Behavior on x { NumberAnimation { duration: 90; easing.type: Easing.OutCubic } }
                            Behavior on y { NumberAnimation { duration: 90; easing.type: Easing.OutCubic } }
                        }
                    }

                    Item {
                        id: zBand
                        width: 28
                        height: xyBand.height

                        Rectangle {
                            width: 10
                            height: parent.height
                            radius: 5
                            anchors.horizontalCenter: parent.horizontalCenter
                            color: theme.dark ? "#252528" : "#e0e0e0"
                            border.color: theme.dark ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0, 0, 0, 0.08)
                            border.width: 1
                        }

                        Rectangle {
                            width: parent.width
                            height: 1
                            anchors.verticalCenter: parent.verticalCenter
                            color: theme.dark ? Qt.rgba(1, 1, 1, 0.10) : Qt.rgba(0, 0, 0, 0.12)
                        }

                        Rectangle {
                            id: zMarker
                            width: 18
                            height: 6
                            radius: 3
                            color: theme.colorAccent
                            x: (zBand.width - width) / 2
                            y: (zBand.height - height) / 2 - backlashViz.zNorm * ((zBand.height - height - 14) / 2)

                            Behavior on y { NumberAnimation { duration: 90; easing.type: Easing.OutCubic } }
                        }
                    }
                }
            }

            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: theme.colorBorder }
        }
    } // End: Flickable

}
