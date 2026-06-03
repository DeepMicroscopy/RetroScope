"""Measurement bridge: Exposes measurement state and helpers to QML."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import Property, QObject, Signal, Slot

from retroscope.domain import measurement


class MeasurementBridge(QObject):
    """Expose measurement state and pure helpers to QML."""

    measurementsChanged = Signal()
    pendingPointsChanged = Signal()
    selectedIdChanged = Signal(int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._session = measurement.MeasurementSession()

    @Property(list, notify=measurementsChanged)
    def measurements(self) -> list[dict[str, Any]]:
        return self._session.measurements

    @Property(list, notify=pendingPointsChanged)
    def pendingPoints(self) -> list[dict[str, float]]:
        return self._session.pending_points

    @Property(int, notify=selectedIdChanged)
    def selectedId(self) -> int:
        return self._session.selected_id

    @Slot()
    def clearMeasurements(self) -> None:
        self._session.clear()
        self.measurementsChanged.emit()
        self.pendingPointsChanged.emit()
        self.selectedIdChanged.emit(self._session.selected_id)

    @Slot()
    def resetPending(self) -> None:
        if self._session.reset_pending():
            self.pendingPointsChanged.emit()

    @Slot(int)
    def selectMeasurement(self, measurement_id: int) -> None:
        if self._session.select(measurement_id):
            self.selectedIdChanged.emit(self._session.selected_id)

    @Slot(int)
    def deleteMeasurement(self, measurement_id: int) -> None:
        measurements_changed, selected_changed = self._session.delete(measurement_id)
        if measurements_changed:
            self.measurementsChanged.emit()
        if selected_changed:
            self.selectedIdChanged.emit(self._session.selected_id)

    @Slot(str, float, float, result=bool)
    def handleClick(self, active_tool: str, x: float, y: float) -> bool:
        measurements_changed, pending_changed = self._session.handle_click(active_tool, x, y)
        if measurements_changed:
            self.measurementsChanged.emit()
        if pending_changed:
            self.pendingPointsChanged.emit()
        return measurements_changed

    @Slot(str, result=str)
    def colorForType(self, measurement_type: str) -> str:
        return measurement.color_for_type(measurement_type)

    @Slot(str, result=str)
    def toolType(self, active_tool: str) -> str:
        return measurement.tool_type(active_tool)

    @Slot(str, result=int)
    def pointsRequired(self, measurement_type: str) -> int:
        return measurement.points_required(measurement_type)

    @Slot("QVariant", "QVariant", result=float)
    def distancePx(self, p1: object, p2: object) -> float:
        return measurement.distance_px(p1, p2)

    @Slot("QVariant", "QVariant", float, result=float)
    def distanceUm(self, p1: object, p2: object, um_per_pixel: float) -> float:
        return measurement.distance_um(p1, p2, um_per_pixel)

    @Slot("QVariant", "QVariant", "QVariant", result=float)
    def angleDeg(self, p1: object, vertex: object, p2: object) -> float:
        return measurement.angle_deg(p1, vertex, p2)

    @Slot(float, str, float, result=str)
    def formatLength(self, um: float, unit: str, um_per_pixel: float) -> str:
        return measurement.format_length(um, unit, um_per_pixel)

    @Slot(float, str, float, result=str)
    def formatArea(self, um2: float, unit: str, um_per_pixel: float) -> str:
        return measurement.format_area(um2, unit, um_per_pixel)

    @Slot("QVariant", str, float, result=str)
    def formatValue(self, item: object, unit: str, um_per_pixel: float) -> str:
        return measurement.format_value(self._mapping(item), unit, um_per_pixel)

    @Slot("QVariant", result=str)
    def formatSub(self, item: object) -> str:
        return measurement.format_sub(self._mapping(item))

    @Slot("QVariant", str, float, result=str)
    def formatAux(self, item: object, unit: str, um_per_pixel: float) -> str:
        return measurement.format_aux(self._mapping(item), unit, um_per_pixel)

    @Slot(int, str, "QVariant", str, result="QVariant")
    def createMeasurement(
        self,
        measurement_id: int,
        measurement_type: str,
        points: object,
        label: str,
    ) -> dict[str, Any]:
        return measurement.create_measurement(
            measurement_id,
            measurement_type,
            self._sequence(points),
            label,
        )

    @Slot("QVariant", float, float, float, result=int)
    def nearestMeasurementId(
        self,
        measurements: object,
        x: float,
        y: float,
        hit_radius: float = 20.0,
    ) -> int:
        return measurement.nearest_measurement_id(
            [self._mapping(item) for item in self._sequence(measurements)],
            {"x": x, "y": y},
            hit_radius,
        )

    @staticmethod
    def _mapping(value: object) -> Mapping[str, Any]:
        if hasattr(value, "toVariant"):
            value = value.toVariant()
        return value if isinstance(value, Mapping) else {}

    @staticmethod
    def _sequence(value: object) -> list[Any]:
        if hasattr(value, "toVariant"):
            value = value.toVariant()
        return list(value) if isinstance(value, (list, tuple)) else []
