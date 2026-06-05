"""Test SettingsBridge interactions with configuration."""


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


def test_settings_bridge_joystick_smoothing_persists(tmp_path):
    from retroscope.bridge.settings_bridge import SettingsBridge

    config = ConfigStub()
    bridge = SettingsBridge(config, StoreStub(tmp_path))
    seen: list[int] = []
    bridge.joystick_smoothing_changed.connect(seen.append)

    bridge.setJoystickSmoothingPct(125)

    assert bridge.joystickSmoothingPct == 100
    assert config.values["input.joystick_smoothing_pct"] == 100
    assert seen == [100]


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
