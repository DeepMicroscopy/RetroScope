pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "components"
import RetroScope 1.0

// Sidebar on the right, containing objective selector, focus slider, histogram and bookmarks.
Rectangle {
    id: root

    Theme { id: theme }

    color: theme.colorSurfaceLight

    property var histBins: []

    function showInputPanel() {
        Qt.callLater(function() { App.system.showInputPanel() })
    }

    function normalizedSlack(slack, backlash) {
        var halfBand = Math.abs(Number(backlash)) / 2.0
        if (halfBand <= 0)
            return 0.0
        return Math.max(-1.0, Math.min(1.0, Number(slack) / halfBand))
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

                property real xNorm: root.normalizedSlack(App.motion.backlashSlackX, App.objective.activeBacklashX)
                property real yNorm: root.normalizedSlack(App.motion.backlashSlackY, App.objective.activeBacklashY)
                property real zNorm: root.normalizedSlack(App.motion.backlashSlackZ, App.objective.activeBacklashZ)

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

            // Bookmarks
            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 30
                Text {
                    text: "BOOKMARKS"
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

            ColumnLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 14
                Layout.rightMargin: 14
                Layout.bottomMargin: 10
                spacing: 3

                Repeater {
                    model: App.bookmarks.bookmarkList
                    delegate: Rectangle {
                        id: bmRow
                        required property var modelData
                        required property int index
                        Layout.fillWidth: true
                        height: 44
                        radius: 5
                        color: theme.bgSecondary

                        Column {
                            anchors.fill: parent
                            anchors.leftMargin: 8
                            anchors.rightMargin: 8
                            anchors.topMargin: 6
                            anchors.bottomMargin: 5
                            spacing: 2

                            // Row 1: dot + name + objective
                            Row {
                                width: parent.width
                                spacing: 6
                                Rectangle {
                                    width: 6; height: 6; radius: 3
                                    color: bmRow.modelData.color
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                                Text {
                                    text: bmRow.modelData.name
                                    color: theme.colorText
                                    font.pixelSize: 11
                                    font.weight: Font.Medium
                                    width: parent.width - 6 - 6 - objBadge.width - 6
                                    elide: Text.ElideRight
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                                Rectangle {
                                    id: objBadge
                                    width: objLabel.implicitWidth + 8
                                    height: 16
                                    radius: 8
                                    color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.12)
                                    anchors.verticalCenter: parent.verticalCenter
                                    Text {
                                        id: objLabel
                                        anchors.centerIn: parent
                                        text: bmRow.modelData.objective
                                        color: theme.colorAccent
                                        font.pixelSize: 9
                                        font.weight: Font.Medium
                                    }
                                }
                            }

                            // Row 2: XYZ position
                            Text {
                                text: "X " + bmRow.modelData.x + "  Y " + bmRow.modelData.y + "  Z " + bmRow.modelData.z
                                color: theme.colorTextSub
                                font.pixelSize: 9
                                font.family: "Courier New"
                            }
                        }

                        // Tap -> navigate
                        TapHandler {
                            onTapped: App.bookmarks.navigateTo(bmRow.modelData.name)
                        }
                        // Long press -> delete confirm
                        TapHandler {
                            longPressThreshold: 0.6
                            onLongPressed: {
                                deletePopup.targetName = bmRow.modelData.name
                                deletePopup.open()
                            }
                        }
                    }
                }

                // Save current button
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 28
                    radius: 5
                    color: "transparent"
                    border.color: theme.dark ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0, 0, 0, 0.08)
                    Text {
                        anchors.centerIn: parent
                        text: "+ Save current"
                        color: theme.colorText
                        font.pixelSize: 11
                    }
                    TapHandler {
                        onTapped: {
                            savePopup.nameText = "Mark " + (App.bookmarks.bookmarkList.length + 1)
                            savePopup.open()
                        }
                    }
                }

            }
        }
    } // End: Flickable

    // Save Bookmark popup
    Popup {
        id: savePopup
        anchors.centerIn: parent
        width: 200
        padding: 16
        modal: true
        closePolicy: Popup.CloseOnEscape

        property string nameText: ""

        background: Rectangle {
            color: theme.colorSurface
            radius: 10
            border.color: theme.colorBorder
            border.width: 1
        }

        Column {
            width: parent.width
            spacing: 12

            Text {
                text: "Save Bookmark"
                color: theme.colorText
                font.pixelSize: 13
                font.weight: Font.Medium
            }

            Rectangle {
                width: parent.width
                height: 34
                radius: 6
                color: theme.dark ? Qt.rgba(1, 1, 1, 0.05) : Qt.rgba(0, 0, 0, 0.04)
                border.color: nameField.activeFocus
                              ? Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.5)
                              : theme.colorBorder
                border.width: 1

                TextInput {
                    id: nameField
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    verticalAlignment: TextInput.AlignVCenter
                    text: savePopup.nameText
                    color: theme.colorText
                    font.pixelSize: 12
                    selectByMouse: true
                    onActiveFocusChanged: if (activeFocus) root.showInputPanel()
                    onAccepted: savePopup.accept()
                }
            }

            Row {
                width: parent.width
                spacing: 8

                Rectangle {
                    width: (parent.width - 8) / 2
                    height: 32
                    radius: 6
                    color: theme.dark ? Qt.rgba(1, 1, 1, 0.05) : Qt.rgba(0, 0, 0, 0.04)
                    Text {
                        anchors.centerIn: parent
                        text: "Cancel"
                        color: theme.colorTextSub
                        font.pixelSize: 12
                    }
                    TapHandler { onTapped: savePopup.close() }
                }

                Rectangle {
                    width: (parent.width - 8) / 2
                    height: 32
                    radius: 6
                    color: Qt.rgba(theme.colorAccent.r, theme.colorAccent.g, theme.colorAccent.b, 0.15)
                    Text {
                        anchors.centerIn: parent
                        text: "Save"
                        color: theme.colorAccent
                        font.pixelSize: 12
                        font.weight: Font.Medium
                    }
                    TapHandler {
                        onTapped: savePopup.accept()
                    }
                }
            }
        }

        function accept() {
            var name = nameField.text.trim()
            if (name.length > 0) App.bookmarks.saveCurrent(name)
            savePopup.close()
        }

        onOpened: {
            nameField.text = savePopup.nameText
            nameField.selectAll()
            nameField.forceActiveFocus()
        }
    }

    // Delete Confirm popup
    Popup {
        id: deletePopup
        anchors.centerIn: parent
        width: 200
        padding: 16
        modal: true
        closePolicy: Popup.CloseOnEscape

        property string targetName: ""

        background: Rectangle {
            color: theme.colorSurface
            radius: 10
            border.color: theme.colorBorder
            border.width: 1
        }

        Column {
            width: parent.width
            spacing: 12

            Text {
                text: "Delete Bookmark?"
                color: theme.colorText
                font.pixelSize: 13
                font.weight: Font.Medium
            }

            Text {
                text: deletePopup.targetName
                color: theme.colorTextSub
                font.pixelSize: 11
                width: parent.width
                elide: Text.ElideRight
            }

            Row {
                width: parent.width
                spacing: 8

                Rectangle {
                    width: (parent.width - 8) / 2
                    height: 32
                    radius: 6
                    color: theme.dark ? Qt.rgba(1, 1, 1, 0.05) : Qt.rgba(0, 0, 0, 0.04)
                    Text {
                        anchors.centerIn: parent
                        text: "Cancel"
                        color: theme.colorTextSub
                        font.pixelSize: 12
                    }
                    TapHandler { onTapped: deletePopup.close() }
                }

                Rectangle {
                    width: (parent.width - 8) / 2
                    height: 32
                    radius: 6
                    color: Qt.rgba(0.8, 0.15, 0.15, 0.15)
                    Text {
                        anchors.centerIn: parent
                        text: "Delete"
                        color: theme.colorDanger
                        font.pixelSize: 12
                        font.weight: Font.Medium
                    }
                    TapHandler {
                        onTapped: {
                            App.bookmarks.deleteBM(deletePopup.targetName)
                            deletePopup.close()
                        }
                    }
                }
            }
        }
    }

}
