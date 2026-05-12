"""Seed snapshot.json from local fixtures.

Useful when you want to demo the bot without hitting gzwtacmap.com — point
DATA_DIR at a temp dir and run this once.

    python scripts/seed_from_fixtures.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bot import config  # noqa: E402
from bot.utils.cache import GZWStore  # noqa: E402


def _load(name: str) -> list[dict]:
    p = ROOT / "fixtures" / name
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> int:
    s = config.load()
    payload = {
        "tasks": _load("sample_tasks.json"),
        "keys": _load("sample_keys.json"),
        "places": _load("sample_places.json"),
        "groups": _load("sample_groups.json"),
        "traders": _load("sample_traders.json"),
        "factions": _load("sample_factions.json"),
    }
    store = GZWStore.from_dict(payload)
    store.save_snapshot(s.snapshot_path)
    print(f"seeded → {s.snapshot_path}")
    print(store.stats())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
