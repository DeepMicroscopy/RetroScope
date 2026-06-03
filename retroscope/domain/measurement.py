"""Measurement geometry and formatting helpers."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

MEASUREMENT_COLORS = {
    "distance": "#5DCAA5",
    "angle": "#EF9F27",
    "rect": "#85B7EB",
}

TOOL_TYPES = {
    "Distance": "distance",
    "Angle": "angle",
    "Rectangle area": "rect",
}

POINTS_REQUIRED = {
    "distance": 2,
    "angle": 3,
    "rect": 2,
}

@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float


class MeasurementSession:
    """Mutable measurement-list state independent from Qt/QML."""

    def __init__(self) -> None:
        self.measurements: list[dict[str, Any]] = []
        self.pending_points: list[dict[str, float]] = []
        self.selected_id = -1
        self._next_id = 1

    def clear(self) -> None:
        self.measurements = []
        self.pending_points = []
        self.selected_id = -1
        self._next_id = 1

    def reset_pending(self) -> bool:
        if not self.pending_points:
            return False
        self.pending_points = []
        return True

    def select(self, measurement_id: int) -> bool:
        measurement_id = int(measurement_id)
        if measurement_id == self.selected_id:
            return False
        self.selected_id = measurement_id
        return True

    def delete(self, measurement_id: int) -> tuple[bool, bool]:
        measurement_id = int(measurement_id)
        next_measurements = [
            item for item in self.measurements
            if int(item.get("id", -1)) != measurement_id
        ]
        if len(next_measurements) == len(self.measurements):
            return False, False

        self.measurements = next_measurements
        selected_changed = self.selected_id == measurement_id
        if selected_changed:
            self.selected_id = -1
        return True, selected_changed

    def handle_click(self, active_tool: str, x: float, y: float) -> tuple[bool, bool]:
        measurement_type = tool_type(active_tool)
        self.pending_points = self.pending_points + [{"x": float(x), "y": float(y)}]

        if len(self.pending_points) != points_required(measurement_type):
            return False, True

        item = create_measurement(
            self._next_id,
            measurement_type,
            self.pending_points,
            "",
        )
        self._next_id += 1
        self.measurements = self.measurements + [item]
        self.pending_points = []
        return True, True


def point_from(value: Any) -> Point:
    """Convert a QML/Python point-like value into a typed point."""
    if hasattr(value, "toVariant"):
        value = value.toVariant()
    if isinstance(value, Point):
        return value
    if isinstance(value, Mapping):
        return Point(float(value.get("x", 0.0)), float(value.get("y", 0.0)))
    return Point(float(getattr(value, "x", 0.0)), float(getattr(value, "y", 0.0)))


def points_from(values: Iterable[Any]) -> list[Point]:
    return [point_from(value) for value in values]


def color_for_type(measurement_type: str) -> str:
    return MEASUREMENT_COLORS.get(measurement_type, "#888888")


def tool_type(active_tool: str) -> str:
    return TOOL_TYPES.get(active_tool, "distance")


def points_required(measurement_type: str) -> int:
    return POINTS_REQUIRED.get(measurement_type, 2)


def distance_px(p1: Any, p2: Any) -> float:
    first = point_from(p1)
    second = point_from(p2)
    return math.hypot(second.x - first.x, second.y - first.y)


def distance_um(p1: Any, p2: Any, um_per_pixel: float) -> float:
    return distance_px(p1, p2) * float(um_per_pixel)


def angle_deg(p1: Any, vertex: Any, p2: Any) -> float:
    first = point_from(p1)
    mid = point_from(vertex)
    second = point_from(p2)
    a1 = math.atan2(first.y - mid.y, first.x - mid.x)
    a2 = math.atan2(second.y - mid.y, second.x - mid.x)
    deg = abs(a1 - a2) * 180.0 / math.pi
    return 360.0 - deg if deg > 180.0 else deg


def rect_area_um2(p1: Any, p2: Any, um_per_pixel: float) -> float:
    first = point_from(p1)
    second = point_from(p2)
    width = abs(second.x - first.x) * float(um_per_pixel)
    height = abs(second.y - first.y) * float(um_per_pixel)
    return width * height


def format_length(um: float, unit: str, um_per_pixel: float) -> str:
    if unit == "mm":
        return f"{um / 1000:.3f} mm"
    if unit == "px":
        return f"{um / float(um_per_pixel):.0f} px"
    return f"{um:.1f} \u00b5m"


def format_area(um2: float, unit: str, um_per_pixel: float) -> str:
    if unit == "mm":
        return f"{um2 / 1e6:.4f} mm\u00b2"
    if unit == "px":
        px_area = um2 / (float(um_per_pixel) * float(um_per_pixel))
        return f"{px_area:.0f} px\u00b2"
    return f"{um2:.0f} \u00b5m\u00b2"


def format_value(measurement: Mapping[str, Any], unit: str, um_per_pixel: float) -> str:
    measurement_type = str(measurement.get("type", ""))
    points = list(measurement.get("points", []))
    if measurement_type == "distance" and len(points) >= 2:
        return format_length(distance_um(points[0], points[1], um_per_pixel), unit, um_per_pixel)
    if measurement_type == "angle" and len(points) >= 3:
        return f"{angle_deg(points[0], points[1], points[2]):.1f}\u00b0"
    if measurement_type == "rect" and len(points) >= 2:
        return format_area(rect_area_um2(points[0], points[1], um_per_pixel), unit, um_per_pixel)
    return ""


def format_sub(measurement: Mapping[str, Any]) -> str:
    measurement_type = str(measurement.get("type", ""))
    points = list(measurement.get("points", []))
    if measurement_type == "distance" and len(points) >= 2:
        return f"{distance_px(points[0], points[1]):.0f} px"
    if measurement_type == "angle":
        return "3 vertices"
    if measurement_type == "rect" and len(points) >= 2:
        p1 = point_from(points[0])
        p2 = point_from(points[1])
        return f"{abs(p2.x - p1.x):.0f}\u00d7{abs(p2.y - p1.y):.0f} px"
    return ""

def format_aux(measurement: Mapping[str, Any], unit: str, um_per_pixel: float) -> str:
    if str(measurement.get("type", "")) != "rect":
        return ""
    points = list(measurement.get("points", []))
    if len(points) < 2:
        return ""
    p1 = point_from(points[0])
    p2 = point_from(points[1])
    width_um = abs(p2.x - p1.x) * float(um_per_pixel)
    height_um = abs(p2.y - p1.y) * float(um_per_pixel)
    return f"W: {format_length(width_um, unit, um_per_pixel)}   H: {format_length(height_um, unit, um_per_pixel)}"

def create_measurement(
    measurement_id: int,
    measurement_type: str,
    points: Iterable[Any],
    label: str = "",
) -> dict[str, Any]:
    return {
        "id": int(measurement_id),
        "type": measurement_type,
        "points": [{"x": point.x, "y": point.y} for point in points_from(points)],
        "color": color_for_type(measurement_type),
        "label": label,
    }

def nearest_measurement_id(
    measurements: Iterable[Mapping[str, Any]],
    point: Any,
    hit_radius: float = 20.0,
) -> int:
    cursor = point_from(point)
    best_dist = float(hit_radius)
    best_id = -1

    for item in measurements:
        measurement_id = int(item.get("id", -1))
        points = points_from(item.get("points", []))
        for candidate in points:
            dist = distance_px(cursor, candidate)
            if dist < best_dist:
                best_dist = dist
                best_id = measurement_id

        if item.get("type") == "distance" and len(points) >= 2:
            midpoint = Point((points[0].x + points[1].x) / 2, (points[0].y + points[1].y) / 2)
            dist = distance_px(cursor, midpoint)
            if dist < best_dist:
                best_dist = dist
                best_id = measurement_id

    return best_id
