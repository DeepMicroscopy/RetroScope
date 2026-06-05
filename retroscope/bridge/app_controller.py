"""AppController: Single root QObject exposed to QML as 'App'."""

from PySide6.QtCore import Property, QObject, Signal, Slot

from retroscope.bridge.autofocus_bridge import AutofocusBridge
from retroscope.bridge.calibration_bridge import CalibrationBridge
from retroscope.bridge.objective_detector_bridge import ObjectiveDetectorBridge
from retroscope.bridge.automation_bridge import AutomationBridge
from retroscope.bridge.bookmark_bridge import BookmarkBridge
from retroscope.bridge.button_bridge import ButtonBridge
from retroscope.bridge.direct_camera_bridge import DirectCameraBridge
from retroscope.bridge.motion_bridge import MotionBridge
from retroscope.bridge.objective_bridge import ObjectiveBridge
from retroscope.bridge.overlay_bridge import OverlayBridge
from retroscope.bridge.gallery_bridge import GalleryBridge
from retroscope.bridge.measurement_bridge import MeasurementBridge
from retroscope.bridge.settings_bridge import SettingsBridge
from retroscope.bridge.status_bridge import StatusBridge
from retroscope.bridge.system_bridge import SystemBridge
from retroscope.bridge.update_bridge import UpdateBridge
from retroscope.platform import is_pi
from retroscope.services.camera_service import CameraService
from retroscope.services.measurement_capture import MeasurementCaptureService


