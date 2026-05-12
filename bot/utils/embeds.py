"""GZW-themed embed builders.

The whole bot's visual identity flows through this module. If you want to
re-skin every command, change it here.

Design language:
  - Author line carries the *callsign* of the data source ("INTEL · TASK")
  - Title is the entity's display name, prefixed with a tactical glyph
  - Body uses ASCII banners + key/value HUD blocks (not bullet soup)
  - Footer always cites gzwtacmap.com and the data freshness timestamp
  - Color is chosen from the GZW palette per entity type
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Sequence

import discord

from . import colors
from .text import (
    DASH_BAR,
    banner,
    code_block,
    kv_table,
    progress_bar,
    safe_field,
    truncate,
)

# --- Glyphs (kept simple to render across clients) ----------------------------
GLYPH = {
    "task": "◉",
    "side": "◈",
    "contract": "◇",
    "key": "⌬",
    "place": "◬",
    "lz": "▲",
    "cop": "■",
    "loot": "✦",
    "trader": "◎",
    "faction": "❖",
    "warning": "△",
    "ok": "✓",
    "fail": "✕",
    "intel": "❉",
    "track": "▶",
}


# -----------------------------------------------------------------------------
# Core builder
# -----------------------------------------------------------------------------
def base_embed(
    *,
    title: str,
    description: str | None = None,
    color: int = colors.GZW_OLIVE,
    author_kind: str = "INTEL",
    url: str | None = None,
    thumb: str | None = None,
    footer_extra: str | None = None,
) -> discord.Embed:
    e = discord.Embed(
        title=truncate(title, 256),
        description=truncate(description or "", 4000),
        color=color,
        url=url,
        timestamp=datetime.now(timezone.utc),
    )
    e.set_author(name=f"GZW · {author_kind.upper()}")
    foot = "Source: gzwtacmap.com"
    if footer_extra:
        foot = f"{foot}  ·  {footer_extra}"
    e.set_footer(text=truncate(foot, 2048))
    if thumb:
        e.set_thumbnail(url=thumb)
    return e


# -----------------------------------------------------------------------------
# Per-entity embeds
# -----------------------------------------------------------------------------
def embed_task(task: dict, *, base_url: str) -> discord.Embed:
    """Render a single Task entity.

    Expected dict keys (gracefully degrades if any are missing):
      name, slug, type ('main'/'side'/'contract'), trader, faction,
      summary, description, rewards (list[str]), prerequisites (list[str]),
      objectives (list[{name,id,note}]), source_url
    """
    glyph = GLYPH.get(task.get("type", "task"), GLYPH["task"])
    color = colors.color_for_task_type(task.get("type"))
    e = base_embed(
        title=f"{glyph}  {task.get('name', 'Unknown Task')}",
        color=color,
        author_kind=f"TASK · {(task.get('type') or 'main').upper()}",
        url=task.get("source_url") or f"{base_url}/maps/lamang/tasks/{task.get('slug','')}",
        thumb=task.get("thumb"),
        footer_extra=task.get("updated_at"),
    )

    head_pairs = [
        ("TRADER", task.get("trader") or "—"),
        ("FACTION", task.get("faction") or "Any"),
        ("TYPE", (task.get("type") or "main").title()),
        ("STATUS", task.get("user_status") or "Not started"),
    ]
    e.description = (
        f"`{banner('intel — task brief')}`\n"
        + kv_table(head_pairs)
        + (f"\n{task.get('summary','').strip()}" if task.get("summary") else "")
    )

    objs = task.get("objectives") or []
    if objs:
        lines = []
        for i, o in enumerate(objs[:10], 1):
            mark = GLYPH["ok"] if o.get("done") else GLYPH["fail"]
            label = o.get("name") or o.get("id") or "—"
            note = f" — {o['note']}" if o.get("note") else ""
            lines.append(f"`{i:>2}` {mark}  {label}{note}")
        e.add_field(
            name=f"{GLYPH['place']}  Objectives ({len(objs)})",
            value=safe_field("\n".join(lines)),
            inline=False,
        )

    if task.get("rewards"):
        e.add_field(
            name=f"{GLYPH['intel']}  Rewards",
            value=safe_field("\n".join(f"• {r}" for r in task["rewards"][:8])),
            inline=True,
        )
    if task.get("prerequisites"):
        e.add_field(
            name=f"{GLYPH['warning']}  Prerequisites",
            value=safe_field("\n".join(f"• {r}" for r in task["prerequisites"][:8])),
            inline=True,
        )
    if task.get("description"):
        e.add_field(
            name=f"{DASH_BAR}",
            value=safe_field(task["description"], limit=1024),
            inline=False,
        )

    return e


def embed_key(key: dict, *, base_url: str) -> discord.Embed:
    e = base_embed(
        title=f"{GLYPH['key']}  {key.get('name', 'Unknown Key')}",
        color=colors.INTEL_AMBER,
        author_kind="KEY · ITEM",
        url=key.get("source_url") or f"{base_url}/maps/lamang/keys",
        thumb=key.get("thumb"),
    )
    pairs = [
        ("REGION", key.get("region") or "—"),
        ("FOUND ON", key.get("found_on") or "AI loot"),
        ("RARITY", key.get("rarity") or "—"),
        ("USE-USES", str(key.get("uses") or "∞")),
    ]
    e.description = f"`{banner('key intel')}`\n" + kv_table(pairs)

    doors = key.get("doors") or []
    if doors:
        lines = [f"• {d.get('name','—')} — {d.get('location','—')}" for d in doors[:10]]
        e.add_field(
            name=f"{GLYPH['place']}  Opens ({len(doors)})",
            value=safe_field("\n".join(lines)),
            inline=False,
        )
    if key.get("notes"):
        e.add_field(name=DASH_BAR, value=safe_field(key["notes"]), inline=False)
    return e


def embed_place(place: dict, *, base_url: str) -> discord.Embed:
    e = base_embed(
        title=f"{GLYPH['place']}  {place.get('name', 'Unknown Place')}",
        color=colors.WIRE_BLUE,
        author_kind=f"PLACE · {(place.get('group') or 'POI').upper()}",
        url=place.get("source_url")
        or f"{base_url}/maps/lamang/place/{place.get('id', '')}",
        thumb=place.get("thumb"),
    )
    pairs = [
        ("REGION", place.get("region") or "—"),
        ("GROUP", place.get("group") or "POI"),
        ("COORDS", place.get("coords") or "—"),
        ("LZ", place.get("nearest_lz") or "—"),
    ]
    e.description = f"`{banner('place intel')}`\n" + kv_table(pairs)
    if place.get("description"):
        e.add_field(name=DASH_BAR, value=safe_field(place["description"]), inline=False)
    if place.get("related_tasks"):
        e.add_field(
            name=f"{GLYPH['task']}  Related Tasks",
            value=safe_field("\n".join(f"• {t}" for t in place["related_tasks"][:8])),
            inline=False,
        )
    if place.get("screenshot"):
        e.set_image(url=place["screenshot"])
    return e


def embed_lz(lz: dict, *, base_url: str) -> discord.Embed:
    e = base_embed(
        title=f"{GLYPH['lz']}  {lz.get('name', 'LZ')}",
        color=colors.SAFE_GREEN,
        author_kind="LZ · LANDING",
        url=lz.get("source_url") or f"{base_url}/maps/lamang/group/1",
    )
    pairs = [
        ("REGION", lz.get("region") or "—"),
        ("FACTION", lz.get("faction") or "Any"),
        ("THREAT", lz.get("threat") or "Low"),
    ]
    e.description = f"`{banner('landing zone')}`\n" + kv_table(pairs)
    if lz.get("notes"):
        e.add_field(name=DASH_BAR, value=safe_field(lz["notes"]), inline=False)
    return e


def embed_trader(trader: dict) -> discord.Embed:
    e = base_embed(
        title=f"{GLYPH['trader']}  {trader.get('name','Trader')}",
        color=colors.color_for_trader(trader.get("name")),
        author_kind="TRADER · DOSSIER",
        thumb=trader.get("portrait"),
    )
    pairs = [
        ("CALLSIGN", trader.get("callsign") or "—"),
        ("ROLE", trader.get("role") or "—"),
        ("FACTION", trader.get("faction") or "—"),
        ("TASKS", str(trader.get("task_count") or "—")),
    ]
    e.description = (
        f"`{banner('vendor dossier')}`\n"
        + kv_table(pairs)
        + (f"\n{trader.get('bio','').strip()}" if trader.get("bio") else "")
    )
    if trader.get("specialties"):
        e.add_field(
            name=f"{GLYPH['intel']}  Specialties",
            value=safe_field("\n".join(f"• {s}" for s in trader["specialties"])),
            inline=False,
        )
    return e


def embed_faction(faction: dict) -> discord.Embed:
    pmc = (faction.get("type") or "").lower() == "pmc"
    color = (
        colors.LRI_GREEN
        if "lri" in faction.get("name","").lower()
        else colors.MITHRAS_BLUE
        if "mithras" in faction.get("name","").lower()
        else colors.CRIMSON_SHIELD
        if "csi" in faction.get("name","").lower() or "crimson" in faction.get("name","").lower()
        else colors.HOSTILE_RED
    )
    e = base_embed(
        title=f"{GLYPH['faction']}  {faction.get('name','Faction')}",
        color=color,
        author_kind=f"FACTION · {'PMC' if pmc else 'HOSTILE'}",
    )
    e.description = (
        f"`{banner('faction dossier')}`\n"
        + kv_table([
            ("TYPE", "PMC" if pmc else "HOSTILE"),
            ("HQ", faction.get("hq") or "—"),
            ("AOR", faction.get("aor") or "—"),
            ("THREAT", faction.get("threat") or "—"),
        ])
        + (f"\n{faction.get('bio','').strip()}" if faction.get("bio") else "")
    )
    return e


def embed_search_results(query: str, hits: Sequence[dict]) -> discord.Embed:
    e = base_embed(
        title=f"{GLYPH['intel']}  Search · “{truncate(query, 80)}”",
        color=colors.GZW_KHAKI,
        author_kind="INTEL · SEARCH",
    )
    if not hits:
        e.description = code_block("No matches in current intel.\nTry a shorter query.")
        return e
    lines = []
    for h in hits[:15]:
        kind = (h.get("kind") or "?").upper()
        score = h.get("score")
        score_str = f" [{score:>3}]" if score is not None else ""
        lines.append(f"`{kind:<6}`{score_str}  {h.get('name','—')}")
    e.description = code_block("\n".join(lines))
    return e


def embed_tracker(user_name: str, summary: dict) -> discord.Embed:
    """summary keys: total_tasks, done_tasks, total_keys, owned_keys, recent (list)."""
    e = base_embed(
        title=f"{GLYPH['track']}  Op-tracker · {user_name}",
        color=colors.GZW_FATIGUE,
        author_kind="OPERATOR · TRACKER",
    )
    pb_tasks = progress_bar(summary.get("done_tasks", 0), summary.get("total_tasks", 0))
    pb_keys = progress_bar(summary.get("owned_keys", 0), summary.get("total_keys", 0))
    e.description = (
        f"`{banner('operator status')}`\n"
        + code_block(
            f"Tasks   {pb_tasks}\n"
            f"Keys    {pb_keys}\n"
            f"Faction {summary.get('faction') or '—'}"
        )
    )
    recent = summary.get("recent") or []
    if recent:
        lines = [f"• {GLYPH['ok'] if r.get('done') else GLYPH['fail']}  {r.get('name','—')}" for r in recent[:8]]
        e.add_field(name=f"{GLYPH['intel']}  Recent activity", value=safe_field("\n".join(lines)), inline=False)
    return e


def embed_error(message: str) -> discord.Embed:
    e = base_embed(
        title=f"{GLYPH['warning']}  Comms broken",
        color=colors.PRIORITY_RED,
        author_kind="ERROR",
    )
    e.description = code_block(message)
    return e


def embed_help() -> discord.Embed:
    e = base_embed(
        title=f"{GLYPH['intel']}  GZW Tac DisBot · Briefing",
        color=colors.GZW_OLIVE,
        author_kind="HQ · BRIEFING",
    )
    e.description = (
        f"`{banner('available commands')}`\n"
        + code_block(
            "/task search   look up a task by name\n"
            "/task list     filter tasks by trader/type/faction\n"
            "/key search    look up a key by name\n"
            "/place search  look up a POI / objective\n"
            "/lz list       all landing zones\n"
            "/cop list      combat outposts\n"
            "/trader info   trader dossiers\n"
            "/faction info  PMC + hostile factions\n"
            "/search        fuzzy search across everything\n"
            "/track me      your personal progress\n"
            "/track set     mark task / key as done\n"
            "/map           map link & overview\n"
            "/refresh       (admin) re-scrape now\n"
        )
        + "\nIntel sourced from gzwtacmap.com — refreshed every 6h."
    )
    return e
