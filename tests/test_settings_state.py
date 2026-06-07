"""Test SettingsBridge interactions with configuration."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication


def _app() -> QCoreApplication:
    return QCoreApplication.instance() or QCoreApplication([])


class ConfigStub:
    def __init__(self, values=None):
        self.values = values or {}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


class StoreStub:
    def __init__(self, root):
        self._root = root

    def capture_root(self):
        return self._root

    def total_count(self):
        return 0


class StorageStatsStub:
    def __init__(self, disk_used=0, disk_total=1, capture_count=0):
        self.disk_used = disk_used
        self.disk_total = disk_total
        self.capture_count = capture_count


class StorageServiceStub:
    def __init__(self, root, count=0):
        self._root = root
        self.count = count
        self.cleared = False

    def capture_root(self):
        return self._root

    def set_capture_root(self, value):
        expanded = type(self._root)(value).expanduser()
        if expanded == self._root:
            return None
        self._root = expanded
        return str(expanded)

    def refresh_stats(self):
        return StorageStatsStub(
            disk_used=12_345,
            disk_total=98_765,
            capture_count=self.count,
        )

    def clear_all_captures(self):
        self.cleared = True
        self.count = 0
        return self.refresh_stats()


def test_settings_bridge_camera_performance_toggles_persist(tmp_path):
    from retroscope.bridge.settings_bridge import SettingsBridge

    config = ConfigStub()
    bridge = SettingsBridge(config, StoreStub(tmp_path))
    analysis_seen: list[bool] = []
    video_seen: list[bool] = []
    bridge.camera_frame_analysis_changed.connect(analysis_seen.append)
    bridge.camera_live_video_changed.connect(video_seen.append)

    bridge.setCameraFrameAnalysisEnabled(False)
    bridge.setCameraLiveVideoEnabled(False)

    assert bridge.cameraFrameAnalysisEnabled is False
    assert bridge.cameraLiveVideoEnabled is False
    assert config.values["camera.frame_analysis_enabled"] is False
    assert config.values["camera.live_video_enabled"] is False
    assert analysis_seen == [False]
    assert video_seen == [False]


def test_settings_bridge_storage_uses_storage_service_stats(tmp_path):
    from retroscope.bridge.settings_bridge import SettingsBridge

    config = ConfigStub()
    storage = StorageServiceStub(tmp_path / "captures", count=5)
    bridge = SettingsBridge(config, storage)
    roots_seen: list[str] = []
    bridge.capture_root_changed.connect(roots_seen.append)

    assert bridge.captureCount == 5

    storage.count = 7
    bridge.refreshStorage()
    assert bridge.captureCount == 7

    new_root = tmp_path / "new-captures"
    bridge.setCaptureRoot(str(new_root))

    assert bridge.captureRoot == str(new_root)
    assert roots_seen == [str(new_root)]

    bridge.clearAllCaptures()

    assert storage.cleared
    assert bridge.captureCount == 0


def test_settings_bridge_joystick_backlash_compensation_persists_and_emits(tmp_path):
    from retroscope.bridge.settings_bridge import SettingsBridge

    config = ConfigStub()
    bridge = SettingsBridge(config, StoreStub(tmp_path))
    seen: list[bool] = []
    bridge.joystick_backlash_compensation_changed.connect(seen.append)

    assert bridge.joystickBacklashCompensationEnabled is True

    bridge.setJoystickBacklashCompensationEnabled(False)

    assert bridge.joystickBacklashCompensationEnabled is False
    assert config.values["input.joystick_backlash_compensation_enabled"] is False
    assert seen == [False]


def test_settings_bridge_joystick_backlash_signal_can_drive_motion_controller(tmp_path):
    from types import SimpleNamespace

    from retroscope.bridge.settings_bridge import SettingsBridge
    from retroscope.services.motion_controller import MotionController

    class Sangaboard:
        def move_rel(self, dx: int, dy: int, dz: int, coalesce: bool = False) -> None:
            pass

    class ObjectiveManager:
        def current_profile(self):
            return SimpleNamespace(
                backlash_x=0,
                backlash_y=0,
                backlash_z=0,
                um_per_pixel=1.0,
                focus_stack_step=10,
            )

    config = ConfigStub()
    bridge = SettingsBridge(config, StoreStub(tmp_path))
    ctrl = MotionController(Sangaboard(), ObjectiveManager(), config)
    bridge.joystick_backlash_compensation_changed.connect(
        ctrl.setJoystickBacklashCompensationEnabled
    )

    bridge.setJoystickBacklashCompensationEnabled(False)

    assert ctrl._joystick_backlash_compensation_enabled is False


def test_settings_bridge_sangaboard_timing_uses_reported_values_until_user_override(tmp_path):
    from retroscope.bridge.settings_bridge import SettingsBridge

    config = ConfigStub()
    bridge = SettingsBridge(config, StoreStub(tmp_path))
    step_requests: list[int] = []
    ramp_requests: list[int] = []
    bridge.sangaboard_step_time_set_requested.connect(step_requests.append)
    bridge.sangaboard_ramp_time_set_requested.connect(ramp_requests.append)

    bridge.onSangaboardTimingUpdated(750, 25000)
    assert bridge.sangaboardStepTimeUs == 750
    assert bridge.sangaboardRampTimeUs == 25000
    assert "motor.sangaboard_step_time_us" not in config.values

    bridge.applySangaboardTimingOverrides()
    assert step_requests == []
    assert ramp_requests == []

    bridge.setSangaboardStepTimeUs(1234)
    assert bridge.sangaboardStepTimeUs == 1250
    assert config.values["motor.sangaboard_step_time_us"] == 1250
    assert step_requests == [1250]

    bridge.onSangaboardTimingUpdated(700, 30000)
    assert bridge.sangaboardStepTimeUs == 700
    assert bridge.sangaboardRampTimeUs == 30000

    bridge.applySangaboardTimingOverrides()
    assert step_requests == [1250, 1250]


def _real_settings_bridge(tmp_path, monkeypatch):
    _app()
    import retroscope.services.config_store as config_store
    from retroscope.bridge.settings_bridge import SettingsBridge
    from retroscope.services.config_store import ConfigStore
    from retroscope.services.image_store import ImageStore

    monkeypatch.setattr(config_store, "_CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_store, "_CONFIG_FILE", tmp_path / "config.json")
    cfg = ConfigStore(autosave_delay_ms=0)
    cfg.load()
    return SettingsBridge(cfg, ImageStore(cfg))


def _real_settings_context(tmp_path, monkeypatch):
    _app()
    import retroscope.services.config_store as config_store
    from retroscope.bridge.settings_bridge import SettingsBridge
    from retroscope.services.config_store import ConfigStore
    from retroscope.services.image_store import ImageStore
    from retroscope.services.objective_manager import ObjectiveManager

    monkeypatch.setattr(config_store, "_CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_store, "_CONFIG_FILE", tmp_path / "config.json")
    cfg = ConfigStore(autosave_delay_ms=0)
    cfg.load()
    objectives = ObjectiveManager(cfg)
    bridge = SettingsBridge(cfg, ImageStore(cfg))
    return cfg, objectives, bridge


def test_settings_bridge_autofocus_speed_preset_balanced_sets_defaults(tmp_path, monkeypatch) -> None:
    bridge = _real_settings_bridge(tmp_path, monkeypatch)

    bridge.setAutofocusSpeedPreset("fast")
    assert bridge.autofocusSettleMs == 1000
    assert bridge.autofocusMoveStartMs == 400
    assert bridge.autofocusCoarsePositions == 11
    assert bridge.autofocusFinePositions == 13
    assert bridge.autofocusSamplesPerPosition == 1

    bridge.setAutofocusSpeedPreset("slow")
    assert bridge.autofocusSettleMs == 1000
    assert bridge.autofocusFinePositions == 31

    bridge.setAutofocusSettleMs(1000)
    bridge.setAutofocusSpeedPreset("custom")
    assert bridge.autofocusSettleMs == 1000


def test_settings_bridge_autofocus_coarse_positions_force_odd(tmp_path, monkeypatch) -> None:
    bridge = _real_settings_bridge(tmp_path, monkeypatch)

    bridge.setAutofocusCoarsePositions(14)
    assert bridge.autofocusCoarsePositions == 15

    bridge.setAutofocusCoarsePositions(40)
    assert bridge.autofocusCoarsePositions == 41


def test_settings_bridge_autofocus_fine_positions_force_odd(tmp_path, monkeypatch) -> None:
    bridge = _real_settings_bridge(tmp_path, monkeypatch)

    bridge.setAutofocusFinePositions(12)
    assert bridge.autofocusFinePositions == 13

    bridge.setAutofocusFinePositions(40)
    assert bridge.autofocusFinePositions == 41


def test_settings_bridge_reset_defaults_resets_full_config_and_live_state(tmp_path, monkeypatch) -> None:
    cfg, objectives, bridge = _real_settings_context(tmp_path, monkeypatch)
    defaults = cfg._load_defaults()
    deadzone_seen: list[int] = []
    analysis_seen: list[bool] = []
    bridge.joystick_deadzone_changed.connect(deadzone_seen.append)
    bridge.camera_frame_analysis_changed.connect(analysis_seen.append)

    objectives.set_param("4x", "backlash_x", 999)
    objectives.set_active("100x")
    bridge.setJoystickDeadzonePct(44)
    bridge.setCameraFrameAnalysisEnabled(False)
    bridge.setJoystickBacklashCompensationEnabled(False)

    bridge.resetToDefaults()

    assert cfg.get("objectives.4x.backlash_x") == defaults["objectives"]["4x"]["backlash_x"]
    assert cfg.get("ui.active_objective") == defaults["ui"]["active_objective"]
    assert cfg.get("input.deadzone_pct") == defaults["input"]["deadzone_pct"]
    assert (
        cfg.get("input.joystick_backlash_compensation_enabled")
        is defaults["input"]["joystick_backlash_compensation_enabled"]
    )
    assert bridge.joystickDeadzonePct == defaults["input"]["deadzone_pct"]
    assert (
        bridge.joystickBacklashCompensationEnabled
        is defaults["input"]["joystick_backlash_compensation_enabled"]
    )
    assert bridge.cameraFrameAnalysisEnabled is defaults["camera"]["frame_analysis_enabled"]
    assert objectives.active_objective == defaults["ui"]["active_objective"]
    assert objectives.profile("4x").backlash_x == defaults["objectives"]["4x"]["backlash_x"]
    assert deadzone_seen[-1] == defaults["input"]["deadzone_pct"]
    assert analysis_seen[-1] is defaults["camera"]["frame_analysis_enabled"]
