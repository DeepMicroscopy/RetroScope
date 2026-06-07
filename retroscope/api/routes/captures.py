"""Gallery capture routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse

from retroscope.api.context import get_api_context
from retroscope.api.ids import capture_api_id_from_item
from retroscope.api.models import CaptureListResponse, CapturePosition, CaptureSummary

router = APIRouter()

_CAPTURE_TYPES = {"all", "snapshot", "video", "stack", "stitch"}
_SORT_ORDERS = {"newest", "oldest"}


@router.get("/captures", response_model=CaptureListResponse)
def list_captures(
    request: Request,
    capture_type: str = Query("all", alias="type"),
    sort: str = Query("newest"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> CaptureListResponse:
    if capture_type not in _CAPTURE_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported capture type")
    if sort not in _SORT_ORDERS:
        raise HTTPException(status_code=422, detail="Unsupported sort order")

    context = get_api_context(request)
    items = _filtered_sorted_items(context.image_store.scan_items(), capture_type, sort)
    total = len(items)
    page = items[offset:offset + limit]
    return CaptureListResponse(
        total=total,
        limit=limit,
        offset=offset,
        captures=[_to_capture_summary(request, item) for item in page],
    )


@router.get("/captures/{capture_id}/download", name="download_capture")
def download_capture(request: Request, capture_id: str) -> FileResponse:
    context = get_api_context(request)
    item = _find_capture(context.image_store.scan_items(), capture_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Capture not found")

    path = Path(str(item.get("path", "")))
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Capture file not found")

    return FileResponse(
        str(path),
        filename=path.name,
        media_type="application/octet-stream",
    )


def _filtered_sorted_items(
    raw_items: list[dict[str, Any]],
    capture_type: str,
    sort: str,
) -> list[dict[str, Any]]:
    items = [
        item for item in raw_items
        if capture_type == "all" or item.get("type") == capture_type
    ]
    items.sort(
        key=lambda item: (
            float(item.get("captured_ts", 0.0)),
            float(item.get("mtime_ts", 0.0)),
            str(item.get("filename", "")),
        ),
        reverse=sort == "newest",
    )
    return items


def _find_capture(items: list[dict[str, Any]], capture_id: str) -> dict[str, Any] | None:
    for item in items:
        if capture_api_id_from_item(item) == capture_id:
            return item
    return None


def _to_capture_summary(request: Request, item: dict[str, Any]) -> CaptureSummary:
    capture_id = capture_api_id_from_item(item)
    metadata = item.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    return CaptureSummary(
        id=capture_id,
        filename=str(item.get("filename", "")),
        type=str(item.get("type", "")),
        captured_at=str(item.get("captured_at", "")),
        objective=str(item.get("objective", "")),
        width=int(item.get("width", 0) or 0),
        height=int(item.get("height", 0) or 0),
        file_size=int(item.get("file_size", 0) or 0),
        format=str(item.get("format", "")),
        tags=[str(tag) for tag in item.get("tags", [])],
        position=CapturePosition(
            x=item.get("pos_x"),
            y=item.get("pos_y"),
            z=item.get("pos_z"),
        ),
        metadata=metadata,
        download_url=str(request.url_for("download_capture", capture_id=capture_id)),
    )
