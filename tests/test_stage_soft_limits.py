"""Tests for stage soft limit behavior in MotionController and TileScannerWorker.

Note: Partially AI-generated
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication

from retroscope.drivers.sangaboard import MockSangaboard
from retroscope.services.motion_controller import MotionController, _joystick_curve
from retroscope.services.tile_scanner import _TileScannerWorker


class FakeConfig:
    def __init__(self, soft_limits: dict | None = None) -> None:
        self._data = {
            "motor": {
                "soft_limits": {
                    "enabled": False,
                    "calibrated": False,
                    "x_min": 0,
                    "x_max": 0,
                    "y_min": 0,
                    "y_max": 0,
                    **(soft_limits or {}),
                }
            }
        }
        self.save_count = 0

    def get(self, key: str, default=None):
        node = self._data
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, key: str, value) -> None:
        node = self._data
        parts = key.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value

    def save(self) -> None:
        self.save_count += 1


class FakeObjectiveManager:
    active_objective = "10x"

    def current_profile(self):
        return SimpleNamespace(
            backlash_x=0,
            backlash_y=0,
            backlash_z=0,
            um_per_pixel=1.0,
            focus_stack_step=10,
        )


class FakeSangaboard:
    def __init__(self) -> None:
        self.moves: list[tuple[int, int, int]] = []
        self.blocking_moves: list[tuple[int, int, int, float | None]] = []
        self.zeroed = False
        self.stopped = False
        self.released = False

    def move_rel(self, dx: int, dy: int, dz: int, coalesce: bool = False) -> None:
        self.moves.append((dx, dy, dz))

    def move_rel_blocking(self, dx: int, dy: int, dz: int, timeout: float | None = None) -> bool:
        self.blocking_moves.append((dx, dy, dz, timeout))
        return True

    def zero_position(self) -> None:
        self.zeroed = True

    def stop_motors(self) -> None:
        self.stopped = True

    def release_motors(self) -> None:
        self.released = True


class FakeLimitMotion:
    def __init__(self, x_max: int) -> None:
        self.x_max = x_max
        self.blocked: list[str] = []

    def can_move_to_xy(self, x: int, y: int, source: str = "manual", emit_block: bool = True) -> bool:
        del y, emit_block
        if x <= self.x_max:
            return True
        self.blocked.append(source)
        return False


class FakeTileCamera:
    def __init__(self, recording: bool = False) -> None:
        self._recording = recording
        self.started = 0
        self.stopped = 0
        self.captures = 0

    def is_recording(self) -> bool:
        return self._recording

    def start_recording(self) -> None:
        self.started += 1
        self._recording = True

    def stop_recording(self) -> None:
        self.stopped += 1
        self._recording = False

    def get_latest_frame(self):
        self.captures += 1
        return None


class FakeCaptureTileCamera(FakeTileCamera):
    def __init__(self) -> None:
        super().__init__()
        self.frames = [
            np.full((24, 32, 3), value, dtype=np.uint8)
            for value in (10, 20)
        ]

    def capture_native_frame(self, should_cancel=None, allow_tap_fallback: bool = False):
        del should_cancel, allow_tap_fallback
        self.captures += 1
        return self.frames[min(self.captures - 1, len(self.frames) - 1)]


class FakeTileMotion:
    def __init__(self) -> None:
        self.moves: list[tuple[int, int, int, str]] = []
        self.blocking_moves: list[tuple[int, int, int, str]] = []

    def can_move_to_xy(self, x: int, y: int, source: str = "manual", emit_block: bool = True) -> bool:
        del x, y, source, emit_block
        return True

    def move_rel(self, dx: int, dy: int, dz: int, source: str = "manual") -> bool:
        self.moves.append((dx, dy, dz, source))
        return True

    def move_rel_blocking(self, dx: int, dy: int, dz: int, source: str = "manual") -> bool:
        self.blocking_moves.append((dx, dy, dz, source))
        return True


def _app() -> QCoreApplication:
    return QCoreApplication.instance() or QCoreApplication([])


def _controller(config: FakeConfig | None = None) -> tuple[MotionController, FakeSangaboard]:
    _app()
    sb = FakeSangaboard()
    ctrl = MotionController(sb, FakeObjectiveManager(), config or FakeConfig())
    return ctrl, sb


def test_mock_sangaboard_zero_position_resets_position() -> None:
    _app()
    mock = MockSangaboard()
    mock.move_rel(10, 20, 30)
    mock._pos = [7, 8, 9]
    mock._target = [10, 20, 30]

    mock.zero_position()

    assert mock._pos == [0, 0, 0]
    assert mock._target == [0, 0, 0]


def test_home_zero_requires_endstop_and_resets_soft_limit_state() -> None:
    cfg = FakeConfig({"enabled": True, "calibrated": True, "x_max": 100, "y_max": 100})
    ctrl, sb = _controller(cfg)
    blocked: list[str] = []
    resets: list[tuple[int, int, int]] = []
    ctrl.motion_blocked.connect(blocked.append)
    ctrl.position_reset.connect(lambda x, y, z: resets.append((x, y, z)))
    ctrl.on_position_updated(50, 60, 70)

    assert ctrl.confirm_home_zero() is False
    assert blocked[-1] == "stage_home_requires_endstop"
    assert sb.zeroed is False

    ctrl.on_endstop_triggered(True)

    assert ctrl.confirm_home_zero() is True
    assert sb.zeroed is True
    assert resets[-1] == (0, 0, 0)
    assert ctrl.soft_limits_enabled is False
    assert ctrl.soft_limits_calibrated is False
    assert cfg.get("motor.soft_limits.enabled") is False
    assert cfg.save_count >= 1


def test_bottom_right_limit_normalizes_and_persists() -> None:
    cfg = FakeConfig()
    ctrl, _ = _controller(cfg)
    ctrl.on_position_updated(-500, 300, 0)

    assert ctrl.save_bottom_right_limit() is True

    assert ctrl.soft_limits_enabled is True
    assert ctrl.soft_limits_calibrated is True
    assert (ctrl.soft_limit_x_min, ctrl.soft_limit_x_max) == (-500, 0)
    assert (ctrl.soft_limit_y_min, ctrl.soft_limit_y_max) == (0, 300)
    assert cfg.get("motor.soft_limits.x_min") == -500
    assert cfg.get("motor.soft_limits.y_max") == 300


def test_motion_controller_blocks_out_of_range_move() -> None:
    cfg = FakeConfig({"enabled": True, "calibrated": True, "x_min": 0, "x_max": 100, "y_min": 0, "y_max": 100})
    ctrl, sb = _controller(cfg)
    blocked: list[str] = []
    ctrl.motion_blocked.connect(blocked.append)
    ctrl.on_position_updated(50, 50, 0)

    assert ctrl.move_rel(20, 0, 0) is True
    assert sb.moves[-1] == (20, 0, 0)
    assert ctrl.move_rel(40, 0, 0) is False

    assert sb.moves == [(20, 0, 0)]
    assert blocked[-1] == "soft_limit_stage"


def test_blocking_z_move_uses_blocking_driver_without_touching_live_queue() -> None:
    ctrl, sb = _controller()

    assert ctrl.move_z_blocking(123) is True

    assert sb.moves == []
    assert len(sb.blocking_moves) == 1
    dx, dy, dz, timeout = sb.blocking_moves[0]
    assert (dx, dy, dz) == (0, 0, 123)
    assert timeout is not None and timeout >= 5.0


def test_normal_z_move_stays_fire_and_forget() -> None:
    ctrl, sb = _controller()

    assert ctrl.move_z(123) is True

    assert sb.moves == [(0, 0, 123)]
    assert sb.blocking_moves == []


def test_deenergize_motors_releases_hold_and_clears_intent() -> None:
    ctrl, sb = _controller()
    ctrl._vx_filtered = 0.5
    ctrl._vy_filtered = -0.5
    ctrl._dx_accum = 1.2
    ctrl._dy_accum = -2.4
    ctrl._encoder_accum = 75

    ctrl.deenergize_motors()

    assert sb.released is True
    assert ctrl._vx_filtered == 0.0
    assert ctrl._vy_filtered == 0.0
    assert ctrl._dx_accum == 0.0
    assert ctrl._dy_accum == 0.0
    assert ctrl._encoder_accum == 0


def test_joystick_move_is_blocked_at_soft_limit() -> None:
    cfg = FakeConfig({"enabled": True, "calibrated": True, "x_min": 0, "x_max": 100, "y_min": 0, "y_max": 100})
    cfg.set("motor.stage_um_per_step_x", 0.001)
    cfg.set("motor.stage_um_per_step_y", 0.001)
    ctrl, sb = _controller(cfg)
    blocked: list[str] = []
    ctrl.motion_blocked.connect(blocked.append)
    ctrl.on_position_updated(99, 50, 0)
    ctrl._center_x = 0
    ctrl._center_y = 0

    ctrl.on_axes_updated(32767, 0)
    ctrl._dispatch_joystick_at(time.monotonic())

    assert sb.moves == []
    assert blocked[-1] == "soft_limit_stage"


def test_joystick_curve_modes_are_distinct() -> None:
    linear = _joystick_curve(0.5, deadzone=0.0, curve="linear", expo_strength=70)
    expo = _joystick_curve(0.5, deadzone=0.0, curve="exponential", expo_strength=70)
    scurve = _joystick_curve(0.25, deadzone=0.0, curve="scurve", expo_strength=70)

    assert linear == 0.5
    assert expo < linear
    assert scurve == pytest.approx(0.15625)


def test_tile_scan_preflight_rejects_out_of_range_scan() -> None:
    _app()
    motion = FakeLimitMotion(x_max=100)
    worker = _TileScannerWorker(
        camera_svc=None,
        motion_ctrl=motion,
        autofocus_svc=None,
        image_store=None,
        objective_mgr=FakeObjectiveManager(),
        get_position=lambda: (0, 0, 0),
        cols=2,
        rows=1,
        overlap=0.2,
        pattern="serpentine",
        autofocus_each=False,
        record_video=False,
    )

    assert worker._preflight_soft_limits([(0, 0), (1, 0)], step_x=200, step_y=100) is False
    assert motion.blocked == ["automation"]


def test_still_tile_scan_uses_blocking_moves_before_settle_and_capture(tmp_path) -> None:
    _app()
    camera = FakeCaptureTileCamera()
    motion = FakeTileMotion()
    events: list[str] = []
    worker = _TileScannerWorker(
        camera_svc=camera,
        motion_ctrl=motion,
        autofocus_svc=SimpleNamespace(busy=False),
        image_store=SimpleNamespace(new_image_path=lambda *args, **kwargs: tmp_path / "scan.ome.tiff"),
        objective_mgr=FakeObjectiveManager(),
        get_position=lambda: (0, 0, 0),
        cols=2,
        rows=1,
        overlap=0.2,
        pattern="raster",
        autofocus_each=False,
        record_video=False,
    )
    worker._stitch_tiles = lambda tiles: tiles[0]["frame"]
    worker._save_scan = lambda tiles: "saved"
    worker._move_rel_blocking = lambda dx, dy, dz: events.append(f"blocking:{dx},{dy},{dz}") or True
    worker._capture_frame = lambda: events.append("capture") or camera.capture_native_frame()

    worker.run()

    assert events == ["capture", "blocking:1024,0,0", "capture", "blocking:-1024,0,0"]
    assert motion.moves == []
    assert motion.blocking_moves == []


def test_tile_scan_blocking_helper_prefers_motion_blocking_api() -> None:
    _app()
    motion = FakeTileMotion()
    worker = _TileScannerWorker(
        camera_svc=FakeTileCamera(),
        motion_ctrl=motion,
        autofocus_svc=None,
        image_store=None,
        objective_mgr=FakeObjectiveManager(),
        get_position=lambda: (0, 0, 0),
        cols=1,
        rows=1,
        overlap=0.2,
        pattern="raster",
        autofocus_each=False,
        record_video=False,
    )

    assert worker._move_rel_blocking(12, 34, 0) is True
    assert motion.blocking_moves == [(12, 34, 0, "automation")]
    assert motion.moves == []


def test_tile_scan_uses_configured_calibration_size_not_latest_frame() -> None:
    _app()

    class ConfiguredObjectiveManager(FakeObjectiveManager):
        _config = SimpleNamespace(
            get=lambda key, default=None: {
                "camera.resolution": "640x360",
                "motor.stage_um_per_step_x": 2.0,
                "motor.stage_um_per_step_y": 3.0,
            }.get(key, default)
        )

    class FrameSizeCamera(FakeTileCamera):
        def get_latest_frame(self):
            return np.zeros((111, 222, 3), dtype=np.uint8)

    worker = _TileScannerWorker(
        camera_svc=FrameSizeCamera(),
        motion_ctrl=FakeTileMotion(),
        autofocus_svc=None,
        image_store=None,
        objective_mgr=ConfiguredObjectiveManager(),
        get_position=lambda: (0, 0, 0),
        cols=2,
        rows=2,
        overlap=0.5,
        pattern="raster",
        autofocus_each=False,
        record_video=False,
    )

    assert worker._calibration_frame_size_px() == (640, 360)


def test_tile_scan_mosaic_mode_uses_full_tile_grid_without_stitch() -> None:
    _app()
    worker = _TileScannerWorker(
        camera_svc=FakeTileCamera(),
        motion_ctrl=FakeTileMotion(),
        autofocus_svc=None,
        image_store=None,
        objective_mgr=FakeObjectiveManager(),
        get_position=lambda: (1, 2, 3),
        cols=2,
        rows=1,
        overlap=0.2,
        pattern="raster",
        autofocus_each=False,
        record_video=False,
        stitch_after=False,
    )
    worker._try_stitch_tiles = lambda _tiles: (_ for _ in ()).throw(AssertionError("stitch must not run"))
    tiles = [
        {"col": 0, "row": 0, "frame": np.full((2, 3, 3), 10, dtype=np.uint8)},
        {"col": 1, "row": 0, "frame": np.full((2, 3, 3), 20, dtype=np.uint8)},
    ]

    rendered, actual_mode = worker._render_scan_result(tiles)
    metadata = worker._scan_metadata(
        rendered,
        len(tiles),
        requested_mode=worker._requested_output_mode(),
        actual_mode=actual_mode,
    )

    assert actual_mode == "mosaic"
    assert rendered.shape == (2, 6, 3)
    assert np.all(rendered[:, :3] == 10)
    assert np.all(rendered[:, 3:] == 20)
    assert metadata["output"] == {"requested": "mosaic", "actual": "mosaic"}

def test_video_tile_scan_records_only_and_uses_continuous_row_moves() -> None:
    _app()
    camera = FakeTileCamera()
    motion = FakeTileMotion()
    worker = _TileScannerWorker(
        camera_svc=camera,
        motion_ctrl=motion,
        autofocus_svc=SimpleNamespace(start_autofocus=lambda: (_ for _ in ()).throw(AssertionError("no autofocus"))),
        image_store=SimpleNamespace(new_image_path=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no scan save"))),
        objective_mgr=FakeObjectiveManager(),
        get_position=lambda: (0, 0, 0),
        cols=3,
        rows=2,
        overlap=0.2,
        pattern="serpentine",
        autofocus_each=True,
        record_video=True,
        stitch_after=True,
    )
    worker.run()

    assert camera.started == 1
    assert camera.stopped == 1
    assert camera.captures == 0
    assert motion.blocking_moves == [
        (2048, 0, 0, "automation"),
        (0, 576, 0, "automation"),
        (-2048, 0, 0, "automation"),
    ]
