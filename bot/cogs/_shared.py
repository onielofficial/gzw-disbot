"""Shared autocomplete + helpers used across cogs."""
from __future__ import annotations

from typing import Iterable, List

import discord
from discord import app_commands
from rapidfuzz import fuzz, process


def _fuzzy_pick(items: Iterable[tuple[str, str]], query: str, *, limit: int = 25) -> list[app_commands.Choice[str]]:
    """items is iterable of (display, value). Returns up to `limit` choices."""
    items = list(items)
    if not query:
        return [app_commands.Choice(name=d[:100], value=v[:100]) for d, v in items[:limit]]
    names = [d for d, _ in items]
    scored = process.extract(query, names, scorer=fuzz.WRatio, limit=limit)
    out = []
    for name, _score, idx in scored:
        d, v = items[idx]
        out.append(app_commands.Choice(name=d[:100], value=v[:100]))
    return out


def store(bot: discord.Client):
    """Cogs reach the GZWStore via bot.store (set up in main.py)."""
    return bot.store  # type: ignore[attr-defined]
