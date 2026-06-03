"""Test the measurement domain logic."""

from retroscope.domain.measurement import (
    MeasurementSession,
    angle_deg,
    create_measurement,
    distance_px,
    distance_um,
    format_aux,
    format_sub,
    format_value,
    nearest_measurement_id,
    tool_type,
)


def test_distance_geometry_and_formatting():
    item = create_measurement(1, "distance", [{"x": 0, "y": 0}, {"x": 3, "y": 4}])

    assert distance_px(item["points"][0], item["points"][1]) == 5
    assert distance_um(item["points"][0], item["points"][1], 2.0) == 10
    assert format_value(item, "\u00b5m", 2.0) == "10.0 \u00b5m"
    assert format_value(item, "mm", 2.0) == "0.010 mm"
    assert format_value(item, "px", 2.0) == "5 px"
    assert format_sub(item) == "5 px"


def test_angle_and_rectangle_formatting():
    angle = create_measurement(
        2,
        "angle",
        [{"x": 1, "y": 0}, {"x": 0, "y": 0}, {"x": 0, "y": 1}],
    )
    rect = create_measurement(3, "rect", [{"x": 0, "y": 0}, {"x": 10, "y": 5}])

    assert angle_deg(angle["points"][0], angle["points"][1], angle["points"][2]) == 90
    assert format_value(angle, "\u00b5m", 1.0) == "90.0\u00b0"
    assert format_sub(angle) == "3 vertices"
    assert format_value(rect, "\u00b5m", 2.0) == "200 \u00b5m\u00b2"
    assert format_value(rect, "px", 2.0) == "50 px\u00b2"
    assert format_aux(rect, "\u00b5m", 2.0) == "W: 20.0 \u00b5m   H: 10.0 \u00b5m"


def test_tool_mapping_and_nearest_hit():
    distance = create_measurement(7, "distance", [{"x": 0, "y": 0}, {"x": 100, "y": 0}])
    rect = create_measurement(8, "rect", [{"x": 200, "y": 200}, {"x": 220, "y": 220}])

    assert tool_type("Rectangle area") == "rect"
    assert tool_type("unknown") == "distance"
    assert nearest_measurement_id([distance, rect], {"x": 50, "y": 3}) == 7
    assert nearest_measurement_id([distance, rect], {"x": 205, "y": 205}) == 8
    assert nearest_measurement_id([distance, rect], {"x": 400, "y": 400}) == -1


def test_measurement_session_creates_and_resets_pending_points():
    session = MeasurementSession()

    created, pending_changed = session.handle_click("Distance", 0, 0)
    assert not created
    assert pending_changed
    assert session.pending_points == [{"x": 0.0, "y": 0.0}]
    assert session.measurements == []

    created, pending_changed = session.handle_click("Distance", 3, 4)
    assert created
    assert pending_changed
    assert session.pending_points == []
    assert len(session.measurements) == 1
    assert session.measurements[0]["id"] == 1
    assert session.measurements[0]["type"] == "distance"

    assert not session.reset_pending()
    session.handle_click("Angle", 1, 0)
    assert session.reset_pending()
    assert session.pending_points == []


def test_measurement_session_selection_delete_and_clear():
    session = MeasurementSession()
    session.handle_click("Distance", 0, 0)
    session.handle_click("Distance", 10, 0)
    session.handle_click("Rectangle area", 20, 20)
    session.handle_click("Rectangle area", 30, 30)

    assert [item["id"] for item in session.measurements] == [1, 2]
    assert session.select(2)
    assert session.selected_id == 2
    assert not session.select(2)

    measurements_changed, selected_changed = session.delete(2)
    assert measurements_changed
    assert selected_changed
    assert session.selected_id == -1
    assert [item["id"] for item in session.measurements] == [1]

    session.clear()
    assert session.measurements == []
    assert session.pending_points == []
    assert session.selected_id == -1
