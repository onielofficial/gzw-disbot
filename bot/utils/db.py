"""SQLite helpers for cache + per-user tracker.

We keep two databases:
  - cache.sqlite    : scraped data (tasks, places, keys, groups, traders)
  - tracker.sqlite  : per-user state (task progress, owned keys, settings)

Both are managed via aiosqlite. Tables are created idempotently on init.
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Iterable, Sequence

import aiosqlite


# -----------------------------------------------------------------------------
# Cache DB
# -----------------------------------------------------------------------------
CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tasks (
    slug TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT,
    trader TEXT,
    faction TEXT,
    summary TEXT,
    description TEXT,
    json TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_tasks_trader ON tasks(trader);
CREATE INDEX IF NOT EXISTS idx_tasks_type ON tasks(type);

CREATE TABLE IF NOT EXISTS keys (
    slug TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    region TEXT,
    json TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_keys_region ON keys(region);

CREATE TABLE IF NOT EXISTS places (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    "group" TEXT,
    region TEXT,
    json TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_places_group ON places("group");
CREATE INDEX IF NOT EXISTS idx_places_region ON places(region);

CREATE TABLE IF NOT EXISTS groups (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    json TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# -----------------------------------------------------------------------------
# Tracker DB
# -----------------------------------------------------------------------------
TRACKER_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    faction TEXT,
    settings TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS task_progress (
    user_id TEXT NOT NULL,
    task_slug TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'in_progress',  -- in_progress | done | abandoned
    note TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, task_slug)
);
CREATE INDEX IF NOT EXISTS idx_task_progress_user ON task_progress(user_id);

CREATE TABLE IF NOT EXISTS objective_progress (
    user_id TEXT NOT NULL,
    task_slug TEXT NOT NULL,
    objective_id TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, task_slug, objective_id)
);

CREATE TABLE IF NOT EXISTS owned_keys (
    user_id TEXT NOT NULL,
    key_slug TEXT NOT NULL,
    obtained_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, key_slug)
);
"""


@asynccontextmanager
async def open_db(path: Path, schema: str) -> AsyncIterator[aiosqlite.Connection]:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(path)
    try:
        db.row_factory = aiosqlite.Row
        await db.executescript(schema)
        await db.commit()
        yield db
    finally:
        await db.close()


# -------------------- High-level helpers --------------------

async def upsert_task(db: aiosqlite.Connection, task: dict) -> None:
    await db.execute(
        """
        INSERT INTO tasks (slug, name, type, trader, faction, summary, description, json)
             VALUES (:slug, :name, :type, :trader, :faction, :summary, :description, :json)
        ON CONFLICT(slug) DO UPDATE SET
            name=excluded.name,
            type=excluded.type,
            trader=excluded.trader,
            faction=excluded.faction,
            summary=excluded.summary,
            description=excluded.description,
            json=excluded.json,
            updated_at=datetime('now')
        """,
        {
            "slug": task["slug"],
            "name": task["name"],
            "type": task.get("type"),
            "trader": task.get("trader"),
            "faction": task.get("faction"),
            "summary": task.get("summary"),
            "description": task.get("description"),
            "json": json.dumps(task, ensure_ascii=False),
        },
    )


async def upsert_key(db: aiosqlite.Connection, key: dict) -> None:
    await db.execute(
        """
        INSERT INTO keys (slug, name, region, json) VALUES (:slug, :name, :region, :json)
        ON CONFLICT(slug) DO UPDATE SET
            name=excluded.name, region=excluded.region,
            json=excluded.json, updated_at=datetime('now')
        """,
        {
            "slug": key["slug"],
            "name": key["name"],
            "region": key.get("region"),
            "json": json.dumps(key, ensure_ascii=False),
        },
    )


async def upsert_place(db: aiosqlite.Connection, place: dict) -> None:
    await db.execute(
        """
        INSERT INTO places (id, name, "group", region, json)
             VALUES (:id, :name, :group, :region, :json)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name, "group"=excluded."group", region=excluded.region,
            json=excluded.json, updated_at=datetime('now')
        """,
        {
            "id": str(place["id"]),
            "name": place["name"],
            "group": place.get("group"),
            "region": place.get("region"),
            "json": json.dumps(place, ensure_ascii=False),
        },
    )


async def upsert_group(db: aiosqlite.Connection, group: dict) -> None:
    await db.execute(
        """
        INSERT INTO groups (id, name, json) VALUES (:id, :name, :json)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name, json=excluded.json, updated_at=datetime('now')
        """,
        {
            "id": str(group["id"]),
            "name": group["name"],
            "json": json.dumps(group, ensure_ascii=False),
        },
    )


async def fetch_all_json(db: aiosqlite.Connection, table: str) -> list[dict]:
    safe_tables = {"tasks", "keys", "places", "groups"}
    if table not in safe_tables:
        raise ValueError(f"unknown table: {table}")
    cur = await db.execute(f'SELECT json FROM "{table}"')
    rows = await cur.fetchall()
    return [json.loads(r["json"]) for r in rows]


async def fetch_meta(db: aiosqlite.Connection, key: str) -> str | None:
    cur = await db.execute("SELECT value FROM meta WHERE key=?", (key,))
    row = await cur.fetchone()
    return row["value"] if row else None


async def set_meta(db: aiosqlite.Connection, key: str, value: str) -> None:
    await db.execute(
        """INSERT INTO meta (key, value) VALUES (?, ?)
           ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=datetime('now')""",
        (key, value),
    )
