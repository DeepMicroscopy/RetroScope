pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtMultimedia
import "components"
import RetroScope 1.0

Item {
    id: root

    Theme { id: localTheme }

    readonly property color colorText: localTheme.colorText
    readonly property color colorTextSub: localTheme.colorTextSub
    readonly property color colorBg: localTheme.colorBg
    readonly property color colorSurface: localTheme.colorSurface
    readonly property color colorSurfaceLight: localTheme.colorSurfaceLight
    readonly property color colorBorder: localTheme.colorBorder
    readonly property color colorAccent: localTheme.colorAccent
    readonly property color colorAccentFill: localTheme.colorAccentFill

    property bool addingTag: false
    readonly property var predefinedTags: ["cell cluster", "mitosis", "artifact", "reference", "needs review", "good focus"]

    // Detail viewer state
    property bool showDetail: false
    property string sliceMode: "blended" // "blended" | "single"
    property int sliceIndex: 0
    property int _detailVideoPlaybackState: MediaPlayer.StoppedState

    signal detailVideoCommandRequested()

    readonly property bool detailVideoActive: {
        var s = root._detailVideoPlaybackState;
        return s === MediaPlayer.PlayingState || s === MediaPlayer.PausedState;
    }
    readonly property bool detailVideoPlaying: {
        return root._detailVideoPlaybackState === MediaPlayer.PlayingState;
    }

    onShowDetailChanged: {
        if (!showDetail) {
            root._detailVideoPlaybackState = MediaPlayer.StoppedState;
        }
    }

    // Reset viewer state when selection changes, keep detail open
    Connections {
        target: App.gallery
        function onSelected_changed() {
            root.sliceMode = "blended";
            root.sliceIndex = 0;
            detailFlickable.zoomScale = 1.0;
            root._detailVideoPlaybackState = MediaPlayer.StoppedState;
        }
    }

    function firstGroupLabel() {
        var g = App.gallery.groupedItems;
        return (g && g.length > 0 && g[0].label) ? g[0].label : "No captures";
    }
    function firstGroupCount() {
        var g = App.gallery.groupedItems;
        return (g && g.length > 0 && g[0]["items"]) ? g[0]["items"].length : 0;
    }

    function availablePresetTags(selectedTags) {
        var used = selectedTags || [];
        var out = [];
        for (var i = 0; i < root.predefinedTags.length; i++) {
            var t = root.predefinedTags[i];
            if (used.indexOf(t) === -1)
                out.push(t);
        }
        return out;
    }

    function buildDetailChips(item) {
        var chips = [];
        if (item && item.dateLabel)
            chips.push(item.dateLabel + " " + item.timeLabel);
        if (item && item.objective && item.objective !== "")
            chips.push(item.objective);
        if (item && item.resolution && item.resolution !== "n/a")
            chips.push(item.resolution);
        return chips;
    }

    function toggleDetailVideo() {
        root.detailVideoCommandRequested();
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Full-width detail top bar, only shown in detail mode
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 40
            visible: root.showDetail
            color: root.colorSurface

            Rectangle {
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                height: 1
                color: root.colorBorder
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 0
                anchors.rightMargin: 12
                spacing: 6

                // Back button
                Rectangle {
                    Layout.preferredWidth: 44
                    Layout.preferredHeight: 40
                    color: "transparent"
                    Icon {
                        anchors.centerIn: parent
                        code: "\uf060"
                        iconSize: 14
                        color: root.colorText
                    }
                    TapHandler {
                        onTapped: root.showDetail = false
                    }
                }

                // Filename
                Text {
                    text: detailViewer.dHasItem ? detailViewer.dItem.filename : ""
                    color: root.colorText
                    font.pixelSize: 12
                    font.weight: Font.Medium
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                    Layout.maximumWidth: 220
                }

                // Date / objective / resolution chips
                Row {
                    spacing: 4
                    Repeater {
                        model: detailViewer.dHasItem ? root.buildDetailChips(detailViewer.dItem) : []
                        delegate: Rectangle {
                            id: chipRoot
                            required property string modelData
                            height: 22
                            width: chipLbl.implicitWidth + 12
                            radius: 4
                            color: Qt.rgba(root.colorAccent.r, root.colorAccent.g, root.colorAccent.b, 0.15)
                            Text {
                                id: chipLbl
                                anchors.centerIn: parent
                                text: chipRoot.modelData
                                color: root.colorAccent
                                font.pixelSize: 10
                            }
                        }
                    }
                }

                Item {
                    Layout.fillWidth: true
                }

                // Video play / pause
                Rectangle {
                    visible: detailViewer.dIsVideo
                    Layout.preferredWidth: 80
                    Layout.preferredHeight: 28
                    radius: 6
                    color: root.colorAccentFill
                    Row {
                        anchors.centerIn: parent
                        spacing: 5
                        Icon {
                            code: root.detailVideoPlaying ? "\uf04c" : "\uf04b"
                            iconSize: 10
                            color: "#ffffff"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: root.detailVideoPlaying ? "Pause" : "Play"
                            color: "#ffffff"
                            font.pixelSize: 11
                            font.weight: Font.Medium
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    TapHandler {
                        onTapped: root.toggleDetailVideo()
                    }
                }

                // Stack / Scan mode toggle
                Row {
                    spacing: 4
                    visible: detailViewer.dIsMultiView

                    Rectangle {
                        width: 76
                        height: 28
                        radius: 6
                        color: root.sliceMode === "blended" ? root.colorAccentFill : root.colorSurfaceLight
                        border.color: root.colorBorder
                        border.width: 1
                        Text {
                            anchors.centerIn: parent
                            font.pixelSize: 11
                            text: detailViewer.dIsStack ? "Blended" : "Stitched"
                            color: root.sliceMode === "blended" ? "#ffffff" : root.colorText
                        }
                        TapHandler {
                            onTapped: root.sliceMode = "blended"
                        }
                    }
                    Rectangle {
                        width: 88
                        height: 28
                        radius: 6
                        color: root.sliceMode === "single" ? root.colorAccentFill : root.colorSurfaceLight
                        border.color: root.colorBorder
                        border.width: 1
                        Text {
                            anchors.centerIn: parent
                            font.pixelSize: 11
                            text: detailViewer.dIsStack ? "Single Slice" : "Tile View"
                            color: root.sliceMode === "single" ? "#ffffff" : root.colorText
                        }
                        TapHandler {
                            onTapped: root.sliceMode = "single"
                        }
                    }
                }
            }
        }

        // Main content row (left panel + sidebar)
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // Left panel
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: root.colorBg

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                    // Sticky gallery controls
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.showDetail ? 0 : 40
                        visible: !root.showDetail
                        color: root.colorSurface

                        Rectangle {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            height: 1
                            color: root.colorBorder
                        }

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 12
                            anchors.rightMargin: 12
                            spacing: 8

                            Text {
                                text: App.gallery.captureCount + " captures"
                                color: root.colorTextSub
                                font.pixelSize: 11
                                Layout.fillWidth: true
                            }

                            Rectangle {
                                Layout.preferredHeight: 24
                                Layout.preferredWidth: sortStickyLabel.implicitWidth + 22
                                radius: 5
                                color: root.colorSurfaceLight
                                border.color: root.colorBorder
                                border.width: 1

                                Row {
                                    anchors.centerIn: parent
                                    spacing: 5
                                    
                                    Icon {
                                        code: "\uf078"
                                        iconSize: 8
                                        color: root.colorTextSub
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                    Text {
                                        id: sortStickyLabel
                                        text: App.gallery.sortOrder === "newest" ? "Newest first" : "Oldest first"
                                        color: root.colorTextSub
                                        font.pixelSize: 10
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                }

                                TapHandler {
                                    onTapped: App.gallery.setSortOrder(App.gallery.sortOrder === "newest" ? "oldest" : "newest")
                                }
                            }
                        }
                    }

                    // Content area
                    Item {
                        Layout.fillWidth: true
                        Layout.fillHeight: true

                        // Grid / List
                        Item {
                            anchors.fill: parent
                            visible: !root.showDetail

                            Item {
                                anchors.fill: parent
                                anchors.margins: 12
                                anchors.topMargin: 8

                                TouchScrollView {
                                    id: groupedGridScroll
                                    anchors.fill: parent
                                    visible: App.gallery.viewMode === "grid"
                                    clip: true
                                    contentWidth: availableWidth

                                    Column {
                                        id: groupedGridColumn
                                        width: groupedGridScroll.availableWidth
                                        spacing: 10

                                        Repeater {
                                            model: App.gallery.groupedItems
                                            delegate: Column {
                                                id: gridGroupRoot
                                                required property var modelData
                                                property var group: gridGroupRoot.modelData
                                                property var groupItems: (gridGroupRoot.group && gridGroupRoot.group["items"]) ? gridGroupRoot.group["items"] : []
                                                width: parent.width
                                                spacing: 6

                                                Row {
                                                    width: parent.width
                                                    spacing: 0
                                                    Text {
                                                        text: gridGroupRoot.group.label + " (" + gridGroupRoot.groupItems.length + " captures)"
                                                        color: root.colorTextSub
                                                        font.pixelSize: 11
                                                    }
                                                }

                                                Flow {
                                                    id: groupFlow
                                                    width: parent.width
                                                    spacing: 6
                                                    Repeater {
                                                        model: gridGroupRoot.groupItems
                                                        delegate: Item {
                                                            id: gridItemRoot
                                                            required property var modelData
                                                            property var item: gridItemRoot.modelData
                                                            width: Math.max(120, Math.floor((groupFlow.width - 24) / 5))
                                                            height: width * 0.75
                                                            RoundedMediaPreview {
                                                                anchors.fill: parent
                                                                radius: 6
                                                                backgroundColor: root.colorSurfaceLight
                                                                borderColor: root.colorBorder
                                                                borderWidth: 1
                                                                source: gridItemRoot.item.isVideo ? (gridItemRoot.item.previewUrl || "") : (gridItemRoot.item.fileUrl || "")
                                                                imageVisible: !gridItemRoot.item.isVideo || !!gridItemRoot.item.previewUrl
                                                                fillMode: Image.PreserveAspectCrop
                                                                asynchronous: true
                                                                cache: false
                                                                Rectangle {
                                                                    anchors.fill: parent
                                                                    anchors.margins: 1
                                                                    visible: gridItemRoot.item.isVideo
                                                                    radius: 5
                                                                    color: Qt.rgba(0, 0, 0, 0.35)
                                                                }
                                                                Rectangle {
                                                                    visible: gridItemRoot.item.objective !== ""
                                                                    anchors.top: parent.top
                                                                    anchors.right: parent.right
                                                                    anchors.margins: 4
                                                                    color: App.gallery.selectedId === gridItemRoot.item.itemId ? root.colorAccent : Qt.rgba(0, 0, 0, 0.55)
                                                                    radius: 4
                                                                    height: 16
                                                                    width: objText.implicitWidth + 8
                                                                    Text {
                                                                        id: objText
                                                                        anchors.centerIn: parent
                                                                        text: gridItemRoot.item.objective
                                                                        color: App.gallery.selectedId === gridItemRoot.item.itemId ? "#ffffff" : "#a9a9ad"
                                                                        font.pixelSize: 9
                                                                        font.weight: Font.Medium
                                                                    }
                                                                }
                                                                Rectangle {
                                                                    visible: gridItemRoot.item.type !== "snapshot"
                                                                    anchors.top: parent.top
                                                                    anchors.left: parent.left
                                                                    anchors.margins: 4
                                                                    color: Qt.rgba(0, 0, 0, 0.55)
                                                                    radius: 4
                                                                    height: 16
                                                                    width: typeText.implicitWidth + 8
                                                                    Text {
                                                                        id: typeText
                                                                        anchors.centerIn: parent
                                                                        text: gridItemRoot.item.typeLabel.toUpperCase()
                                                                        color: gridItemRoot.item.type === "stack" ? "#EF9F27" : "#85B7EB"
                                                                        font.pixelSize: 8
                                                                        font.weight: Font.Medium
                                                                    }
                                                                }
                                                                Rectangle {
                                                                    anchors.left: parent.left
                                                                    anchors.right: parent.right
                                                                    anchors.bottom: parent.bottom
                                                                    height: 20
                                                                    gradient: Gradient {
                                                                        GradientStop {
                                                                            position: 0.0
                                                                            color: "transparent"
                                                                        }
                                                                        GradientStop {
                                                                            position: 1.0
                                                                            color: Qt.rgba(0, 0, 0, 0.7)
                                                                        }
                                                                    }
                                                                    Text {
                                                                        anchors.left: parent.left
                                                                        anchors.leftMargin: 6
                                                                        anchors.bottom: parent.bottom
                                                                        anchors.bottomMargin: 4
                                                                        text: gridItemRoot.item.timeLabel
                                                                        color: "#d0d0d0"
                                                                        font.pixelSize: 9
                                                                    }
                                                                }
                                                                Rectangle {
                                                                    anchors.fill: parent
                                                                    color: "transparent"
                                                                    radius: 6
                                                                    border.color: root.colorAccent
                                                                    border.width: App.gallery.selectedId === gridItemRoot.item.itemId ? 2 : 0
                                                                }
                                                                TapHandler {
                                                                    onTapped: App.gallery.selectItem(gridItemRoot.item.itemId)
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }

                                TouchScrollView {
                                    id: groupedListScroll
                                    anchors.fill: parent
                                    visible: App.gallery.viewMode === "list"
                                    clip: true
                                    contentWidth: availableWidth

                                    Column {
                                        id: groupedListColumn
                                        width: groupedListScroll.availableWidth
                                        spacing: 6
                                        Repeater {
                                            model: App.gallery.groupedItems
                                            delegate: Column {
                                                id: listGroupRoot
                                                required property var modelData
                                                property var group: listGroupRoot.modelData
                                                property var groupItems: (listGroupRoot.group && listGroupRoot.group["items"]) ? listGroupRoot.group["items"] : []
                                                width: parent.width
                                                spacing: 4

                                                Row {
                                                    width: parent.width
                                                    spacing: 0
                                                    Text {
                                                        text: listGroupRoot.group.label + " (" + listGroupRoot.groupItems.length + " captures)"
                                                        color: root.colorTextSub
                                                        font.pixelSize: 11
                                                    }
                                                }

                                                Repeater {
                                                    model: listGroupRoot.groupItems
                                                    delegate: Rectangle {
                                                        id: listItemRoot
                                                        required property var modelData
                                                        property var item: listItemRoot.modelData
                                                        width: groupedListColumn.width
                                                        height: 48
                                                        radius: 6
                                                        color: App.gallery.selectedId === listItemRoot.item.itemId ? Qt.rgba(root.colorAccent.r, root.colorAccent.g, root.colorAccent.b, 0.12) : root.colorSurface
                                                        border.color: App.gallery.selectedId === listItemRoot.item.itemId ? root.colorAccent : root.colorBorder
                                                        border.width: App.gallery.selectedId === listItemRoot.item.itemId ? 2 : 1

                                                        RoundedMediaPreview {
                                                            id: listThumb
                                                            anchors.left: parent.left
                                                            anchors.top: parent.top
                                                            anchors.leftMargin: 4
                                                            anchors.topMargin: 4
                                                            width: 56
                                                            height: 40
                                                            radius: 4
                                                            backgroundColor: root.colorSurfaceLight
                                                            borderColor: "transparent"
                                                            borderWidth: 0
                                                            source: listItemRoot.item.isVideo ? (listItemRoot.item.previewUrl || "") : (listItemRoot.item.fileUrl || "")
                                                            imageVisible: !listItemRoot.item.isVideo || !!listItemRoot.item.previewUrl
                                                            fillMode: Image.PreserveAspectCrop
                                                            asynchronous: true
                                                            cache: false
                                                        }
                                                        Text {
                                                            id: listFileSize
                                                            anchors.right: parent.right
                                                            anchors.rightMargin: 8
                                                            anchors.verticalCenter: parent.verticalCenter
                                                            text: listItemRoot.item.fileSize
                                                            color: root.colorTextSub
                                                            font.pixelSize: 10
                                                        }
                                                        Column {
                                                            anchors.left: listThumb.right
                                                            anchors.leftMargin: 8
                                                            anchors.right: listFileSize.left
                                                            anchors.rightMargin: 8
                                                            anchors.top: listThumb.top
                                                            spacing: 2
                                                            Text {
                                                                width: parent.width
                                                                text: listItemRoot.item.filename
                                                                color: root.colorText
                                                                font.pixelSize: 11
                                                                elide: Text.ElideRight
                                                            }
                                                            Text {
                                                                width: parent.width
                                                                text: listItemRoot.item.typeLabel + " • " + listItemRoot.item.timeLabel + " • " + listItemRoot.item.resolution
                                                                color: root.colorTextSub
                                                                font.pixelSize: 10
                                                                elide: Text.ElideRight
                                                            }
                                                        }
                                                        TapHandler {
                                                            onTapped: App.gallery.selectItem(listItemRoot.item.itemId)
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // Detail viewer
                        Item {
                            id: detailViewer
                            anchors.fill: parent
                            visible: root.showDetail

                            property var dItem: App.gallery.selectedItem || {}
                            property bool dHasItem: !!dItem && dItem.id !== undefined
                            property bool dIsVideo: !!dItem.isVideo
                            property bool dIsStack: dItem.type === "stack"
                            property bool dIsPanorama: dItem.type === "stitch"
                            property var dFrames: dItem.frames || []
                            property var dTiles: dItem.tiles || []
                            property bool dIsMultiView: dIsStack || dIsPanorama
                            property bool dShowScrubber: dIsMultiView && root.sliceMode === "single"
                            property var dScrubItems: dIsStack ? dFrames : dTiles

                            // Image / stack / scan
                            Flickable {
                                id: detailFlickable
                                anchors.fill: parent
                                visible: !detailViewer.dIsVideo
                                clip: true
                                interactive: true
                                acceptedButtons: Qt.LeftButton
                                contentWidth: Math.max(width, width * detailFlickable.zoomScale)
                                contentHeight: Math.max(height, height * detailFlickable.zoomScale)
                                boundsMovement: Flickable.StopAtBounds
                                property real zoomScale: 1.0
                                onZoomScaleChanged: {
                                    contentX = Math.max(0, (contentWidth - width) / 2);
                                    contentY = Math.max(0, (contentHeight - height) / 2);
                                }

                                Image {
                                    width: detailFlickable.contentWidth
                                    height: detailFlickable.contentHeight
                                    source: {
                                        if (!detailViewer.dHasItem || detailViewer.dIsVideo)
                                            return "";
                                        if (detailViewer.dShowScrubber && root.sliceIndex >= 0 && root.sliceIndex < detailViewer.dScrubItems.length)
                                            return detailViewer.dScrubItems[root.sliceIndex];
                                        return detailViewer.dItem.fileUrl || "";
                                    }
                                    fillMode: Image.PreserveAspectCrop
                                    asynchronous: false
                                    cache: true
                                }

                                PinchHandler {
                                    target: null
                                    minimumScale: 1.0
                                    maximumScale: 6.0
                                    onActiveScaleChanged: {
                                        var s = Math.max(1.0, Math.min(6.0, detailFlickable.zoomScale * activeScale));
                                        detailFlickable.zoomScale = s;
                                    }
                                }

                                TapHandler {
                                    onTapped: {
                                        if (tapCount === 2)
                                            detailFlickable.zoomScale = detailFlickable.zoomScale > 1.05 ? 1.0 : 2.5;
                                    }
                                }
                            }

                            // Video: thumbnail fallback + player
                            Item {
                                anchors.fill: parent
                                visible: detailViewer.dIsVideo

                                Image {
                                    anchors.fill: parent
                                    source: detailViewer.dHasItem ? (detailViewer.dItem.previewUrl || detailViewer.dItem.fileUrl || "") : ""
                                    fillMode: Image.PreserveAspectCrop
                                    asynchronous: true
                                    cache: false
                                }

                                Loader {
                                    id: detailVideoLoader
                                    anchors.fill: parent
                                    active: detailViewer.dIsVideo && root.showDetail
                                    opacity: root.detailVideoActive ? 1.0 : 0.0
                                    sourceComponent: Component {
                                        Item {
                                            VideoOutput {
                                                id: detailVideoOutput
                                                anchors.fill: parent
                                                fillMode: VideoOutput.PreserveAspectCrop
                                            }

                                            MediaPlayer {
                                                id: detailVideoPlayer
                                                source: detailViewer.dHasItem && detailViewer.dIsVideo && root.showDetail
                                                        ? (detailViewer.dItem.playbackUrl || detailViewer.dItem.fileUrl || "")
                                                        : ""
                                                videoOutput: detailVideoOutput
                                                audioOutput: AudioOutput {
                                                    volume: 1.0
                                                }

                                                onPlaybackStateChanged: root._detailVideoPlaybackState = playbackState
                                            }

                                            Connections {
                                                target: root
                                                function onDetailVideoCommandRequested() {
                                                    if (detailVideoPlayer.playbackState === MediaPlayer.PlayingState)
                                                        detailVideoPlayer.pause();
                                                    else
                                                        detailVideoPlayer.play();
                                                }
                                            }
                                        }
                                    }
                                    onActiveChanged: {
                                        if (!active)
                                            root._detailVideoPlaybackState = MediaPlayer.StoppedState;
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Right sidebar, always visible
            Rectangle {
                Layout.preferredWidth: 240
                Layout.fillHeight: true
                color: root.colorSurface
                Rectangle { width: 1; height: parent.height; color: root.colorBorder }

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                    // Header (hidden in detail mode)
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 38
                        color: "transparent"
                        visible: !root.showDetail
                        Text {
                            text: "SELECTED IMAGE"
                            color: root.colorTextSub
                            font.pixelSize: 10
                            font.weight: Font.Medium
                            font.letterSpacing: 0.8
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left
                            anchors.leftMargin: 14
                        }
                    }

                    TouchScrollView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        contentWidth: width

                        ColumnLayout {
                            id: sidebarContent
                            width: parent.width
                            spacing: 0

                            property var selected: App.gallery.selectedItem
                            property bool hasSelection: !!selected && selected.id !== undefined

                            // Preview thumbnail (hidden in detail mode)
                            Item {
                                Layout.fillWidth: true
                                Layout.preferredHeight: width * 0.75
                                Layout.margins: 12
                                Layout.topMargin: 0
                                visible: !root.showDetail

                                RoundedMediaPreview {
                                    anchors.fill: parent
                                    radius: 6
                                    backgroundColor: root.colorBg
                                    borderColor: root.colorBorder
                                    borderWidth: 1
                                    source: sidebarContent.hasSelection ? (sidebarContent.selected.isVideo ? (sidebarContent.selected.previewUrl || "") : (sidebarContent.selected.fileUrl || "")) : ""
                                    fillMode: Image.PreserveAspectCrop
                                    imageVisible: sidebarContent.hasSelection && (!sidebarContent.selected.isVideo || !!sidebarContent.selected.previewUrl)
                                    asynchronous: true
                                    cache: false

                                    Rectangle {
                                        anchors.top: parent.top
                                        anchors.left: parent.left
                                        anchors.margins: 4
                                        width: 32
                                        height: 32
                                        radius: 6
                                        color: Qt.rgba(0, 0, 0, 0.5)
                                        visible: sidebarContent.hasSelection
                                        Icon {
                                            anchors.centerIn: parent
                                            code: sidebarContent.hasSelection && sidebarContent.selected.isVideo ? "\uf04b" : "\uf065"
                                            iconSize: 10
                                            color: "#bcbcbc"
                                        }
                                        TapHandler {
                                            onTapped: root.showDetail = true
                                        }
                                    }
                                }
                            }

                            // Viewer controls (detail mode only)
                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.leftMargin: 12
                                Layout.rightMargin: 12
                                Layout.topMargin: 12
                                Layout.bottomMargin: 12
                                spacing: 8
                                visible: root.showDetail

                                // Prev / Next navigation
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 6

                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 36
                                        radius: 6
                                        color: App.gallery.selectedIndex > 0 ? root.colorSurfaceLight : Qt.rgba(root.colorSurfaceLight.r, root.colorSurfaceLight.g, root.colorSurfaceLight.b, 0.4)
                                        border.color: root.colorBorder
                                        border.width: 1
                                        Row {
                                            anchors.centerIn: parent
                                            spacing: 5
                                            Icon {
                                                code: "\uf060"
                                                iconSize: 10
                                                color: App.gallery.selectedIndex > 0 ? root.colorText : root.colorTextSub
                                                anchors.verticalCenter: parent.verticalCenter
                                            }
                                            Text {
                                                text: "Prev"
                                                font.pixelSize: 12
                                                color: App.gallery.selectedIndex > 0 ? root.colorText : root.colorTextSub
                                                anchors.verticalCenter: parent.verticalCenter
                                            }
                                        }
                                        TapHandler {
                                            enabled: App.gallery.selectedIndex > 0
                                            onTapped: App.gallery.selectByIndex(App.gallery.selectedIndex - 1)
                                        }
                                    }
                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 36
                                        radius: 6
                                        color: App.gallery.selectedIndex < App.gallery.captureCount - 1 ? root.colorSurfaceLight : Qt.rgba(root.colorSurfaceLight.r, root.colorSurfaceLight.g, root.colorSurfaceLight.b, 0.4)
                                        border.color: root.colorBorder
                                        border.width: 1
                                        Row {
                                            anchors.centerIn: parent
                                            spacing: 5
                                            Text {
                                                text: "Next"
                                                font.pixelSize: 12
                                                color: App.gallery.selectedIndex < App.gallery.captureCount - 1 ? root.colorText : root.colorTextSub
                                                anchors.verticalCenter: parent.verticalCenter
                                            }
                                            Icon {
                                                code: "\uf061"
                                                iconSize: 10
                                                color: App.gallery.selectedIndex < App.gallery.captureCount - 1 ? root.colorText : root.colorTextSub
                                                anchors.verticalCenter: parent.verticalCenter
                                            }
                                        }
                                        TapHandler {
                                            enabled: App.gallery.selectedIndex < App.gallery.captureCount - 1
                                            onTapped: App.gallery.selectByIndex(App.gallery.selectedIndex + 1)
                                        }
                                    }
                                }

                                // Slice / tile slider
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 4
                                    Layout.bottomMargin: 6
                                    visible: sidebarContent.hasSelection && (sidebarContent.selected.type === "stack" || sidebarContent.selected.type === "stitch") && root.sliceMode === "single"

                                    RowLayout {
                                        Layout.fillWidth: true
                                        Text {
                                            text: sidebarContent.hasSelection && sidebarContent.selected.type === "stack" ? "SLICE" : "TILE"
                                            color: root.colorTextSub
                                            font.pixelSize: 10
                                            font.weight: Font.Medium
                                            font.letterSpacing: 0.8
                                        }
                                        Item {
                                            Layout.fillWidth: true
                                        }
                                        Text {
                                            text: {
                                                var items = sidebarContent.hasSelection ? (sidebarContent.selected.type === "stack" ? (sidebarContent.selected.frames || []) : (sidebarContent.selected.tiles || [])) : [];
                                                return (root.sliceIndex + 1) + " / " + items.length;
                                            }
                                            color: root.colorTextSub
                                            font.pixelSize: 10
                                            font.family: "Courier New"
                                        }
                                    }

                                    SSlider {
                                        Layout.fillWidth: true
                                        from: 0
                                        to: {
                                            var items = sidebarContent.hasSelection ? (sidebarContent.selected.type === "stack" ? (sidebarContent.selected.frames || []) : (sidebarContent.selected.tiles || [])) : [];
                                            return Math.max(0, items.length - 1);
                                        }
                                        stepSize: 1
                                        value: root.sliceIndex
                                        onValueEdited: function(v) { root.sliceIndex = Math.round(v) }
                                    }
                                }
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 1
                                color: root.colorBorder
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 32
                                color: "transparent"
                                Text {
                                    text: "METADATA"
                                    color: root.colorTextSub
                                    font.pixelSize: 10
                                    font.weight: Font.Medium
                                    font.letterSpacing: 0.8
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.left: parent.left
                                    anchors.leftMargin: 14
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.leftMargin: 14
                                Layout.rightMargin: 14
                                Layout.bottomMargin: 14
                                spacing: 6
                                Repeater {
                                    model: sidebarContent.hasSelection ? [
                                        {
                                            k: "Date",
                                            v: sidebarContent.selected.dateLabel + ", " + sidebarContent.selected.timeLabel,
                                            c: root.colorText
                                        },
                                        {
                                            k: "Type",
                                            v: sidebarContent.selected.typeLabel,
                                            c: root.colorText
                                        },
                                        {
                                            k: "Objective",
                                            v: sidebarContent.selected.objectiveLabel,
                                            c: root.colorAccent
                                        },
                                        {
                                            k: "Resolution",
                                            v: sidebarContent.selected.resolution,
                                            c: root.colorText
                                        },
                                        {
                                            k: "File size",
                                            v: sidebarContent.selected.fileSize,
                                            c: root.colorText
                                        },
                                        {
                                            k: "Format",
                                            v: sidebarContent.selected.format,
                                            c: root.colorText
                                        }
                                    ] : []
                                    delegate: RowLayout {
                                        id: metadataRow
                                        required property var modelData
                                        Layout.fillWidth: true
                                        Text {
                                            text: metadataRow.modelData.k
                                            color: root.colorTextSub
                                            font.pixelSize: 11
                                        }
                                        Item {
                                            Layout.fillWidth: true
                                        }
                                        Text {
                                            text: metadataRow.modelData.v
                                            color: metadataRow.modelData.c
                                            font.pixelSize: 11
                                        }
                                    }
                                }
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 1
                                color: root.colorBorder
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 32
                                color: "transparent"
                                Text {
                                    text: "POSITION"
                                    color: root.colorTextSub
                                    font.pixelSize: 10
                                    font.weight: Font.Medium
                                    font.letterSpacing: 0.8
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.left: parent.left
                                    anchors.leftMargin: 14
                                }
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                Layout.leftMargin: 14
                                Layout.rightMargin: 14
                                Layout.bottomMargin: 14
                                spacing: 8
                                Repeater {
                                    model: sidebarContent.hasSelection ? (function () {
                                            var s = sidebarContent.selected;
                                            var zv = (s.pos_z === null || s.pos_z === undefined) ? "n/a" : (s.zHalfRange ? (s.pos_z + "\n±" + s.zHalfRange) : String(s.pos_z));
                                            return [
                                                {
                                                    lbl: "X",
                                                    v: s.pos_x === null || s.pos_x === undefined ? "n/a" : String(s.pos_x)
                                                },
                                                {
                                                    lbl: "Y",
                                                    v: s.pos_y === null || s.pos_y === undefined ? "n/a" : String(s.pos_y)
                                                },
                                                {
                                                    lbl: "Z",
                                                    v: zv
                                                }
                                            ];
                                        })() : []
                                    delegate: Rectangle {
                                        id: positionCell
                                        required property var modelData
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 38
                                        color: root.colorSurfaceLight
                                        radius: 5
                                        Column {
                                            anchors.centerIn: parent
                                            spacing: 1
                                            Text {
                                                text: positionCell.modelData.lbl
                                                color: root.colorTextSub
                                                font.pixelSize: 9
                                                anchors.horizontalCenter: parent.horizontalCenter
                                            }
                                            Text {
                                                text: positionCell.modelData.v
                                                color: root.colorTextSub
                                                font.pixelSize: positionCell.modelData.v.indexOf("\n") >= 0 ? 9 : 12
                                                font.family: "Courier New"
                                                horizontalAlignment: Text.AlignHCenter
                                                anchors.horizontalCenter: parent.horizontalCenter
                                            }
                                        }
                                    }
                                }
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 1
                                color: root.colorBorder
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 32
                                color: "transparent"
                                Text {
                                    text: "TAGS"
                                    color: root.colorTextSub
                                    font.pixelSize: 10
                                    font.weight: Font.Medium
                                    font.letterSpacing: 0.8
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.left: parent.left
                                    anchors.leftMargin: 14
                                }
                            }

                            Flow {
                                Layout.fillWidth: true
                                Layout.leftMargin: 14
                                Layout.rightMargin: 14
                                spacing: 4
                                Repeater {
                                    model: sidebarContent.hasSelection ? sidebarContent.selected.tags : []
                                    delegate: Rectangle {
                                        id: tagRoot
                                        required property string modelData
                                        height: 20
                                        width: tagValue.implicitWidth + 22
                                        radius: 4
                                        color: Qt.rgba(root.colorAccent.r, root.colorAccent.g, root.colorAccent.b, 0.08)
                                        Text {
                                            id: tagValue
                                            anchors.left: parent.left
                                            anchors.leftMargin: 6
                                            anchors.right: tagRemove.left
                                            anchors.rightMargin: 4
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: tagRoot.modelData
                                            color: root.colorAccent
                                            font.pixelSize: 10
                                        }
                                        Item {
                                            id: tagRemove
                                            anchors.right: parent.right
                                            anchors.rightMargin: 6
                                            anchors.verticalCenter: parent.verticalCenter
                                            width: 10
                                            height: 10
                                            Icon {
                                                anchors.centerIn: parent
                                                code: "\uf00d"
                                                iconSize: 8
                                                color: root.colorAccent
                                            }
                                            TapHandler {
                                                onTapped: App.gallery.removeTag(tagRoot.modelData)
                                            }
                                        }
                                    }
                                }
                                Rectangle {
                                    visible: sidebarContent.hasSelection
                                    height: 20
                                    width: addText.implicitWidth + 14
                                    radius: 4
                                    color: "transparent"
                                    border.color: root.colorBorder
                                    border.width: 1
                                    Text {
                                        id: addText
                                        anchors.centerIn: parent
                                        text: "+ add"
                                        color: root.colorTextSub
                                        font.pixelSize: 10
                                    }
                                    TapHandler {
                                        onTapped: root.addingTag = !root.addingTag
                                    }
                                }
                            }

                            Flow {
                                visible: root.addingTag && sidebarContent.hasSelection
                                Layout.fillWidth: true
                                Layout.leftMargin: 14
                                Layout.rightMargin: 14
                                Layout.topMargin: 8
                                Layout.bottomMargin: 14
                                spacing: 5
                                Repeater {
                                    model: root.availablePresetTags(sidebarContent.selected.tags)
                                    delegate: Rectangle {
                                        id: presetRoot
                                        required property string modelData
                                        height: 22
                                        width: presetText.implicitWidth + 16
                                        radius: 4
                                        color: root.colorSurfaceLight
                                        border.color: root.colorBorder
                                        border.width: 1
                                        Text {
                                            id: presetText
                                            anchors.centerIn: parent
                                            text: presetRoot.modelData
                                            color: root.colorTextSub
                                            font.pixelSize: 10
                                        }
                                        TapHandler {
                                            onTapped: {
                                                App.gallery.addTag(presetRoot.modelData);
                                                root.addingTag = false;
                                            }
                                        }
                                    }
                                }
                            }

                            Item {
                                Layout.fillHeight: true
                                Layout.minimumHeight: 16
                            }
                        }
                    }
                }
            }
        }
    }
}
