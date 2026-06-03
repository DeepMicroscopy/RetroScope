"""Test the objective calibration logic."""

from retroscope.domain import objective_calibration
from retroscope.services.objective_manager import ObjectiveManager, parse_magnification


class MemoryConfig:
    def __init__(self):
        self.data = {}

    def get(self, key, default=None):
        node = self.data
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, key, value):
        node = self.data
        parts = key.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value


def _manager() -> ObjectiveManager:
    return ObjectiveManager(MemoryConfig())


def test_missing_axis_backlash_defaults_to_zero():
    cfg = MemoryConfig()
    cfg.data = {
        "objectives": {
            "4x": {
                "backlash_z": 7,
            }
        }
    }

    mgr = ObjectiveManager(cfg)

    assert mgr.profile("4x").backlash_x == 0
    assert mgr.profile("4x").backlash_y == 0
    assert mgr.profile("4x").backlash_z == 7


def test_normalized_distance_uses_image_dimensions():
    distance = objective_calibration.normalized_distance_px(1000, 500, 0.1, 0.2, 0.4, 0.6)
    assert round(distance, 6) == 360.555128


def test_um_per_pixel_requires_positive_values():
    assert objective_calibration.um_per_pixel(250, 100) == 2.5
    assert objective_calibration.um_per_pixel(0, 100) == 0
    assert objective_calibration.um_per_pixel(250, 0) == 0


def test_dof_steps_handles_unset_marks():
    unset = objective_calibration.DOF_UNSET_Z
    assert objective_calibration.dof_steps_between(120, 80) == 40
    assert objective_calibration.dof_steps_between(unset, 80) == 0
    assert objective_calibration.dof_steps_between(120, unset) == 0


def test_focus_stack_suggestion_and_backlash_clamping():
    assert objective_calibration.suggested_focus_stack_step(9) == 5
    assert objective_calibration.suggested_focus_stack_step(0) == 1
    assert objective_calibration.adjusted_backlash_steps(10, -20) == 0
    assert objective_calibration.adjusted_backlash_steps(145, 10) == 150


def test_parse_magnification_from_display_name_with_fallback():
    assert parse_magnification("4x") == 4
    assert parse_magnification("Plan 20x") == 20
    assert parse_magnification("100x Oil") == 100
    assert parse_magnification("Plan Apo", "40x") == 40


def test_scaled_um_per_pixel_updates_all_objectives_from_active_measurement():
    mgr = _manager()
    mgr.set_display_name("4x", "Plan 4x")
    mgr.set_display_name("100x", "63x oil")

    mgr.apply_scaled_um_per_pixel("4x", 2.0)

    assert mgr.profile("4x").um_per_pixel == 2.0
    assert mgr.profile("10x").um_per_pixel == 0.8
    assert mgr.profile("20x").um_per_pixel == 0.4
    assert round(mgr.profile("100x").um_per_pixel, 6) == round(2.0 * 4 / 63, 6)


def test_dof_scaling_uses_numerical_aperture_and_derives_focus_parameters():
    mgr = _manager()

    mgr.apply_scaled_dof_steps("4x", 100)

    assert mgr.profile("4x").dof_steps == 100
    assert mgr.profile("4x").focus_stack_step == 50
    assert mgr.profile("4x").autofocus_range_steps == 1000
    assert mgr.profile("10x").dof_steps == 16
    assert mgr.profile("10x").focus_stack_step == 8
    assert mgr.profile("10x").autofocus_range_steps == 200
    assert mgr.profile("100x").dof_steps == 1
    assert mgr.profile("100x").focus_stack_step == 1
    assert mgr.profile("100x").autofocus_range_steps == 200


def test_focus_stack_ratio_can_be_tuned_once_and_applied_to_all_profiles():
    mgr = _manager()
    mgr.apply_scaled_dof_steps("4x", 100)

    mgr.apply_scaled_focus_stack_step("4x", 25)

    assert mgr.profile("4x").focus_stack_step == 25
    assert mgr.profile("10x").focus_stack_step == 4
    assert mgr.profile("20x").focus_stack_step == 2
    assert mgr.profile("100x").focus_stack_step == 1


def test_backlash_calibration_is_applied_to_all_profiles():
    mgr = _manager()

    # Per-axis writes propagate to every objective independently.
    mgr.apply_backlash_axis_to_all("x", 12)
    mgr.apply_backlash_axis_to_all("y", 18)
    mgr.apply_backlash_axis_to_all("z", 7)

    for name in ("4x", "10x", "20x", "40x", "100x"):
        profile = mgr.profile(name)
        assert profile.backlash_x == 12
        assert profile.backlash_y == 18
        assert profile.backlash_z == 7
