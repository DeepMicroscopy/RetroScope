"""Gallery image/video storage helpers and metadata persistence.

Note: Partially AI-generated (_build_item, _ensure_video_thumbnail, _ensure_video_playback_proxy)
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from retroscope.services import ome_tiff

DEFAULT_CAPTURE_ROOT = Path.home() / "retroscope" / "captures"
META_KEY = "microscope_metadata"
SUPPORTED_TYPES = {"snapshot", "video", "stack", "stitch"}
VIDEO_EXTS = {".avi", ".mp4", ".mov", ".mkv", ".m4v"}
THUMBNAIL_DIR = ".thumbnails"
THUMBNAIL_MAX_WIDTH = 640
# Grid/list previews never need more than a few hundred px; keep image thumbnails
# small so huge stitched scans don't get decoded at full resolution to draw a cell.
IMAGE_THUMBNAIL_MAX_WIDTH = 480
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


class ConfigLike(Protocol):
    def get(self, key: str, default: Any = None) -> Any: ...


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or value.strip() == "":
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class ImageStore:
    """Persists and reads capture metadata from media files (+ sidecars)."""

    def __init__(self, config: ConfigLike) -> None:
        self._config = config
        # Incremental scan cache: resolved path -> (mtime, size, built item).
        # Lets scan_items() skip metadata/thumbnail work for unchanged files.
        self._item_cache: dict[str, tuple[float, int, dict[str, Any]]] = {}
        self._cache_lock = threading.RLock()

    # Paths
    def capture_root(self) -> Path:
        raw = self._config.get("captures.root", "")
        if isinstance(raw, str) and raw.strip() != "":
            return Path(raw).expanduser()
        return DEFAULT_CAPTURE_ROOT

    def snapshot_dir(self) -> Path:
        return self.capture_root() / "snapshots"

    def video_dir(self) -> Path:
        return self.capture_root() / "videos"

    def stacks_dir(self) -> Path:
        return self.capture_root() / "stacks"

    def scans_dir(self) -> Path:
        return self.capture_root() / "scans"

    def ensure_directories(self) -> None:
        self.snapshot_dir().mkdir(parents=True, exist_ok=True)
        self.video_dir().mkdir(parents=True, exist_ok=True)
        self.stacks_dir().mkdir(parents=True, exist_ok=True)
        self.scans_dir().mkdir(parents=True, exist_ok=True)
        self.thumbnail_dir().mkdir(parents=True, exist_ok=True)

    def new_image_path(
        self,
        kind: str,
        prefix: str,
        *,
        objective: str = "",
        extension: str = ".ome.tiff",
        captured_at: datetime | None = None,
    ) -> Path:
        now = captured_at or datetime.now()
        if kind == "stack":
            out_dir = self.stacks_dir()
        elif kind == "stitch":
            out_dir = self.scans_dir()
        elif kind == "video":
            out_dir = self.video_dir()
        else:
            out_dir = self.snapshot_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        return self._patterned_path(out_dir, prefix, objective, extension, now)

    def _patterned_path(
        self,
        out_dir: Path,
        media_type: str,
        objective: str,
        extension: str,
        captured_at: datetime,
    ) -> Path:
        ext = extension if extension.startswith(".") else f".{extension}"
        pattern = str(self._config.get("camera.naming_pattern", "{date}_{time}_{obj}") or "").strip()
        if pattern == "":
            pattern = "{date}_{time}_{obj}"
        if "{type}" not in pattern:
            pattern = f"{pattern}_{{type}}"

        for seq in range(1, 10000):
            name = self._render_pattern(pattern, media_type, objective, captured_at, seq)
            candidate = out_dir / f"{name}{ext}"
            if not candidate.exists():
                return candidate
            if "{seq}" not in pattern:
                candidate = out_dir / f"{name}_{seq + 1:03d}{ext}"
                if not candidate.exists():
                    return candidate
        fallback = captured_at.strftime("%Y%m%d_%H%M%S_%f")[:22]
        return out_dir / f"{media_type}_{fallback}{ext}"

    def _render_pattern(
        self,
        pattern: str,
        media_type: str,
        objective: str,
        captured_at: datetime,
        seq: int,
    ) -> str:
        values = {
            "date": captured_at.strftime("%Y%m%d"),
            "time": captured_at.strftime("%H%M%S"),
            "obj": objective or "objective",
            "type": media_type,
            "seq": f"{seq:03d}",
        }
        name = pattern
        for key, value in values.items():
            name = name.replace("{" + key + "}", str(value))
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._-")
        name = re.sub(r"_+", "_", name)
        return name[:160] or media_type

    def thumbnail_dir(self) -> Path:
        return self.capture_root() / THUMBNAIL_DIR

    @staticmethod
    def sidecar_path(media_path: Path) -> Path:
        return Path(f"{media_path}.json")

    # Metadata
    def read_metadata(self, media_path: Path) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        if ome_tiff.is_ome_tiff(media_path):
            metadata.update(ome_tiff.read_metadata(media_path))
        sidecar = self._read_sidecar_metadata(media_path)
        if sidecar:
            metadata.update(sidecar)
        return metadata

    def write_metadata(self, media_path: Path, metadata: dict[str, Any]) -> bool:
        return self._write_sidecar_metadata(media_path, metadata)

    def _read_sidecar_metadata(self, media_path: Path) -> dict[str, Any]:
        sidecar = self.sidecar_path(media_path)
        if not sidecar.exists():
            return {}
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if isinstance(payload, dict) and isinstance(payload.get(META_KEY), dict):
            return payload[META_KEY]
        if isinstance(payload, dict):
            return payload
        return {}

    def _write_sidecar_metadata(self, media_path: Path, metadata: dict[str, Any]) -> bool:
        sidecar = self.sidecar_path(media_path)
        try:
            sidecar.write_text(
                json.dumps({META_KEY: metadata}, indent=2),
                encoding="utf-8",
            )
            return True
        except Exception:
            return False

    # Gallery item operations
    def scan_items(self) -> list[dict[str, Any]]:
        with self._cache_lock:
            self.ensure_directories()
            items: list[dict[str, Any]] = []
            seen: set[str] = set()
            for path in self._iter_capture_files():
                key = str(path.resolve())
                try:
                    stat = path.stat()
                except OSError:
                    continue
                seen.add(key)
                cached = self._item_cache.get(key)
                if cached is not None and cached[0] == stat.st_mtime and cached[1] == stat.st_size:
                    items.append(cached[2])
                    continue
                item = self._build_item(path)
                if item:
                    self._item_cache[key] = (stat.st_mtime, stat.st_size, item)
                    items.append(item)
            # Drop cache entries for files that disappeared.
            for stale in self._item_cache.keys() - seen:
                self._item_cache.pop(stale, None)
            return items

    def invalidate(self, media_path: Path) -> None:
        with self._cache_lock:
            self._item_cache.pop(str(media_path.resolve()), None)

    def persist_tags(self, media_path: Path, tags: list[str]) -> bool:
        with self._cache_lock:
            item = self._build_item(media_path)
            if item is None:
                return False
            md = item["metadata"]
            md["tags"] = tags
            ok = self.write_metadata(media_path, md)
            if ok:
                self.invalidate(media_path)
            return ok

    def total_count(self) -> int:
        """Return number of captured files (images + videos)."""
        return len(self._iter_capture_files())

    def clear_all(self) -> None:
        """Delete all captures, thumbnails..."""
        for p in list(self._iter_capture_files()):
            self.delete_item(p)

    def delete_item(self, media_path: Path) -> bool:
        ok = True
        try:
            media_path.unlink(missing_ok=True)
        except Exception:
            ok = False
        try:
            self.sidecar_path(media_path).unlink(missing_ok=True)
        except Exception:
            ok = False
        self._remove_thumbnails(media_path)
        self._remove_playback_proxies(media_path)
        self.invalidate(media_path)
        return ok

    # Internal helpers
    def _iter_capture_files(self) -> list[Path]:
        paths: list[Path] = []
        seen: set[Path] = set()
        for base in [self.snapshot_dir(), self.stacks_dir(), self.scans_dir(), self.video_dir()]:
            if not base.exists():
                continue
            try:
                entries = list(base.iterdir())
            except OSError:
                continue
            # Only scan base level and one nested level for performace.
            for entry in entries:
                candidates: list[Path] = []
                if entry.is_file():
                    candidates = [entry]
                elif entry.is_dir():
                    try:
                        candidates = [p for p in entry.iterdir() if p.is_file()]
                    except OSError:
                        continue
                for p in candidates:
                    if p.suffix.lower() == ".json":
                        continue
                    if not self._is_supported_capture_file(p):
                        continue
                    rp = p.resolve()
                    if rp in seen:
                        continue
                    seen.add(rp)
                    paths.append(p)
        return paths

    def _build_item(self, media_path: Path) -> dict[str, Any] | None:
        if not media_path.exists():
            return None
        try:
            stat = media_path.stat()
        except OSError:
            return None

        metadata = self.read_metadata(media_path)
        file_type = self._detect_type(media_path, metadata)
        captured = _parse_iso(metadata.get("captured_at"))
        if captured is None:
            captured = datetime.fromtimestamp(stat.st_mtime)

        width, height = self._resolve_dimensions(media_path, metadata)
        position = metadata.get("position", {})
        if not isinstance(position, dict):
            position = {}
        tags = metadata.get("tags", [])
        if not isinstance(tags, list):
            tags = []
        preview_path = str(media_path.resolve())
        playback_path = str(media_path.resolve())
        if file_type == "video":
            thumb = self._ensure_video_thumbnail(media_path, stat.st_mtime, stat.st_size)
            preview_path = str(thumb.resolve()) if thumb is not None else ""
            playback_proxy = self._ensure_video_playback_proxy(media_path, stat.st_mtime, stat.st_size)
            if playback_proxy is not None:
                playback_path = str(playback_proxy.resolve())
        else:
            thumb = self._ensure_image_thumbnail(
                media_path, stat.st_mtime, stat.st_size, ome_tiff.is_ome_tiff(media_path)
            )
            if thumb is not None:
                preview_path = str(thumb.resolve())
        frames, tiles = self._resolve_ome_plane_lists(metadata)

        return {
            "id": str(media_path.resolve()),
            "path": str(media_path.resolve()),
            "preview_path": preview_path,
            "playback_path": playback_path,
            "filename": media_path.name,
            "ext": media_path.suffix.lower(),
            "type": file_type,
            "captured_at": captured.isoformat(timespec="seconds"),
            "captured_ts": captured.timestamp(),
            "mtime_ts": stat.st_mtime,
            "objective": metadata.get("objective", ""),
            "width": width,
            "height": height,
            "file_size": stat.st_size,
            "format": str(metadata.get("format") or ("OME-TIFF" if ome_tiff.is_ome_tiff(media_path) else media_path.suffix.lstrip(".").upper())),
            "pos_x": _coerce_int(position.get("x")),
            "pos_y": _coerce_int(position.get("y")),
            "pos_z": _coerce_int(position.get("z")),
            "tags": [str(t).strip() for t in tags if str(t).strip() != ""],
            "metadata": metadata,
            "frames": frames,
            "tiles": tiles,
        }

    def _detect_type(self, media_path: Path, metadata: dict[str, Any]) -> str:
        md_type = str(metadata.get("type", "")).strip().lower()
        if md_type in SUPPORTED_TYPES:
            return md_type
        ext = media_path.suffix.lower()
        if ext in VIDEO_EXTS:
            return "video"
        if "stack" in media_path.name.lower():
            return "stack"
        if "pano" in media_path.name.lower() or "scan" in media_path.name.lower():
            return "stitch"
        return "snapshot"

    def _resolve_dimensions(self, media_path: Path, metadata: dict[str, Any]) -> tuple[int, int]:
        width = _coerce_int(metadata.get("width"))
        height = _coerce_int(metadata.get("height"))
        if width and height:
            return width, height

        series = metadata.get("ome_series")
        if isinstance(series, list) and series:
            first = series[0]
            if isinstance(first, dict):
                sw = _coerce_int(first.get("width"))
                sh = _coerce_int(first.get("height"))
                if sw and sh:
                    return sw, sh

        resolution = metadata.get("resolution")
        if isinstance(resolution, dict):
            rw = _coerce_int(resolution.get("width"))
            rh = _coerce_int(resolution.get("height"))
            if rw and rh:
                return rw, rh
        return 0, 0

    def _is_supported_capture_file(self, path: Path) -> bool:
        if ome_tiff.is_ome_tiff(path):
            return True
        return path.suffix.lower() in VIDEO_EXTS

    def _resolve_ome_plane_lists(
        self,
        metadata: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        series = metadata.get("ome_series")
        if not isinstance(series, list):
            return [], []

        frames: list[dict[str, Any]] = []
        tiles: list[dict[str, Any]] = []
        for s in series:
            if not isinstance(s, dict):
                continue
            kind = str(s.get("kind", "")).lower()
            ifds = s.get("ifds", [])
            if not isinstance(ifds, list):
                continue
            entries = [
                {
                    "series": int(s.get("index", 0) or 0),
                    "plane": i,
                    "ifd": _coerce_int(ifd) or 0,
                }
                for i, ifd in enumerate(ifds)
            ]
            if kind == "stack_frames":
                frames = entries
            elif kind == "tile_frames":
                tiles = entries
        return frames, tiles

    def _thumbnail_key(self, media_path: Path) -> str:
        return hashlib.sha1(str(media_path.resolve()).encode("utf-8")).hexdigest()[:12]

    def _thumbnail_path(self, media_path: Path, mtime: float, size: int) -> Path:
        key = self._thumbnail_key(media_path)
        stamp = int(mtime)
        return self.thumbnail_dir() / f"{media_path.stem}_{key}_{stamp}_{size}.jpg"

    def _thumbnail_fail_path(self, media_path: Path) -> Path:
        key = self._thumbnail_key(media_path)
        return self.thumbnail_dir() / f"{media_path.stem}_{key}.fail"

    def _remove_thumbnails(self, media_path: Path) -> None:
        thumb_dir = self.thumbnail_dir()
        if not thumb_dir.exists():
            return
        key = self._thumbnail_key(media_path)
        prefix = f"{media_path.stem}_{key}_"
        try:
            for p in thumb_dir.glob(f"{prefix}*.jpg"):
                p.unlink(missing_ok=True)
            self._thumbnail_fail_path(media_path).unlink(missing_ok=True)
        except Exception:
            return

    def _playback_proxy_path(self, media_path: Path, mtime: float, size: int) -> Path:
        key = self._thumbnail_key(media_path)
        stamp = int(mtime)
        return self.thumbnail_dir() / f"{media_path.stem}_{key}_{stamp}_{size}.mp4"

    def _playback_fail_path(self, media_path: Path) -> Path:
        key = self._thumbnail_key(media_path)
        return self.thumbnail_dir() / f"{media_path.stem}_{key}.playback.fail"

    def _remove_playback_proxies(self, media_path: Path) -> None:
        thumb_dir = self.thumbnail_dir()
        if not thumb_dir.exists():
            return
        key = self._thumbnail_key(media_path)
        prefix = f"{media_path.stem}_{key}_"
        try:
            for p in thumb_dir.glob(f"{prefix}*.mp4"):
                p.unlink(missing_ok=True)
            self._playback_fail_path(media_path).unlink(missing_ok=True)
        except Exception:
            return

    def _mark_playback_proxy_failure(self, media_path: Path) -> None:
        marker = self._playback_fail_path(media_path)
        try:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("failed\n", encoding="utf-8")
        except Exception:
            return

    def _mark_thumbnail_failure(self, media_path: Path) -> None:
        marker = self._thumbnail_fail_path(media_path)
        try:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("failed\n", encoding="utf-8")
        except Exception:
            return

    def _downscale_bgr(self, bgr, max_w: int):
        import cv2

        h, w = bgr.shape[:2]
        if w > max_w:
            nh = max(1, int(h * (max_w / float(w))))
            bgr = cv2.resize(bgr, (max_w, nh), interpolation=cv2.INTER_AREA)
        return bgr

    def _rgb_to_bgr(self, rgb):
        import cv2

        if rgb.ndim == 2:
            return cv2.cvtColor(rgb, cv2.COLOR_GRAY2BGR)
        if rgb.shape[2] == 4:
            return cv2.cvtColor(rgb, cv2.COLOR_RGBA2BGR)
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    def write_thumbnail_from_array(self, media_path: Path, rgb) -> Path | None:
        """Pre-generate the gallery thumbnail from an in-memory RGB array (e.g. a freshly stitched scan)."""
        try:
            import cv2

            stat = media_path.stat()
            thumb = self._thumbnail_path(media_path, stat.st_mtime, stat.st_size)
            bgr = self._downscale_bgr(self._rgb_to_bgr(rgb), IMAGE_THUMBNAIL_MAX_WIDTH)
            thumb.parent.mkdir(parents=True, exist_ok=True)
            if cv2.imwrite(str(thumb), bgr):
                self._thumbnail_fail_path(media_path).unlink(missing_ok=True)
                return thumb
        except Exception:
            return None
        return None

    def _ensure_image_thumbnail(
        self,
        media_path: Path,
        mtime: float,
        size: int,
        is_ome: bool,
    ) -> Path | None:
        thumb = self._thumbnail_path(media_path, mtime, size)
        if thumb.exists():
            return thumb

        fail_marker = self._thumbnail_fail_path(media_path)
        if fail_marker.exists():
            try:
                if fail_marker.stat().st_mtime >= mtime:
                    return None
            except OSError:
                pass

        self._remove_thumbnails(media_path)
        try:
            import cv2
        except Exception:
            self._mark_thumbnail_failure(media_path)
            return None

        try:
            if is_ome:
                rgb = ome_tiff.read_plane(media_path, 0)
                if rgb is None:
                    self._mark_thumbnail_failure(media_path)
                    return None
                bgr = self._rgb_to_bgr(rgb)
            else:
                bgr = cv2.imread(str(media_path), cv2.IMREAD_COLOR)
                if bgr is None:
                    self._mark_thumbnail_failure(media_path)
                    return None
            bgr = self._downscale_bgr(bgr, IMAGE_THUMBNAIL_MAX_WIDTH)
            thumb.parent.mkdir(parents=True, exist_ok=True)
            if cv2.imwrite(str(thumb), bgr):
                fail_marker.unlink(missing_ok=True)
                return thumb
        except Exception:
            self._mark_thumbnail_failure(media_path)
            return None
        self._mark_thumbnail_failure(media_path)
        return None

    def _ensure_video_thumbnail(
        self,
        media_path: Path,
        mtime: float,
        size: int,
    ) -> Path | None:
        thumb = self._thumbnail_path(media_path, mtime, size)
        if thumb.exists():
            return thumb

        fail_marker = self._thumbnail_fail_path(media_path)
        if fail_marker.exists():
            try:
                if fail_marker.stat().st_mtime >= mtime:
                    return None
            except OSError:
                pass

        self._remove_thumbnails(media_path)
        try:
            import cv2
        except Exception:
            self._mark_thumbnail_failure(media_path)
            return None

        cap = self._open_video_capture(cv2, media_path)

        if not cap.isOpened():
            cap.release()
            self._mark_thumbnail_failure(media_path)
            return None
        ok, frame = cap.read()
        cap.release()
        if not ok or frame is None:
            self._mark_thumbnail_failure(media_path)
            return None

        try:
            h, w = frame.shape[:2]
            if w > THUMBNAIL_MAX_WIDTH:
                nh = max(1, int(h * (THUMBNAIL_MAX_WIDTH / float(w))))
                frame = cv2.resize(frame, (THUMBNAIL_MAX_WIDTH, nh), interpolation=cv2.INTER_AREA)
            thumb.parent.mkdir(parents=True, exist_ok=True)
            if cv2.imwrite(str(thumb), frame):
                fail_marker.unlink(missing_ok=True)
                return thumb
        except Exception:
            self._mark_thumbnail_failure(media_path)
            return None
        self._mark_thumbnail_failure(media_path)
        return None

    def _open_video_capture(self, cv2, media_path: Path):
        """Open a video with CPU decoding to avoid failed hardware-accel setup warnings."""
        params: list[int] = []
        if hasattr(cv2, "CAP_PROP_HW_ACCELERATION") and hasattr(cv2, "VIDEO_ACCELERATION_NONE"):
            params = [
                int(cv2.CAP_PROP_HW_ACCELERATION),
                int(cv2.VIDEO_ACCELERATION_NONE),
            ]
        if params and hasattr(cv2, "CAP_FFMPEG"):
            try:
                cap = cv2.VideoCapture(str(media_path), cv2.CAP_FFMPEG, params)
                if cap.isOpened():
                    return cap
                cap.release()
            except Exception:
                pass
        return cv2.VideoCapture(str(media_path))

    def _video_codec_name(self, media_path: Path) -> str:
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return ""
        try:
            result = subprocess.run(
                [
                    ffprobe,
                    "-v", "error",
                    "-select_streams", "v:0",
                    "-show_entries", "stream=codec_name",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(media_path),
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=15,
            )
        except Exception:
            return ""
        if result.returncode != 0:
            return ""
        return result.stdout.strip().lower()

    def _needs_video_playback_proxy(self, media_path: Path) -> bool:
        if media_path.suffix.lower() != ".mp4":
            return True
        return self._video_codec_name(media_path) in {"mpeg4", "msmpeg4v1", "msmpeg4v2", "msmpeg4v3"}

    def _ensure_video_playback_proxy(
        self,
        media_path: Path,
        mtime: float,
        size: int,
    ) -> Path | None:
        if not self._needs_video_playback_proxy(media_path):
            return media_path

        proxy = self._playback_proxy_path(media_path, mtime, size)
        if proxy.exists():
            return proxy

        fail_marker = self._playback_fail_path(media_path)
        if fail_marker.exists():
            try:
                if fail_marker.stat().st_mtime >= mtime:
                    return media_path
            except OSError:
                pass

        self._remove_playback_proxies(media_path)

        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            self._mark_playback_proxy_failure(media_path)
            return media_path

        commands = [
            [
                ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-hwaccel", "none", "-i", str(media_path),
                "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", str(proxy),
            ],
            [
                ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-hwaccel", "none", "-i", str(media_path),
                "-an", "-c:v", "h264_videotoolbox", "-b:v", "4M", "-pix_fmt", "yuv420p", str(proxy),
            ],
        ]
        for cmd in commands:
            try:
                result = subprocess.run(
                    cmd,
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=120,
                )
            except Exception:
                continue

            if result.returncode == 0:
                try:
                    if proxy.exists() and proxy.stat().st_size > 0:
                        fail_marker.unlink(missing_ok=True)
                        return proxy
                except OSError:
                    pass

        try:
            proxy.unlink(missing_ok=True)
        except Exception:
            pass
        self._mark_playback_proxy_failure(media_path)
        return media_path
