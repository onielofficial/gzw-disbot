"""/map — quick map link + cache stats."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from ..config import load
from ..utils.embeds import base_embed, GLYPH
from ..utils.text import banner, code_block, kv_table
from ..utils import colors
from ._shared import store


class Maps(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.s = load()

    @app_commands.command(name="map", description="Open the interactive map (gzwtacmap.com)")
    async def map_(self, interaction: discord.Interaction) -> None:
        st = store(self.bot)
        s = self.s
        url = f"{s.base_url}/maps/{s.map_slug}"
        e = base_embed(
            title=f"{GLYPH['intel']}  Lamang · Tactical Map",
            color=colors.GZW_OLIVE,
            author_kind="MAP · INTERACTIVE",
            url=url,
        )
        stats = st.stats()
        e.description = (
            f"`{banner('intel cache')}`\n"
            + kv_table([
                ("TASKS", str(stats["tasks"])),
                ("KEYS", str(stats["keys"])),
                ("PLACES", str(stats["places"])),
                ("GROUPS", str(stats["groups"])),
                ("TRADERS", str(stats["traders"])),
                ("FACTIONS", str(stats["factions"])),
            ])
            + f"\n[Open the interactive map ▸]({url})"
        )
        await interaction.response.send_message(embed=e)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Maps(bot))
