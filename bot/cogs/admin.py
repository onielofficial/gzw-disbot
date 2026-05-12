"""/refresh, /reload — admin operational commands."""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from ..config import load
from ..scrapers.gzwtacmap import scrape_all
from ..utils.cache import GZWStore
from ..utils.embeds import base_embed, GLYPH
from ..utils.text import code_block
from ..utils import colors

log = logging.getLogger(__name__)


def _is_owner(interaction: discord.Interaction) -> bool:
    bot: commands.Bot = interaction.client  # type: ignore
    if bot.application is None:
        return False
    return interaction.user.id == (bot.application.owner.id if bot.application.owner else 0)


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.s = load()

    @app_commands.command(name="refresh", description="(owner) Re-scrape gzwtacmap.com")
    async def refresh(self, interaction: discord.Interaction) -> None:
        if not _is_owner(interaction):
            await interaction.response.send_message("Owner only.", ephemeral=True)
            return
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            payload = await scrape_all(self.s)
            new_store = GZWStore.from_dict(payload)
            new_store.save_snapshot(self.s.snapshot_path)
            self.bot.store = new_store  # type: ignore[attr-defined]
            stats = new_store.stats()
            e = base_embed(
                title=f"{GLYPH['ok']}  Refresh complete",
                color=colors.SAFE_GREEN,
                author_kind="ADMIN · REFRESH",
            )
            e.description = code_block(
                "\n".join(f"{k:<10} {v}" for k, v in stats.items())
            )
            await interaction.followup.send(embed=e, ephemeral=True)
        except Exception as exc:
            log.exception("refresh failed")
            await interaction.followup.send(content=f"Refresh failed: {exc}", ephemeral=True)

    @app_commands.command(name="ping", description="Latency check")
    async def ping(self, interaction: discord.Interaction) -> None:
        ms = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"`pong` · {ms} ms", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
