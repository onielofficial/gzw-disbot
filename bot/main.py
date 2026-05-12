"""GZW Tac DisBot — entry point.

Run with: ``python -m bot.main`` (after installing requirements + setting .env)
"""
from __future__ import annotations

import asyncio
import logging
import signal
import sys
from typing import Optional

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from discord.ext import commands
from rich.logging import RichHandler

from . import config
from .cogs import COGS
from .scrapers.gzwtacmap import scrape_all
from .utils.cache import GZWStore

log = logging.getLogger("gzw")


# -----------------------------------------------------------------------------
def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
    )


# -----------------------------------------------------------------------------
class GZWBot(commands.Bot):
    def __init__(self, settings: config.Settings):
        intents = discord.Intents.default()
        # message_content NOT required — we only use slash commands
        super().__init__(
            command_prefix=commands.when_mentioned,  # legacy commands disabled in practice
            intents=intents,
        )
        self.settings = settings
        self.store: GZWStore = GZWStore.load_snapshot(settings.snapshot_path)
        self.scheduler: Optional[AsyncIOScheduler] = None

    async def setup_hook(self) -> None:
        # Load all cogs
        for cog in COGS:
            await self.load_extension(cog)
            log.info("loaded cog: %s", cog)

        # Sync slash commands
        if self.settings.dev_guild_ids:
            for gid in self.settings.dev_guild_ids:
                guild = discord.Object(id=gid)
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                log.info("synced %d commands to guild %s", len(synced), gid)
        else:
            synced = await self.tree.sync()
            log.info("synced %d global commands (may take ~1h to propagate)", len(synced))

        # Initial scrape if snapshot is empty
        if not (self.store.tasks or self.store.places):
            log.info("snapshot empty — running initial scrape")
            await self._refresh()

        # Schedule recurring refresh
        self.scheduler = AsyncIOScheduler()
        self.scheduler.add_job(
            self._refresh,
            trigger=CronTrigger.from_crontab(self.settings.refresh_cron),
            name="gzw_refresh",
            misfire_grace_time=300,
            coalesce=True,
        )
        self.scheduler.start()
        log.info("scheduler started: %s", self.settings.refresh_cron)

    async def _refresh(self) -> None:
        try:
            payload = await scrape_all(self.settings)
            new_store = GZWStore.from_dict(payload)
            new_store.save_snapshot(self.settings.snapshot_path)
            self.store = new_store
            log.info("refresh ok — %s", new_store.stats())
        except Exception:  # never let scheduler die
            log.exception("refresh failed")

    async def on_ready(self) -> None:
        log.info("logged in as %s (id=%s)", self.user, getattr(self.user, "id", "?"))
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="Lamang · /help",
            )
        )

    async def close(self) -> None:
        if self.scheduler:
            self.scheduler.shutdown(wait=False)
        await super().close()


# -----------------------------------------------------------------------------
def main() -> int:
    settings = config.load()
    setup_logging(settings.log_level)
    bot = GZWBot(settings)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _stop(*_):
        log.info("shutting down")
        loop.create_task(bot.close())

    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _stop)
            except NotImplementedError:
                pass

    try:
        loop.run_until_complete(bot.start(settings.token))
    except KeyboardInterrupt:
        loop.run_until_complete(bot.close())
    finally:
        loop.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
