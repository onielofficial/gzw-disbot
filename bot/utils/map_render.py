"""Render a cropped Lamang map with orange objective markers.

Given a list of ``(x, y)`` pixel coordinates on the base map, this module
loads the base image, crops tightly around the points with padding, draws
orange markers on each, and returns a ``discord.File`` ready to attach.

The base image is resolved in this order:
  1. ``data_dir/maps/<map_slug>.{png,webp,jpg,jpeg}`` (any extension)
  2. Downloaded from ``MAP_BASE_IMAGE_URL`` to ``data_dir/maps/<map_slug>.png``

Pillow is imported lazily so the bot starts even when it isn't installed —
in that case ``render_task_map`` returns ``None`` and the cog skips the map.
"""
from __future__ import annotations

import asyncio
import io
import logging
from pathlib import Path
from typing import Optional, Sequence, Tuple

import aiohttp
import discord

logger = logging.getLogger(__name__)

DEFAULT_PAD_PX = 200
DEFAULT_MARKER_RADIUS = 14
_MARKER_OUTLINE_PX = 4
_MARKER_FILL = (255, 140, 0, 255)
_MARKER_OUTLINE = (255, 255, 255, 255)
_MARKER_SHADOW = (0, 0, 0, 160)

_BASE_MAP_EXTS = (".png", ".webp", ".jpg", ".jpeg")


def _try_import_pil():
    try:
        from PIL import Image, ImageDraw  # type: ignore
        return Image, ImageDraw
    except ImportError:
        logger.warning("Pillow not installed; map rendering disabled")
        return None, None


async def _download_base_map(url: str, dest: Path, *, user_agent: str) -> bool:
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(
            timeout=timeout, headers={"User-Agent": user_agent}
        ) as session:
            async with session.get(url) as resp:
                if resp.status >= 400:
                    logger.warning("base map %s returned HTTP %s", url, resp.status)
                    return False
                data = await resp.read()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return True
    except Exception as exc:
        logger.warning("base map download failed (%s): %s", url, exc)
        return False


async def resolve_base_map(
    data_dir: Path,
    map_slug: str,
    base_image_url: Optional[str],
    *,
    user_agent: str = "GZW-DisBot/1.0",
) -> Optional[Path]:
    maps_dir = data_dir / "maps"
    for ext in _BASE_MAP_EXTS:
        candidate = maps_dir / f"{map_slug}{ext}"
        if candidate.exists():
            return candidate
    if base_image_url:
        target = maps_dir / f"{map_slug}.png"
        if await _download_base_map(base_image_url, target, user_agent=user_agent):
            return target
    return None


def _crop_window(
    points: Sequence[Tuple[float, float]],
    width: int,
    height: int,
    pad: int,
) -> Tuple[int, int, int, int]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    left = int(min(xs)) - pad
    top = int(min(ys)) - pad
    right = int(max(xs)) + pad
    bottom = int(max(ys)) + pad

    # Guarantee a minimum window so a single objective doesn't render at 1px.
    min_window = pad * 2
    if right - left < min_window:
        cx = (left + right) // 2
        left = cx - pad
        right = cx + pad
    if bottom - top < min_window:
        cy = (top + bottom) // 2
        top = cy - pad
        bottom = cy + pad

    # Clamp into the source image.
    left = max(0, left)
    top = max(0, top)
    right = min(width, right)
    bottom = min(height, bottom)
    if right <= left:
        right = min(width, left + 1)
    if bottom <= top:
        bottom = min(height, top + 1)
    return left, top, right, bottom


def _render_sync(
    base_path: Path,
    points: Sequence[Tuple[float, float]],
    *,
    pad: int,
    marker_radius: int,
) -> Optional[bytes]:
    Image, ImageDraw = _try_import_pil()
    if Image is None:
        return None
    with Image.open(base_path) as raw:
        img = raw.convert("RGBA")
    width, height = img.size

    left, top, right, bottom = _crop_window(points, width, height, pad)
    crop = img.crop((left, top, right, bottom)).convert("RGBA")
    overlay = Image.new("RGBA", crop.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for x, y in points:
        cx = int(round(x)) - left
        cy = int(round(y)) - top
        shadow_r = marker_radius + 3
        outline_r = marker_radius + _MARKER_OUTLINE_PX
        draw.ellipse(
            (cx - shadow_r, cy - shadow_r, cx + shadow_r, cy + shadow_r),
            fill=_MARKER_SHADOW,
        )
        draw.ellipse(
            (cx - outline_r, cy - outline_r, cx + outline_r, cy + outline_r),
            fill=_MARKER_OUTLINE,
        )
        draw.ellipse(
            (cx - marker_radius, cy - marker_radius,
             cx + marker_radius, cy + marker_radius),
            fill=_MARKER_FILL,
        )

    composed = Image.alpha_composite(crop, overlay).convert("RGB")
    buf = io.BytesIO()
    composed.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


async def render_task_map(
    points: Sequence[Tuple[float, float]],
    *,
    data_dir: Path,
    map_slug: str,
    base_image_url: Optional[str] = None,
    user_agent: str = "GZW-DisBot/1.0",
    filename: str = "objectives.png",
    pad: int = DEFAULT_PAD_PX,
    marker_radius: int = DEFAULT_MARKER_RADIUS,
) -> Optional[discord.File]:
    """Build a cropped, marker-annotated map image.

    Returns ``None`` (so the caller can skip silently) when:
      - ``points`` is empty
      - Pillow is not installed
      - the base map can't be loaded or downloaded
      - rendering itself fails
    """
    pts = [
        (float(x), float(y))
        for x, y in points
        if x is not None and y is not None
    ]
    if not pts:
        return None

    base_path = await resolve_base_map(
        data_dir, map_slug, base_image_url, user_agent=user_agent
    )
    if not base_path:
        logger.info("no base map available for %s — skipping render", map_slug)
        return None

    try:
        blob = await asyncio.to_thread(
            _render_sync, base_path, pts, pad=pad, marker_radius=marker_radius
        )
    except Exception:
        logger.exception("map render failed")
        return None
    if not blob:
        return None
    return discord.File(io.BytesIO(blob), filename=filename)
