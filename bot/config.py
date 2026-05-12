"""Runtime configuration. Single source of truth for env vars + paths."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent


def _env(key: str, default: str | None = None, *, required: bool = False) -> str:
    val = os.getenv(key, default)
    if required and not val:
        raise RuntimeError(f"Missing required env var: {key}")
    return val or ""


def _split_ids(value: str) -> List[int]:
    return [int(x.strip()) for x in value.split(",") if x.strip().isdigit()]


@dataclass(frozen=True)
class Settings:
    # discord
    token: str = field(default_factory=lambda: _env("DISCORD_TOKEN", required=True))
    dev_guild_ids: List[int] = field(
        default_factory=lambda: _split_ids(_env("DEV_GUILD_IDS", ""))
    )

    # scraper
    base_url: str = field(default_factory=lambda: _env("GZW_BASE_URL", "https://gzwtacmap.com").rstrip("/"))
    map_slug: str = field(default_factory=lambda: _env("GZW_MAP_SLUG", "lamang"))
    scrape_concurrency: int = field(default_factory=lambda: int(_env("SCRAPE_CONCURRENCY", "4")))
    scrape_delay_ms: int = field(default_factory=lambda: int(_env("SCRAPE_DELAY_MS", "400")))
    user_agent: str = field(default_factory=lambda: _env("USER_AGENT", "GZW-DisBot/1.0"))

    # cache / storage
    data_dir: Path = field(default_factory=lambda: Path(_env("DATA_DIR", str(ROOT / "data"))))
    cache_ttl_hours: int = field(default_factory=lambda: int(_env("CACHE_TTL_HOURS", "12")))
    refresh_cron: str = field(default_factory=lambda: _env("REFRESH_CRON", "0 */6 * * *"))

    # branding
    embed_footer: str = field(default_factory=lambda: _env("EMBED_FOOTER", "GZW Tac DisBot · INTEL"))
    embed_thumb_url: str = field(default_factory=lambda: _env("EMBED_THUMB_URL", ""))

    # logging
    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO").upper())

    @property
    def db_path(self) -> Path:
        return self.data_dir / "tracker.sqlite"

    @property
    def cache_path(self) -> Path:
        return self.data_dir / "cache.sqlite"

    @property
    def snapshot_path(self) -> Path:
        return self.data_dir / "snapshot.json"


# A single, lazily constructed instance most callers should import.
def load() -> Settings:
    s = Settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    return s
