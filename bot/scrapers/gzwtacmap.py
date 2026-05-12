"""Scraper for gzwtacmap.com.

The site is a Next.js app, so it ships the page data inside `__NEXT_DATA__`
or streamed chunks. We try to use that first (cheapest, most accurate)
and fall back to scraping rendered HTML with BeautifulSoup.

The scraper is *defensive*: if a selector or key changes, the bot keeps
running on the prior cached snapshot, just with a warning logged.

Public coroutine `scrape_all()` returns a `GZWStore`-shaped dict.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Iterable, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..config import Settings
from ..data.models import Faction, Group, Key, KeyDoor, Objective, Place, Task, Trader
from ..data.static import FACTIONS, TRADERS
from ..utils.text import slugify
from .base import FetchError, HttpFetcher
from .jsonld import deep_find_lists, parse_next_data, parse_next_streamed

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------
def url_tasks(s: Settings) -> str: return f"{s.base_url}/maps/{s.map_slug}/tasks"
def url_task(s: Settings, slug: str) -> str: return f"{s.base_url}/maps/{s.map_slug}/tasks/{slug}"
def url_keys(s: Settings) -> str: return f"{s.base_url}/maps/{s.map_slug}/keys"
def url_place(s: Settings, pid: str) -> str: return f"{s.base_url}/maps/{s.map_slug}/place/{pid}"
def url_group(s: Settings, gid: str) -> str: return f"{s.base_url}/maps/{s.map_slug}/group/{gid}"


# ---------------------------------------------------------------------------
# Generic Next.js extraction
# ---------------------------------------------------------------------------
def _next_props(html: str) -> dict:
    """Pull the most useful page props from a Next.js page."""
    nd = parse_next_data(html)
    return (
        nd.get("props", {}).get("pageProps", {})
        if isinstance(nd, dict)
        else {}
    )


def _absolutize(base_url: str, href: Optional[str]) -> Optional[str]:
    if not href:
        return None
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return urljoin(base_url + "/", href.lstrip("/"))


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------
async def _scrape_task_index(fetcher: HttpFetcher, s: Settings) -> list[Task]:
    html = await fetcher.get_text(url_tasks(s))
    props = _next_props(html)

    candidates = deep_find_lists(props, key_hints=("tasks", "missions", "items"))
    raw_tasks: list[dict] = next((c for c in candidates if c), [])

    if not raw_tasks:
        # HTML fallback — find anchors to /tasks/<slug>
        soup = BeautifulSoup(html, "lxml")
        seen = set()
        for a in soup.select("a[href*='/tasks/']"):
            href = a.get("href") or ""
            m = re.search(r"/tasks/([^/?#]+)$", href)
            if not m:
                continue
            slug = m.group(1)
            if slug in seen:
                continue
            seen.add(slug)
            raw_tasks.append({"slug": slug, "name": (a.get_text(strip=True) or slug).strip()})

    out: list[Task] = []
    for r in raw_tasks:
        slug = (r.get("slug") or slugify(r.get("name", ""))).strip()
        if not slug:
            continue
        out.append(
            Task(
                slug=slug,
                name=r.get("name") or slug.replace("-", " ").title(),
                type=(r.get("type") or r.get("category") or "main").lower(),
                trader=r.get("trader") or r.get("vendor"),
                faction=r.get("faction"),
                summary=r.get("summary") or r.get("short_description"),
                description=r.get("description"),
                source_url=url_task(s, slug),
            )
        )
    return out


async def _scrape_task_detail(fetcher: HttpFetcher, s: Settings, t: Task) -> Task:
    html = await fetcher.get_text(t.source_url or url_task(s, t.slug))
    props = _next_props(html)

    # Try to find the singular "task" object the page is rendered for.
    detail: dict = {}
    if isinstance(props, dict):
        for k in ("task", "mission", "data", "item"):
            if isinstance(props.get(k), dict):
                detail = props[k]
                break

    if detail:
        t.name = detail.get("name") or t.name
        t.type = (detail.get("type") or detail.get("category") or t.type or "main").lower()
        t.trader = detail.get("trader") or detail.get("vendor") or t.trader
        t.faction = detail.get("faction") or t.faction
        t.summary = detail.get("summary") or detail.get("shortDescription") or t.summary
        t.description = detail.get("description") or t.description
        t.rewards = list(detail.get("rewards") or t.rewards)
        t.prerequisites = list(detail.get("prerequisites") or t.prerequisites)
        objs = detail.get("objectives") or detail.get("steps") or []
        if objs:
            t.objectives = [
                Objective(
                    id=str(o.get("id") or o.get("placeId") or i),
                    name=o.get("name") or o.get("title"),
                    note=o.get("note") or o.get("description"),
                    place_id=str(o.get("placeId")) if o.get("placeId") else None,
                    location=o.get("location") or o.get("region"),
                    x=_as_float(o.get("x") or o.get("coordX") or o.get("cx")),
                    y=_as_float(o.get("y") or o.get("coordY") or o.get("cy")),
                )
                for i, o in enumerate(objs)
            ]

    # HTML fallback for description
    if not t.description:
        soup = BeautifulSoup(html, "lxml")
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            t.description = meta["content"]
    return t


def _as_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Playwright fallback
# ---------------------------------------------------------------------------
# Gated by Settings.use_playwright. Imports playwright lazily so the bot still
# runs (with empty objective coords) when playwright isn't installed.
_pw_sema: Optional[asyncio.Semaphore] = None


def _get_pw_sema(limit: int) -> asyncio.Semaphore:
    global _pw_sema
    if _pw_sema is None:
        _pw_sema = asyncio.Semaphore(max(1, limit))
    return _pw_sema


async def fetch_task_via_playwright(
    task_url: str,
    *,
    user_agent: str = "GZW-DisBot/1.0",
    timeout_ms: int = 20000,
) -> Optional[dict]:
    """Render `task_url` in headless Chromium and pull objective markers from
    the DOM. Returns ``{"objectives": [{"id","name","place_id","x","y","location"}], "description": str|None}``
    or ``None`` if playwright isn't installed / the page fails to load.

    The extractor tries three sources in order: marker DOM nodes with data
    attributes, SVG ``<circle>`` markers, and any ``__NEXT_DATA__`` blob that
    finished hydrating client-side.
    """
    try:
        from playwright.async_api import async_playwright  # type: ignore
    except ImportError:
        logger.info("playwright not installed; skipping rich scrape for %s", task_url)
        return None

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                context = await browser.new_context(user_agent=user_agent)
                page = await context.new_page()
                await page.goto(task_url, wait_until="networkidle", timeout=timeout_ms)
                # Best-effort wait for marker layer — don't fail if none appear.
                try:
                    await page.wait_for_selector(
                        "[data-marker-x], [data-objective], circle[data-place-id], .objective-marker, .marker",
                        timeout=max(2000, timeout_ms // 2),
                    )
                except Exception:
                    pass
                objectives = await page.evaluate(_PW_EXTRACT_JS)
                description = await page.evaluate(
                    "() => { const m = document.querySelector('meta[name=\"description\"]'); return m ? m.content : null; }"
                )
                return {"objectives": objectives or [], "description": description}
            finally:
                await browser.close()
    except Exception as exc:
        logger.warning("playwright scrape failed for %s: %s", task_url, exc)
        return None


_PW_EXTRACT_JS = r"""
() => {
    const out = [];
    const seen = new Set();
    const add = (rec) => {
        if (rec.x == null || rec.y == null) return;
        const key = String(rec.id || rec.place_id || `${rec.x},${rec.y}`);
        if (seen.has(key)) return;
        seen.add(key);
        out.push(rec);
    };

    // 1. Generic data-attribute markers
    document.querySelectorAll('[data-marker-x][data-marker-y]').forEach(el => {
        add({
            id: el.dataset.id || el.dataset.objectiveId || '',
            place_id: el.dataset.placeId || '',
            name: el.getAttribute('aria-label') || (el.textContent || '').trim() || null,
            location: el.dataset.location || null,
            x: parseFloat(el.dataset.markerX),
            y: parseFloat(el.dataset.markerY),
        });
    });

    // 2. SVG circle markers
    document.querySelectorAll('circle[data-place-id], circle[data-objective-id]').forEach(el => {
        add({
            id: el.dataset.objectiveId || '',
            place_id: el.dataset.placeId || '',
            name: el.dataset.name || el.getAttribute('aria-label') || null,
            location: el.dataset.location || null,
            x: parseFloat(el.getAttribute('cx')),
            y: parseFloat(el.getAttribute('cy')),
        });
    });

    // 3. CSS transform: translate(...px, ...px) on anything that looks like an objective marker
    if (out.length === 0) {
        const markerLike = document.querySelectorAll('[class*="marker" i], [class*="objective" i]');
        markerLike.forEach(el => {
            const t = (el.style && el.style.transform) || '';
            const m = t.match(/translate(?:3d)?\(\s*(-?\d+(?:\.\d+)?)px\s*,\s*(-?\d+(?:\.\d+)?)px/);
            if (!m) return;
            add({
                id: el.dataset.id || '',
                place_id: el.dataset.placeId || '',
                name: el.getAttribute('aria-label') || null,
                location: el.dataset.location || null,
                x: parseFloat(m[1]),
                y: parseFloat(m[2]),
            });
        });
    }

    // 4. Hydrated __NEXT_DATA__ — gzwtacmap streams data in, so this may
    //    only be populated after the client has mounted.
    try {
        const nd = document.getElementById('__NEXT_DATA__');
        if (nd && nd.textContent) {
            const stack = [JSON.parse(nd.textContent)];
            while (stack.length) {
                const o = stack.pop();
                if (!o || typeof o !== 'object') continue;
                const objs = o.objectives || o.steps;
                if (Array.isArray(objs)) {
                    objs.forEach(ob => {
                        const x = ob.x ?? ob.coordX ?? ob.cx;
                        const y = ob.y ?? ob.coordY ?? ob.cy;
                        if (typeof x === 'number' && typeof y === 'number') {
                            add({
                                id: ob.id != null ? String(ob.id) : '',
                                place_id: ob.placeId != null ? String(ob.placeId) : '',
                                name: ob.name || ob.title || null,
                                location: ob.location || ob.region || null,
                                x, y,
                            });
                        }
                    });
                }
                for (const k in o) {
                    const v = o[k];
                    if (v && typeof v === 'object') stack.push(v);
                }
            }
        }
    } catch (e) { /* noop */ }

    return out;
}
"""


async def _enrich_task_via_playwright(s: Settings, t: Task) -> Task:
    """Fill objective coordinates on `t` using a headless Chromium render.

    No-op if playwright is disabled, the page fails, or no markers are found.
    Merges by ``place_id`` when possible, otherwise falls back to positional
    alignment for tasks whose ordered objectives already exist.
    """
    if not s.use_playwright:
        return t
    has_any_coords = any(o.x is not None and o.y is not None for o in t.objectives)
    if has_any_coords:
        return t
    sema = _get_pw_sema(s.playwright_concurrency)
    async with sema:
        rendered = await fetch_task_via_playwright(
            t.source_url or url_task(s, t.slug),
            user_agent=s.user_agent,
            timeout_ms=s.playwright_timeout_ms,
        )
    if not rendered:
        return t

    rendered_objs = rendered.get("objectives") or []
    if not rendered_objs:
        return t

    if not t.description and rendered.get("description"):
        t.description = rendered["description"]

    by_place: dict[str, dict] = {
        str(r.get("place_id")): r for r in rendered_objs if r.get("place_id")
    }

    if t.objectives:
        for i, obj in enumerate(t.objectives):
            match = None
            if obj.place_id and obj.place_id in by_place:
                match = by_place[obj.place_id]
            elif i < len(rendered_objs):
                match = rendered_objs[i]
            if not match:
                continue
            obj.x = obj.x if obj.x is not None else _as_float(match.get("x"))
            obj.y = obj.y if obj.y is not None else _as_float(match.get("y"))
            obj.location = obj.location or match.get("location")
            if not obj.place_id and match.get("place_id"):
                obj.place_id = str(match["place_id"])
            if not obj.name and match.get("name"):
                obj.name = match.get("name")
    else:
        t.objectives = [
            Objective(
                id=str(r.get("id") or r.get("place_id") or i),
                name=r.get("name"),
                place_id=str(r["place_id"]) if r.get("place_id") else None,
                location=r.get("location"),
                x=_as_float(r.get("x")),
                y=_as_float(r.get("y")),
            )
            for i, r in enumerate(rendered_objs)
        ]
    return t


async def scrape_tasks(fetcher: HttpFetcher, s: Settings) -> list[Task]:
    index = await _scrape_task_index(fetcher, s)
    if not index:
        return []
    sema = asyncio.Semaphore(s.scrape_concurrency)

    async def fill(t: Task) -> Task:
        async with sema:
            try:
                t = await _scrape_task_detail(fetcher, s, t)
            except FetchError as exc:
                logger.warning("task detail failed for %s: %s", t.slug, exc)
                return t
        # Playwright pass runs outside the aiohttp semaphore — it has its own
        # concurrency cap because Chromium is expensive.
        try:
            t = await _enrich_task_via_playwright(s, t)
        except Exception as exc:  # never let one task kill the batch
            logger.warning("playwright enrich failed for %s: %s", t.slug, exc)
        return t

    return await asyncio.gather(*(fill(t) for t in index))


# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------
async def scrape_keys(fetcher: HttpFetcher, s: Settings) -> list[Key]:
    html = await fetcher.get_text(url_keys(s))
    props = _next_props(html)
    candidates = deep_find_lists(props, key_hints=("keys", "items"))
    raw_keys: list[dict] = next((c for c in candidates if c), [])

    if not raw_keys:
        soup = BeautifulSoup(html, "lxml")
        # Try table rows or list items containing "key"
        rows = soup.select("tr, li, .key, [data-key]")
        for row in rows:
            txt = row.get_text(" ", strip=True)
            if "key" not in txt.lower():
                continue
            name = (row.find(["a", "h2", "h3", "strong"]) or row).get_text(strip=True)
            if name:
                raw_keys.append({"name": name})

    out: list[Key] = []
    seen_slugs: set[str] = set()
    for r in raw_keys:
        name = (r.get("name") or "").strip()
        if not name:
            continue
        slug = r.get("slug") or slugify(name)
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        doors_raw = r.get("doors") or r.get("opens") or []
        doors = [
            KeyDoor(
                name=d.get("name") if isinstance(d, dict) else str(d),
                location=(d.get("location") if isinstance(d, dict) else None),
                place_id=str(d.get("placeId")) if isinstance(d, dict) and d.get("placeId") else None,
            )
            for d in doors_raw
        ]
        out.append(
            Key(
                slug=slug,
                name=name,
                region=r.get("region"),
                found_on=r.get("foundOn") or r.get("found_on"),
                rarity=r.get("rarity"),
                uses=r.get("uses"),
                doors=doors,
                notes=r.get("notes"),
                source_url=url_keys(s),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Places
# ---------------------------------------------------------------------------
async def scrape_places(fetcher: HttpFetcher, s: Settings, *, max_ids: int = 1500) -> list[Place]:
    """Index page is the map itself, which lists places in the streamed Next chunks.

    We pull whatever is there and stop. Resolving every individual /place/{id}
    page would be hundreds of requests; the index alone has enough fields for
    embeds to look good.
    """
    html = await fetcher.get_text(f"{s.base_url}/maps/{s.map_slug}")
    props = _next_props(html)
    candidates = deep_find_lists(props, key_hints=("places", "markers", "pois", "points"))
    raw_places: list[dict] = next((c for c in candidates if c), [])

    if not raw_places:
        # Stream-chunk fallback
        for chunk in parse_next_streamed(html):
            if "place" in chunk.lower():
                # Best-effort: regex out objects like {"id":1373,"name":"..."}
                for m in re.finditer(
                    r'\{"id":(\d+),"name":"([^"]+)"', chunk
                ):
                    raw_places.append({"id": m.group(1), "name": m.group(2)})

    out: list[Place] = []
    seen: set[str] = set()
    for r in raw_places[:max_ids]:
        pid = str(r.get("id") or "").strip()
        name = (r.get("name") or "").strip()
        if not pid or not name or pid in seen:
            continue
        seen.add(pid)
        out.append(
            Place(
                id=pid,
                name=name,
                group=str(r.get("group") or r.get("category") or "POI"),
                region=r.get("region"),
                description=r.get("description"),
                coords=(
                    f"{r['x']},{r['y']}"
                    if isinstance(r.get("x"), (int, float)) and isinstance(r.get("y"), (int, float))
                    else None
                ),
                related_tasks=list(r.get("tasks") or []),
                source_url=url_place(s, pid),
                screenshot=_absolutize(s.base_url, r.get("screenshot") or r.get("image")),
                thumb=_absolutize(s.base_url, r.get("thumb") or r.get("icon")),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------
async def scrape_groups(fetcher: HttpFetcher, s: Settings) -> list[Group]:
    """Groups are categories the map filters by. We can't enumerate them
    without a known list, so we probe well-known IDs (1, 38) and any ID we
    learn from places we've seen. This stays cheap and deterministic.
    """
    out: list[Group] = []
    known: dict[str, str] = {"1": "Landing Zones", "38": "Combat Outposts"}

    for gid, fallback_name in known.items():
        try:
            html = await fetcher.get_text(url_group(s, gid))
        except FetchError as exc:
            logger.warning("group %s fetch failed: %s", gid, exc)
            continue
        props = _next_props(html)
        info = props.get("group") if isinstance(props, dict) else None
        name = (info or {}).get("name") if isinstance(info, dict) else None
        out.append(
            Group(
                id=gid,
                name=name or fallback_name,
                description=(info or {}).get("description") if isinstance(info, dict) else None,
                place_count=int((info or {}).get("count", 0)) if isinstance(info, dict) else 0,
                source_url=url_group(s, gid),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------
async def scrape_all(s: Settings) -> dict:
    """Scrape everything and return a dict shaped for GZWStore.from_dict()."""
    async with HttpFetcher(
        user_agent=s.user_agent,
        concurrency=s.scrape_concurrency,
        delay_ms=s.scrape_delay_ms,
    ) as fetcher:
        # Run independent fetches concurrently
        tasks_t, keys_t, places_t, groups_t = await asyncio.gather(
            scrape_tasks(fetcher, s),
            scrape_keys(fetcher, s),
            scrape_places(fetcher, s),
            scrape_groups(fetcher, s),
            return_exceptions=True,
        )

    def _ok(x):
        if isinstance(x, Exception):
            logger.error("scrape sub-task failed: %s", x)
            return []
        return x

    return {
        "tasks": [t.to_dict() for t in _ok(tasks_t)],
        "keys": [k.to_dict() for k in _ok(keys_t)],
        "places": [p.to_dict() for p in _ok(places_t)],
        "groups": [g.to_dict() for g in _ok(groups_t)],
        # Static, hand-curated:
        "traders": [Trader(**t).to_dict() for t in TRADERS],
        "factions": [Faction(**f).to_dict() for f in FACTIONS],
    }
