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
from typing import Optional
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
        t.location = detail.get("location") or detail.get("region") or t.location
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
                )
                for i, o in enumerate(objs)
            ]

    # HTML fallback — the task detail page has a metadata table with rows like:
    #   <td>Location</td><td>Tiger Bay</td>
    # We also grab description from meta if the JSON path was empty.
    soup = BeautifulSoup(html, "lxml")
    if not t.location:
        t.location = _parse_table_field(soup, "location") or _parse_table_field(soup, "region")
    if not t.description:
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            t.description = meta["content"]
    return t


def _parse_table_field(soup: "BeautifulSoup", label: str) -> Optional[str]:
    """Find a value paired with `label` in a simple two-column HTML table."""
    for td in soup.find_all("td"):
        if td.get_text(strip=True).lower() == label.lower():
            sibling = td.find_next_sibling("td")
            if sibling:
                val = sibling.get_text(strip=True)
                return val if val else None
    return None


async def scrape_tasks(fetcher: HttpFetcher, s: Settings) -> list[Task]:
    index = await _scrape_task_index(fetcher, s)
    if not index:
        return []
    sema = asyncio.Semaphore(s.scrape_concurrency)

    async def fill(t: Task) -> Task:
        async with sema:
            try:
                return await _scrape_task_detail(fetcher, s, t)
            except FetchError as exc:
                logger.warning("task detail failed for %s: %s", t.slug, exc)
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
