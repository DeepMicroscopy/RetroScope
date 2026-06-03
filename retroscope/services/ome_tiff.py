"""OME-TIFF read/write helpers for microscope image captures.

Note: Partially AI-generated (_build_ome_xml, _as_uint8_rgb)
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import numpy as np
from PIL import Image, TiffImagePlugin

OME_NS = "http://www.openmicroscopy.org/Schemas/OME/2016-06"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
SCHEMA_LOCATION = f"{OME_NS} {OME_NS}/ome.xsd"
METADATA_TAG = "MicroscopeMetadata"
OME_EXTS = {".ome.tif", ".ome.tiff"}

ET.register_namespace("", OME_NS)
ET.register_namespace("xsi", XSI_NS)


@dataclass
class OmePlane:
    data: np.ndarray
    z: int = 0
    t: int = 0
    c: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OmeSeries:
    name: str
    kind: str
    planes: list[OmePlane]
    size_z: int = 1
    size_t: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


def is_ome_tiff(path: Path) -> bool:
    name = path.name.lower()
    return name.endswith(".ome.tif") or name.endswith(".ome.tiff")


def encode_ome_path(path: str | Path) -> str:
    raw = str(Path(path).expanduser().resolve()).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_ome_path(token: str) -> Path:
    padding = "=" * (-len(token) % 4)
    raw = base64.urlsafe_b64decode((token + padding).encode("ascii"))
    return Path(raw.decode("utf-8"))


def ome_image_url(path: str | Path, ifd: int = 0, mtime: float | None = None) -> str:
    token = encode_ome_path(path)
    stamp = int(mtime or Path(path).stat().st_mtime)
    return f"image://ome/{token}/{int(ifd)}?v={stamp}"


def write_snapshot(path: Path, frame: np.ndarray, metadata: dict[str, Any]) -> None:
    h, w = frame.shape[:2]
    md = {
        **metadata,
        "type": "snapshot",
        "width": int(w),
        "height": int(h),
        "format": "OME-TIFF",
    }
    write_ome_tiff(
        path,
        [
            OmeSeries(
                name=path.stem,
                kind="snapshot",
                planes=[OmePlane(_as_uint8_rgb(frame))],
                metadata=md,
            )
        ],
        md,
    )


def write_focus_stack(
    path: Path,
    blended: np.ndarray,
    frames: list[np.ndarray],
    metadata: dict[str, Any],
    z_positions: list[int],
) -> None:
    h, w = blended.shape[:2]
    md = {
        **metadata,
        "type": "stack",
        "width": int(w),
        "height": int(h),
        "format": "OME-TIFF",
        "frames": len(frames),
    }
    raw_planes = [
        OmePlane(
            _as_uint8_rgb(frame),
            z=i,
            metadata={
                "index": i,
                "z_offset": int(z_positions[i]) if i < len(z_positions) else i,
            },
        )
        for i, frame in enumerate(frames)
    ]
    write_ome_tiff(
        path,
        [
            OmeSeries(
                name=f"{path.stem} blended",
                kind="stack_result",
                planes=[OmePlane(_as_uint8_rgb(blended))],
                metadata={**md, "role": "blended"},
            ),
            OmeSeries(
                name=f"{path.stem} source planes",
                kind="stack_frames",
                planes=raw_planes,
                size_z=max(1, len(raw_planes)),
                metadata={**md, "role": "source_frames"},
            ),
        ],
        md,
    )


def write_tile_scan(
    path: Path,
    stitched: np.ndarray,
    tiles: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> None:
    h, w = stitched.shape[:2]
    md = {
        **metadata,
        "type": "stitch",
        "width": int(w),
        "height": int(h),
        "format": "OME-TIFF",
        "tiles": len(tiles),
    }
    raw_planes = []
    for i, tile in enumerate(tiles):
        raw_planes.append(
            OmePlane(
                _as_uint8_rgb(tile["frame"]),
                t=i,
                metadata={
                    "index": i,
                    "col": int(tile.get("col", 0)),
                    "row": int(tile.get("row", 0)),
                    "position": tile.get("position", {}),
                },
            )
        )
    write_ome_tiff(
        path,
        [
            OmeSeries(
                name=f"{path.stem} stitched",
                kind="stitch_result",
                planes=[OmePlane(_as_uint8_rgb(stitched))],
                metadata={**md, "role": "stitched"},
            ),
            OmeSeries(
                name=f"{path.stem} source tiles",
                kind="tile_frames",
                planes=raw_planes,
                size_t=max(1, len(raw_planes)),
                metadata={**md, "role": "source_tiles"},
            ),
        ],
        md,
    )


def write_ome_tiff(path: Path, series: list[OmeSeries], metadata: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pages: list[np.ndarray] = []
    ifd = 0
    for s in series:
        s.metadata["ifd_start"] = ifd
        s.metadata["ifd_count"] = len(s.planes)
        for plane in s.planes:
            pages.append(_as_uint8_rgb(plane.data))
            plane.metadata["ifd"] = ifd
            ifd += 1
    ome_xml = _build_ome_xml(series, metadata)
    try:
        _write_with_tifffile(path, pages, ome_xml)
    except Exception:
        _write_with_pillow(path, pages, ome_xml)


def read_metadata(path: Path) -> dict[str, Any]:
    xml = read_ome_xml(path)
    if not xml:
        return {}
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return {}

    ns = {"ome": OME_NS}
    md: dict[str, Any] = {}
    for elem in root.findall(".//ome:" + METADATA_TAG, ns):
        if elem.text:
            try:
                payload = json.loads(elem.text)
                if isinstance(payload, dict):
                    md.update(payload)
            except json.JSONDecodeError:
                pass

    series = []
    for image_index, image in enumerate(root.findall("ome:Image", ns)):
        pixels = image.find("ome:Pixels", ns)
        if pixels is None:
            continue
        px = pixels.attrib
        tiff_data = pixels.findall("ome:TiffData", ns)
        planes = pixels.findall("ome:Plane", ns)
        ifds = [_to_int(td.attrib.get("IFD"), 0) for td in tiff_data]
        image_md = _series_metadata(image, ns)
        series.append(
            {
                "index": image_index,
                "name": image.attrib.get("Name", ""),
                "kind": image_md.get("kind", ""),
                "width": _to_int(px.get("SizeX"), 0),
                "height": _to_int(px.get("SizeY"), 0),
                "size_z": _to_int(px.get("SizeZ"), 1),
                "size_t": _to_int(px.get("SizeT"), 1),
                "size_c": _to_int(px.get("SizeC"), 3),
                "ifds": ifds,
                "planes": [_plane_metadata(p) for p in planes],
                "metadata": image_md,
            }
        )
    md["ome_series"] = series
    if series:
        md.setdefault("width", series[0].get("width", 0))
        md.setdefault("height", series[0].get("height", 0))
    return md


def read_ome_xml(path: Path) -> str:
    try:
        import tifffile

        with tifffile.TiffFile(str(path)) as tif:
            return str(tif.pages[0].description or "")
    except Exception:
        pass
    try:
        with Image.open(path) as img:
            raw = img.tag_v2.get(270)
            if isinstance(raw, tuple):
                raw = raw[0] if raw else ""
            return str(raw or "")
    except Exception:
        return ""


def read_plane(path: Path, ifd: int = 0) -> np.ndarray | None:
    try:
        import tifffile

        with tifffile.TiffFile(str(path)) as tif:
            if ifd < 0 or ifd >= len(tif.pages):
                return None
            return _as_uint8_rgb(tif.pages[ifd].asarray())
    except Exception:
        pass
    try:
        with Image.open(path) as img:
            img.seek(max(0, int(ifd)))
            return _as_uint8_rgb(np.asarray(img.convert("RGB")))
    except Exception:
        return None


def _build_ome_xml(series: list[OmeSeries], metadata: dict[str, Any]) -> str:
    ome = ET.Element(
        f"{{{OME_NS}}}OME",
        {
            "Creator": "RetroScope",
            f"{{{XSI_NS}}}schemaLocation": SCHEMA_LOCATION,
        },
    )
    annotations = ET.SubElement(ome, f"{{{OME_NS}}}StructuredAnnotations")
    ann = ET.SubElement(annotations, f"{{{OME_NS}}}XMLAnnotation", {"ID": "Annotation:0"})
    value = ET.SubElement(ann, f"{{{OME_NS}}}Value")
    payload = ET.SubElement(value, f"{{{OME_NS}}}{METADATA_TAG}")
    payload.text = json.dumps(_jsonable(metadata), separators=(",", ":"))

    for image_index, s in enumerate(series):
        image = ET.SubElement(
            ome,
            f"{{{OME_NS}}}Image",
            {"ID": f"Image:{image_index}", "Name": s.name},
        )
        ET.SubElement(image, f"{{{OME_NS}}}AnnotationRef", {"ID": "Annotation:0"})
        series_ann = ET.SubElement(
            image,
            f"{{{OME_NS}}}Description",
        )
        series_ann.text = json.dumps(
            _jsonable({"kind": s.kind, **s.metadata}),
            separators=(",", ":"),
        )
        first = s.planes[0].data
        height, width = first.shape[:2]
        pixels = ET.SubElement(
            image,
            f"{{{OME_NS}}}Pixels",
            {
                "ID": f"Pixels:{image_index}",
                "DimensionOrder": "XYZTC",
                "Type": "uint8",
                "SignificantBits": "8",
                "BigEndian": "false",
                "Interleaved": "true",
                "SizeX": str(int(width)),
                "SizeY": str(int(height)),
                "SizeZ": str(max(1, int(s.size_z))),
                "SizeC": "3",
                "SizeT": str(max(1, int(s.size_t))),
            },
        )
        ET.SubElement(
            pixels,
            f"{{{OME_NS}}}Channel",
            {
                "ID": f"Channel:{image_index}:0",
                "Name": "RGB",
                "SamplesPerPixel": "3",
            },
        )
        for plane in s.planes:
            ifd = int(plane.metadata.get("ifd", 0))
            ET.SubElement(
                pixels,
                f"{{{OME_NS}}}TiffData",
                {
                    "IFD": str(ifd),
                    "FirstZ": str(int(plane.z)),
                    "FirstT": str(int(plane.t)),
                    "FirstC": str(int(plane.c)),
                    "PlaneCount": "1",
                },
            )
            plane_attrs = {
                "TheZ": str(int(plane.z)),
                "TheT": str(int(plane.t)),
                "TheC": str(int(plane.c)),
            }
            position = plane.metadata.get("position")
            if isinstance(position, dict):
                if position.get("x") is not None:
                    plane_attrs["PositionX"] = str(position.get("x"))
                if position.get("y") is not None:
                    plane_attrs["PositionY"] = str(position.get("y"))
                if position.get("z") is not None:
                    plane_attrs["PositionZ"] = str(position.get("z"))
            ET.SubElement(pixels, f"{{{OME_NS}}}Plane", plane_attrs)

    body = ET.tostring(ome, encoding="unicode")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!-- Warning: this comment is an OME-XML metadata block. -->\n"
        + body
    )


def _write_with_tifffile(path: Path, pages: list[np.ndarray], ome_xml: str) -> None:
    import tifffile

    size = sum(int(p.nbytes) for p in pages)
    with tifffile.TiffWriter(str(path), bigtiff=size > 3_800_000_000) as tif:
        for i, page in enumerate(pages):
            tif.write(
                page,
                photometric="rgb",
                planarconfig="contig",
                description=ome_xml if i == 0 else None,
                metadata=None,
            )


def _write_with_pillow(path: Path, pages: list[np.ndarray], ome_xml: str) -> None:
    if not pages:
        raise ValueError("OME-TIFF requires at least one image plane")
    images = [Image.fromarray(_as_uint8_rgb(page), mode="RGB") for page in pages]
    tiffinfo = TiffImagePlugin.ImageFileDirectory_v2()
    tiffinfo[270] = ome_xml
    images[0].save(
        path,
        format="TIFF",
        save_all=True,
        append_images=images[1:],
        compression="raw",
        tiffinfo=tiffinfo,
    )


def _series_metadata(image: ET.Element, ns: dict[str, str]) -> dict[str, Any]:
    desc = image.find("ome:Description", ns)
    if desc is None or not desc.text:
        return {}
    try:
        payload = json.loads(desc.text)
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        return {}


def _plane_metadata(plane: ET.Element) -> dict[str, Any]:
    return {
        "z": _to_int(plane.attrib.get("TheZ"), 0),
        "t": _to_int(plane.attrib.get("TheT"), 0),
        "c": _to_int(plane.attrib.get("TheC"), 0),
        "position": {
            "x": _maybe_int(plane.attrib.get("PositionX")),
            "y": _maybe_int(plane.attrib.get("PositionY")),
            "z": _maybe_int(plane.attrib.get("PositionZ")),
        },
    }


def _as_uint8_rgb(frame: np.ndarray) -> np.ndarray:
    arr = np.asarray(frame)
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    if arr.ndim == 2:
        arr = np.stack([arr, arr, arr], axis=2)
    if arr.ndim == 3 and arr.shape[2] == 4:
        arr = arr[:, :, :3]
    if arr.ndim != 3 or arr.shape[2] != 3:
        raise ValueError(f"expected RGB image plane, got shape {arr.shape}")
    return np.ascontiguousarray(arr)


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _maybe_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None
