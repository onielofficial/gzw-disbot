"""Grayzone Warfare-inspired color palette for Discord embeds.

Discord embed colors are 24-bit ints. We pick palettes that read well on
Discord's dark theme — muted military greens and warning ambers — so embeds
feel like an in-game tactical briefing rather than a generic info card.
"""
from __future__ import annotations

# --- Brand ---
GZW_OLIVE = 0x4B5320       # primary brand
GZW_FATIGUE = 0x556B2F     # secondary brand (lighter olive)
GZW_KHAKI = 0x8F8B66       # neutral / informational
GZW_CHARCOAL = 0x1A1A17    # near-black for "classified" feel

# --- Status ---
INTEL_AMBER = 0xD9A441     # advisory / objective markers
PRIORITY_RED = 0xA02525    # high-priority / hostile
SAFE_GREEN = 0x4F7942      # success / completed
WIRE_BLUE = 0x3B5A6C       # neutral data
CRIMSON_SHIELD = 0x8B0000  # CSI faction
LRI_GREEN = 0x4F7942       # Lamang Recovery Initiative
MITHRAS_BLUE = 0x4A6FA5    # Mithras Security Systems
HOSTILE_RED = 0x6E1A1A     # hostile factions

# --- By trader (loose color cues from in-game UI) ---
TRADER_COLORS = {
    "handshake": 0x6F7E54,
    "gunny": 0x8F6F3A,
    "lab rat": 0x4E7E7B,
    "artisan": 0x806A4F,
    "banshee": 0x735478,
}

# --- By task type ---
TASK_TYPE_COLORS = {
    "main": GZW_OLIVE,
    "side": WIRE_BLUE,
    "contract": INTEL_AMBER,
}


def color_for_trader(name: str | None) -> int:
    if not name:
        return GZW_OLIVE
    return TRADER_COLORS.get(name.strip().lower(), GZW_OLIVE)


def color_for_task_type(t: str | None) -> int:
    if not t:
        return GZW_OLIVE
    return TASK_TYPE_COLORS.get(t.strip().lower(), GZW_OLIVE)
