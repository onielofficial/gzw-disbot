"""In-memory cache facade over the SQLite cache + JSON snapshot.

The bot loads the snapshot on startup, exposes async getters used by cogs,
and the scheduler refreshes the snapshot every N hours.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from rapidfuzz import fuzz, process

from .text import slugify


@dataclass
class GZWStore:
    tasks: list[dict] = field(default_factory=list)
    keys: list[dict] = field(default_factory=list)
    places: list[dict] = field(default_factory=list)
    groups: list[dict] = field(default_factory=list)
    traders: list[dict] = field(default_factory=list)
    factions: list[dict] = field(default_factory=list)

    # ---- Loaders ----

    @classmethod
    def from_dict(cls, payload: dict) -> "GZWStore":
        return cls(
            tasks=payload.get("tasks", []) or [],
            keys=payload.get("keys", []) or [],
            places=payload.get("places", []) or [],
            groups=payload.get("groups", []) or [],
            traders=payload.get("traders", []) or [],
            factions=payload.get("factions", []) or [],
        )

    def to_dict(self) -> dict:
        return {
            "tasks": self.tasks,
            "keys": self.keys,
            "places": self.places,
            "groups": self.groups,
            "traders": self.traders,
            "factions": self.factions,
        }

    @classmethod
    def load_snapshot(cls, path: Path) -> "GZWStore":
        if not path.exists():
            return cls()
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save_snapshot(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- Lookups ----

    def task_by_slug(self, slug: str) -> dict | None:
        slug = slugify(slug)
        return next((t for t in self.tasks if t.get("slug") == slug), None)

    def key_by_slug(self, slug: str) -> dict | None:
        slug = slugify(slug)
        return next((k for k in self.keys if k.get("slug") == slug), None)

    def place_by_id(self, pid: str | int) -> dict | None:
        s = str(pid)
        return next((p for p in self.places if str(p.get("id")) == s), None)

    def filter_tasks(self, *, trader: str | None = None, type_: str | None = None, faction: str | None = None) -> list[dict]:
        items = self.tasks
        if trader:
            t = trader.lower()
            items = [x for x in items if (x.get("trader") or "").lower() == t]
        if type_:
            t = type_.lower()
            items = [x for x in items if (x.get("type") or "").lower() == t]
        if faction:
            f = faction.lower()
            items = [x for x in items if (x.get("faction") or "").lower() == f]
        return items

    def filter_places(self, *, group: str | None = None, region: str | None = None) -> list[dict]:
        items = self.places
        if group:
            g = group.lower()
            items = [x for x in items if (x.get("group") or "").lower() == g]
        if region:
            r = region.lower()
            items = [x for x in items if (x.get("region") or "").lower() == r]
        return items

    # ---- Universal fuzzy search ----

    def search(self, query: str, *, limit: int = 15, min_score: int = 55) -> list[dict]:
        """Returns dicts of {kind, name, slug/id, score}.

        Score is the rapidfuzz match score 0-100. We bias slightly by entity
        kind so a task named the same as a place wins.
        """
        if not query:
            return []
        haystacks: list[tuple[str, str, str]] = []  # (kind, name, ref)
        for t in self.tasks:
            haystacks.append(("task", t.get("name", ""), t.get("slug", "")))
        for k in self.keys:
            haystacks.append(("key", k.get("name", ""), k.get("slug", "")))
        for p in self.places:
            haystacks.append(("place", p.get("name", ""), str(p.get("id", ""))))
        for tr in self.traders:
            haystacks.append(("trader", tr.get("name", ""), tr.get("name", "").lower()))
        for f in self.factions:
            haystacks.append(("faction", f.get("name", ""), f.get("name", "").lower()))

        names = [h[1] for h in haystacks]
        # Use partial_ratio so "tiger" matches "Tiger Bay Armory key"
        matches = process.extract(query, names, scorer=fuzz.partial_ratio, limit=limit * 3)
        results = []
        seen = set()
        for name, score, idx in matches:
            if score < min_score:
                continue
            kind, _, ref = haystacks[idx]
            key = (kind, ref)
            if key in seen:
                continue
            seen.add(key)
            results.append({"kind": kind, "name": name, "ref": ref, "score": int(score)})
            if len(results) >= limit:
                break
        return results

    # ---- Stats ----

    def stats(self) -> dict:
        return {
            "tasks": len(self.tasks),
            "keys": len(self.keys),
            "places": len(self.places),
            "groups": len(self.groups),
            "traders": len(self.traders),
            "factions": len(self.factions),
        }