class AppController(QObject):
    """Root application controller exposed to QML."""

    frameAvailable        = Signal()
    snapshot_saved        = Signal(str)          # path
    snapshot_failed       = Signal(str)          # reason
    capture_busy_changed  = Signal(bool)         # native capture in progress
    recording_saved       = Signal(str)          # path
    histogram_updated     = Signal(list)         # 64 ints [0..100]
    focus_score_updated   = Signal(float)        # raw Laplacian variance
    focus_source_updated  = Signal(str)          # "source" or "analysis"
    fps_updated           = Signal(float)        # measured capture FPS
    camera_resolution_changed = Signal(str)
    camera_capabilities_changed = Signal()
    recording_changed     = Signal(bool)

    def __init__(
        self,
        motion: MotionBridge,
        objective: ObjectiveBridge,
        overlay: OverlayBridge,
        gallery: GalleryBridge,
        status: StatusBridge,
        update: UpdateBridge,
        system: SystemBridge,
        buttons: ButtonBridge,
        autofocus: AutofocusBridge,
        bookmarks: BookmarkBridge,
        measurement: MeasurementBridge,
        automation: AutomationBridge,
        calibration: CalibrationBridge,
        settings: SettingsBridge,
        obj_detector: ObjectiveDetectorBridge,
        camera_svc: CameraService,
        measurement_capture_svc: MeasurementCaptureService,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._motion       = motion
        self._objective    = objective
        self._overlay      = overlay
        self._gallery      = gallery
        self._status       = status
        self._update       = update
        self._system       = system
        self._buttons      = buttons
        self._autofocus    = autofocus
        self._bookmarks    = bookmarks
        self._measurement   = measurement
        self._automation    = automation
        self._calibration   = calibration
        self._settings      = settings
        self._obj_detector  = obj_detector
        self._camera_svc    = camera_svc
        self._measurement_capture_svc = measurement_capture_svc
        self._camera_fps: float = float(settings.cameraFps)
        self._camera_resolution = settings.cameraResolution
        self._camera_resolution_options: list[str] = []
        self._camera_fps_options: list[int] = []
        self._shutdown_done = False
        self._direct_camera_bridge = DirectCameraBridge(
            camera_svc,
            enabled=True,
            parent=self,
        )
        camera_svc.set_recording_backend(self._direct_camera_bridge)
        camera_svc.set_native_capture_backend(self._direct_camera_bridge)
        self._direct_camera_bridge.configureCamera(
            settings.cameraDevice,
            settings.cameraResolution,
            settings.cameraFps,
        )
        camera_svc.set_frame_analysis_enabled(settings.cameraFrameAnalysisEnabled)
        self._direct_camera_bridge.setFrameAnalysisEnabled(settings.cameraFrameAnalysisEnabled)
        self._direct_camera_bridge.setLiveVideoEnabled(settings.cameraLiveVideoEnabled)
        settings.camera_device_changed.connect(self._direct_camera_bridge.setCameraDevice)
        settings.camera_resolution_changed.connect(self._direct_camera_bridge.setCameraResolution)
        settings.camera_fps_changed.connect(self._direct_camera_bridge.setCameraFps)
        settings.camera_frame_analysis_changed.connect(camera_svc.set_frame_analysis_enabled)
        settings.camera_frame_analysis_changed.connect(
            self._direct_camera_bridge.setFrameAnalysisEnabled
        )
        settings.camera_live_video_changed.connect(
            self._direct_camera_bridge.setLiveVideoEnabled
        )
        self._direct_camera_bridge.camera_format_changed.connect(
            self._on_direct_camera_format_changed
        )
        self._direct_camera_bridge.camera_capabilities_changed.connect(
            self._on_direct_camera_capabilities_changed
        )

        self._capture_busy = False

        camera_svc.frame_available.connect(self.frameAvailable)
        camera_svc.snapshot_saved.connect(self.snapshot_saved)
        camera_svc.snapshot_failed.connect(self.snapshot_failed)
        camera_svc.capture_busy_changed.connect(self._on_capture_busy_changed)
        camera_svc.recording_saved.connect(self.recording_saved)
        camera_svc.histogram_updated.connect(self.histogram_updated)
        camera_svc.focus_score_updated.connect(self.focus_score_updated)
        camera_svc.focus_source_updated.connect(self.focus_source_updated)
        camera_svc.recording_changed.connect(self.recording_changed)

    def _on_direct_camera_format_changed(self) -> None:
        resolution = self._direct_camera_bridge.activeResolution
        fps = self._direct_camera_bridge.activeFps
        if resolution:
            self._camera_resolution = resolution
            self.camera_resolution_changed.emit(resolution)
        if fps > 0:
            self._camera_fps = fps
            self.fps_updated.emit(fps)

    def _on_direct_camera_capabilities_changed(self) -> None:
        self._camera_resolution_options = list(self._direct_camera_bridge.availableResolutions)
        self._camera_fps_options = [int(v) for v in self._direct_camera_bridge.availableFps]
        self.camera_capabilities_changed.emit()

    # Properties
    @Property(QObject, constant=True)
    def automation(self) -> AutomationBridge:
        return self._automation

    @Property(QObject, constant=True)
    def calibration(self) -> CalibrationBridge:
        return self._calibration

    @Property(QObject, constant=True)
    def settings(self) -> SettingsBridge:
        return self._settings

    @Property(QObject, constant=True)
    def motion(self) -> MotionBridge:
        return self._motion

    @Property(QObject, constant=True)
    def objective(self) -> ObjectiveBridge:
        return self._objective

    @Property(QObject, constant=True)
    def overlay(self) -> OverlayBridge:
        return self._overlay

    @Property(QObject, constant=True)
    def status(self) -> StatusBridge:
        return self._status

    @Property(QObject, constant=True)
    def gallery(self) -> GalleryBridge:
        return self._gallery

    @Property(QObject, constant=True)
    def update(self) -> UpdateBridge:
        return self._update

    @Property(QObject, constant=True)
    def system(self) -> SystemBridge:
        return self._system

    @Property(QObject, constant=True)
    def buttons(self) -> ButtonBridge:
        return self._buttons

    @Property(QObject, constant=True)
    def autofocus(self) -> AutofocusBridge:
        return self._autofocus

    @Property(QObject, constant=True)
    def objDetector(self) -> ObjectiveDetectorBridge:
        return self._obj_detector

    @Property(QObject, constant=True)
    def bookmarks(self) -> BookmarkBridge:
        return self._bookmarks

    @Property(QObject, constant=True)
    def measurement(self) -> MeasurementBridge:
        return self._measurement

    @Property(bool, constant=True)
    def isMockMode(self) -> bool:
        return not is_pi()

    @Property(QObject, constant=True)
    def cameraFrameTap(self) -> DirectCameraBridge:
        return self._direct_camera_bridge

    @Property(bool, notify=recording_changed)
    def isRecording(self) -> bool:
        return self._camera_svc.is_recording()

    @Property(bool, notify=capture_busy_changed)
    def captureBusy(self) -> bool:
        return self._capture_busy

    def _on_capture_busy_changed(self, busy: bool) -> None:
        if busy == self._capture_busy:
            return
        self._capture_busy = busy
        self.capture_busy_changed.emit(busy)

    @Property(float, notify=fps_updated)
    def cameraFps(self) -> float:
        return self._camera_fps

    @Property(str, notify=camera_resolution_changed)
    def cameraResolution(self) -> str:
        return self._camera_resolution

    @Property(list, notify=camera_capabilities_changed)
    def cameraResolutionOptions(self) -> list[str]:
        return self._camera_resolution_options

    @Property(list, notify=camera_capabilities_changed)
    def cameraFpsOptions(self) -> list[int]:
        return self._camera_fps_options

    # Slots called from QML
    @Slot()
    def takeSnapshot(self) -> None:
        self._camera_svc.capture_snapshot()

    @Slot()
    def toggleRecording(self) -> None:
        if self._camera_svc.is_recording():
            self._camera_svc.stop_recording()
        else:
            self._camera_svc.start_recording()

    @Slot()
    def shutdown(self) -> None:
        if self._shutdown_done:
            return
        self._shutdown_done = True
        if self._camera_svc.is_recording():
            self._camera_svc.stop_recording()
        self._direct_camera_bridge.stop()
        self._camera_svc.shutdown()

    @Slot("QVariant", result=str)
    def saveMeasurementImage(self, image: object) -> str:
        """Save a grabbed QML measurement image as OME-TIFF."""
        return self._measurement_capture_svc.save_qimage(
            image,
            objective=self._objective.activeObjective,
            position=(self._motion.posX, self._motion.posY, self._motion.posZ),
        )
