"""Render a cropped map image with an orange location marker."""
from __future__ import annotations

import asyncio
import io
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CROP_SIZE = 400      # half-width / half-height of the crop window in pixels
MARKER_RADIUS = 18
PADDING = 20         # minimum gap between marker and crop edge


async def render_location_map(
    location: str | None,
    map_slug: str,
    data_dir: str | Path,
) -> Optional["discord.File"]:
    """Look up location coords, crop the base map, draw a marker, return discord.File.

    Returns None if the location is unknown, the map file is missing, or
    Pillow is not installed.
    """
    try:
        from bot.data.locations import find_coords
        coords = find_coords(location)
        if coords is None:
            logger.debug("no coords for location: %s", location)
            return None

        map_path = _find_map_file(data_dir, map_slug)
        if map_path is None:
            logger.warning("base map not found for slug: %s", map_slug)
            return None

        return await asyncio.get_event_loop().run_in_executor(
            None, _render_sync, coords, map_path, location or "Unknown"
        )
    except ImportError:
        logger.warning("Pillow not installed, skipping map render")
        return None
    except Exception as exc:
        logger.warning("map render failed: %s", exc)
        return None


def _find_map_file(data_dir: str | Path, slug: str) -> Optional[Path]:
    base = Path(data_dir) / "maps"
    for ext in ("png", "webp", "jpg", "jpeg"):
        p = base / f"{slug}.{ext}"
        if p.exists():
            return p
    return None


def _render_sync(
    coords: tuple[int, int],
    map_path: Path,
    location_name: str,
) -> "discord.File":
    import discord
    from PIL import Image, ImageDraw, ImageFont

    img = Image.open(map_path).convert("RGBA")
    W, H = img.size
    cx, cy = coords

    x1 = max(0, cx - CROP_SIZE)
    y1 = max(0, cy - CROP_SIZE)
    x2 = min(W, cx + CROP_SIZE)
    y2 = min(H, cy + CROP_SIZE)
    cropped = img.crop((x1, y1, x2, y2))

    mx = cx - x1
    my = cy - y1

    draw = ImageDraw.Draw(cropped)

    # Shadow
    draw.ellipse(
        [mx - MARKER_RADIUS - 2, my - MARKER_RADIUS - 2,
         mx + MARKER_RADIUS + 2, my + MARKER_RADIUS + 2],
        fill=(0, 0, 0, 120),
    )
    # White outline
    draw.ellipse(
        [mx - MARKER_RADIUS - 1, my - MARKER_RADIUS - 1,
         mx + MARKER_RADIUS + 1, my + MARKER_RADIUS + 1],
        fill=(255, 255, 255, 255),
    )
    # Orange fill
    draw.ellipse(
        [mx - MARKER_RADIUS, my - MARKER_RADIUS,
         mx + MARKER_RADIUS, my + MARKER_RADIUS],
        fill=(255, 140, 0, 255),
    )

    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16
        )
    except Exception:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), location_name, font=font)
    tw = bbox[2] - bbox[0]
    tx = mx - tw // 2
    ty = my + MARKER_RADIUS + 6

    draw.text((tx + 1, ty + 1), location_name, font=font, fill=(0, 0, 0, 200))
    draw.text((tx, ty), location_name, font=font, fill=(255, 255, 255, 255))

    buf = io.BytesIO()
    cropped.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return discord.File(buf, filename="map.png")
