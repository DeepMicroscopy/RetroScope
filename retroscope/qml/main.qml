pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.VirtualKeyboard
import "components"
import RetroScope 1.0

ApplicationWindow {
    id: root
    width: 1280
    height: 800
    title: "RetroScope"
    visibility: App.isMockMode ? Window.AutomaticVisibility : Window.FullScreen
    visible: false

    function centerMockWindow() {
        if (!App.isMockMode)
            return
        root.x = Math.max(0, Math.round((Screen.width - root.width) / 2))
        root.y = Math.max(0, Math.round((Screen.height - root.height) / 2))
    }

    Component.onCompleted: {
        centerMockWindow()
        visible = true
    }

    FontLoader { source: "fonts/Font Awesome 7 Free-Solid-900.otf" }
    Theme { id: appTheme }

    // Theme palette
    readonly property bool dark: appTheme.dark
    readonly property color colorBg: appTheme.colorBg
    readonly property color colorSurface: appTheme.colorSurface
    readonly property color colorSurfaceLight: appTheme.colorSurfaceLight
    readonly property color colorBorder: appTheme.colorBorder
    readonly property color colorText: appTheme.colorText
    readonly property color colorTextSub: appTheme.colorTextSub
    readonly property color colorAccent: appTheme.colorAccent
    readonly property color colorAccentLight: appTheme.colorAccentLight
    readonly property color colorAccentFill: appTheme.colorAccentFill
    readonly property color colorDanger: appTheme.colorDanger
    readonly property color colorWarning: appTheme.colorWarning
    readonly property color colorSuccess: appTheme.colorSuccess
    readonly property color colorMeasureGreen: appTheme.colorMeasureGreen
    readonly property color colorMeasureBlue: appTheme.colorMeasureBlue
    readonly property color bgSelected: appTheme.bgSelected
    readonly property color bgSecondary: appTheme.bgSecondary
    readonly property color floatingButtonBg: appTheme.floatingButtonBg
    readonly property color floatingButtonBorder: appTheme.floatingButtonBorder

    property int automationTabIndex: 0
    property string measureSource: "live"   // "live" or "gallery"
    onMeasureSourceChanged: {
        if (measureSource === "gallery") {
            var sel = App.gallery.selectedItem
            // No image selected or video selected -> go to gallery tab to pick an image
            if (!App.gallery.selectedId || sel.type === "video") {
                pageStack.currentIndex = 1
                Qt.callLater(function() { root.measureSource = "live" })
            }
        }
    }

    color: colorBg

    function showToast(msg, isError) {
        toastText.text = msg
        toastRect.color = isError ? root.colorDanger : root.colorAccentFill
        toastAnim.restart()
    }

    // Hot reload toast (dev mode only)
    function showReloadToast(ts) {
        reloadToast.show()
    }

    Connections {
        target: App.status
        function onEndstop_changed(triggered) {
            if (triggered) {
                root.showToast("Endstop triggered: focus limit reached", true)
            }
        }
    }

    Connections {
        target: App
        function onSnapshot_saved(path) {
            root.showToast("Capture saved", false)
        }
        function onSnapshot_failed(reason) {
            root.showToast("Capture failed: " + reason, true)
        }
        function onRecording_saved(path) {
            root.showToast("Recording saved", false)
        }
    }

    Connections {
        target: App.gallery
        function onAction_message(msg) {
            root.showToast(msg, false)
        }
    }

    Connections {
        target: App.autofocus
        function onAutofocus_failed(reason) {
            root.showToast("Autofocus: " + reason, true)
        }
    }

    Connections {
        target: App.motion
        function onMotion_blocked(reason) {
            if (reason === "soft_limit_stage") {
                root.showToast("Stage soft limit reached", true)
            } else if (reason === "soft_limit_automation") {
                root.showToast("Automation target outside stage limits", true)
            } else if (reason === "stage_home_requires_endstop") {
                root.showToast("Move Z to the endstop before setting home", true)
            } else if (reason === "stage_home_failed") {
                root.showToast("Could not set stage home", true)
            } else if (reason === "soft_limits_invalid") {
                root.showToast("Move to bottom-right before saving limits", true)
            } else if (reason === "soft_limits_uncalibrated") {
                root.showToast("Calibrate stage limits first", true)
            }
        }
    }

    // Layout: StatusBar (top) + content + NavBar (bottom)
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

            StatusBar {
                Layout.fillWidth: true
                Layout.preferredHeight: 40
                visible: !(pageStack.currentIndex === 1 && galleryView.showDetail)
                currentTab: pageStack.currentIndex
                automationTabIndex: root.automationTabIndex
                measureSource: root.measureSource
                onAutomationTabSelected: function(index) { root.automationTabIndex = index }
                onMeasureSourceSelected: function(source) { root.measureSource = source }
            }

            // Main content row: LiveView + Sidebar (only on Live tab)
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true

                // Tab pages
                StackLayout {
                    id: pageStack
                    anchors.fill: parent
                    currentIndex: 0

                    // Tab 0: Live View
                    RowLayout {
                        spacing: 0
                        LiveView {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                        }
                        Sidebar {
                            Layout.preferredWidth: 240
                            Layout.fillHeight: true
                        }
                    }

                    // Tab 1: Gallery
                    Item {
                        GalleryView { id: galleryView; anchors.fill: parent }
                    }

                    // Tab 2: Automation
                    Item {
                        AutomationView { anchors.fill: parent; currentSubTab: root.automationTabIndex }
                    }

                    // Tab 3: Measure
                    Item {
                        MeasureView {
                            id: measureView
                            anchors.fill: parent
                            sourceMode: root.measureSource
                        }
                    }

                    // Tab 4: Settings
                    Item {
                        SettingsView { anchors.fill: parent }
                    }
                }
            }

            // Bottom navigation bar
            Rectangle {
                id: navBarBg
                Layout.fillWidth: true
                Layout.preferredHeight: 52
                color: root.colorSurfaceLight
                Rectangle { width: parent.width; height: 1; color: root.colorBorder; anchors.top: parent.top }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 16
                    anchors.rightMargin: 16
                    spacing: 0

                    // Tab buttons
                    SegmentedButtonGroup {
                        Layout.alignment: Qt.AlignVCenter
                        itemFillWidth: false
                        itemHeight: 32
                        itemRadius: 8
                        itemHorizontalPadding: 28
                        fontSize: 12
                        model: [
                            { label: "Live",       value: 0 },
                            { label: "Gallery",    value: 1 },
                            { label: "Automation", value: 2 },
                            { label: "Measure",    value: 3 },
                            { label: "Settings",   value: 4 }
                        ]
                        currentValue: pageStack.currentIndex
                        onSelected: function(v) { pageStack.currentIndex = v }
                    }

                    Item { Layout.fillWidth: true } // Spacer

                    // Right actions
                    Row {
                        Layout.alignment: Qt.AlignVCenter
                        spacing: 10
                        visible: pageStack.currentIndex === 0

                        // Record button
                        Rectangle {
                            width: recordRow.implicitWidth + 24
                            height: 32
                            radius: 7
                            color: App.isRecording
                                   ? Qt.rgba(0.9, 0.2, 0.2, 0.12)
                                   : (root.dark ? Qt.rgba(1, 1, 1, 0.04) : Qt.rgba(0, 0, 0, 0.04))
                            border.color: App.isRecording ? root.colorDanger : "transparent"
                            border.width: 1
                            anchors.verticalCenter: parent.verticalCenter

                            Row {
                                id: recordRow
                                anchors.centerIn: parent
                                spacing: 6
                                Icon {
                                    code: "\uf03d"
                                    iconSize: 12
                                    color: App.isRecording ? root.colorDanger : root.colorTextSub
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                                Text {
                                    text: App.isRecording ? "Stop" : "Record"
                                    color: App.isRecording ? root.colorDanger : root.colorTextSub
                                    font.pixelSize: 11
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                            TapHandler { onTapped: App.toggleRecording() }
                        }

                        // Red Circle (Record toggle)
                        Rectangle {
                            id: shutterBtn
                            width: 42
                            height: 42
                            radius: 21
                            color: Qt.rgba(root.colorDanger.r, root.colorDanger.g, root.colorDanger.b, 0.12)
                            border.color: root.colorDanger
                            border.width: 2
                            anchors.verticalCenter: parent.verticalCenter
                            opacity: App.captureBusy ? 0.55 : 1.0

                            Rectangle {
                                width: 14
                                height: 14
                                radius: 7
                                color: root.colorDanger
                                anchors.centerIn: parent
                                visible: !App.captureBusy
                            }

                            // Spinner: As indicator during capture.
                            Item {
                                anchors.centerIn: parent
                                width: 22
                                height: 22
                                visible: App.captureBusy
                                Rectangle {
                                    anchors.fill: parent
                                    radius: width / 2
                                    color: "transparent"
                                    border.color: Qt.rgba(root.colorDanger.r, root.colorDanger.g, root.colorDanger.b, 0.25)
                                    border.width: 2
                                }
                                Item {
                                    id: spinHub
                                    anchors.centerIn: parent
                                    width: parent.width
                                    height: parent.height
                                    RotationAnimation on rotation {
                                        from: 0; to: 360
                                        duration: 800
                                        loops: Animation.Infinite
                                        running: App.captureBusy
                                    }
                                    Rectangle {
                                        width: 6; height: 6; radius: 3
                                        color: root.colorDanger
                                        x: spinHub.width - width
                                        y: (spinHub.height - height) / 2
                                    }
                                }
                            }

                            TapHandler { onTapped: if (!App.captureBusy) App.takeSnapshot() }
                        }
                    }

                    Row {
                        Layout.alignment: Qt.AlignVCenter
                        spacing: 6
                        visible: pageStack.currentIndex === 1

                        Rectangle {
                            width: measureBtnText.implicitWidth + 28
                            height: 32
                            radius: 7
                            visible: !App.gallery.selectedId || App.gallery.selectedItem.type !== "video"
                            color: Qt.rgba(root.colorAccent.r, root.colorAccent.g, root.colorAccent.b, 0.1)

                            Text {
                                id: measureBtnText
                                anchors.centerIn: parent
                                text: "Measure"
                                color: root.colorAccent
                                font.pixelSize: 11
                                font.weight: Font.Medium
                            }
                            TapHandler {
                                onTapped: {
                                    if (!App.gallery.selectedId) return
                                    if (App.gallery.selectedItem.type === "video") return
                                    App.measurement.clearMeasurements()
                                    root.measureSource = "gallery"
                                    pageStack.currentIndex = 3
                                }
                            }
                        }

                        Rectangle {
                            width: gotoText.implicitWidth + 28
                            height: 32
                            radius: 7
                            color: Qt.rgba(root.colorAccent.r, root.colorAccent.g, root.colorAccent.b, 0.1)

                            Text {
                                id: gotoText
                                anchors.centerIn: parent
                                text: "Go to position"
                                color: root.colorAccent
                                font.pixelSize: 11
                                font.weight: Font.Medium
                            }
                            TapHandler {
                                onTapped: {
                                    App.gallery.goToSelectedPosition()
                                    pageStack.currentIndex = 0
                                }
                            }
                        }

                        Rectangle {
                            width: 34
                            height: 32
                            radius: 7
                            color: Qt.rgba(root.colorDanger.r, root.colorDanger.g, root.colorDanger.b, 0.08)
                            border.color: Qt.rgba(root.colorDanger.r, root.colorDanger.g, root.colorDanger.b, 0.4)
                            border.width: 1

                            Icon {
                                anchors.centerIn: parent
                                code: "\uf2ed"
                                iconSize: 12
                                color: root.colorDanger
                            }
                            TapHandler { onTapped: App.gallery.deleteSelected() }
                        }
                    }
                }
            }
        }

    // Toast notification overlay
    Rectangle {
        id: toastRect
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 70
        width: toastText.implicitWidth + 32
        height: 36
        radius: 18
        color: root.colorAccentFill
        opacity: 0
        z: 100

        Label {
            id: toastText
            anchors.centerIn: parent
            color: "white"
            font.pixelSize: 13
        }

        SequentialAnimation {
            id: toastAnim
            NumberAnimation { target: toastRect; property: "opacity"; to: 1; duration: 150 }
            PauseAnimation { duration: 2500 }
            NumberAnimation { target: toastRect; property: "opacity"; to: 0; duration: 400 }
        }
    }

    // Hot reload toast (dev mode)
    ReloadToast {
        id: reloadToast
        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.topMargin: 50
        visible: App.isMockMode
        z: 200
    }

    Item {
        id: keyboardFocusSink
        parent: Overlay.overlay
        focus: true
    }

    MouseArea {
        id: keyboardDismissArea
        parent: Overlay.overlay
        anchors.fill: parent
        z: 9998
        enabled: inputPanel.active
        visible: enabled
        acceptedButtons: Qt.LeftButton
        propagateComposedEvents: true

        onPressed: function(mouse) {
            if (mouse.y < inputPanel.y) {
                keyboardFocusSink.forceActiveFocus()
            }
            mouse.accepted = false
        }
    }

    InputPanel {
        id: inputPanel
        parent: Overlay.overlay
        z: 9999
        x: 0
        y: root.height
        width: root.width

        states: State {
            name: "visible"
            when: inputPanel.active
            PropertyChanges {
                inputPanel.y: root.height - inputPanel.height
            }
        }

        transitions: Transition {
            NumberAnimation {
                properties: "y"
                duration: 120
                easing.type: Easing.OutQuad
            }
        }
    }
}
