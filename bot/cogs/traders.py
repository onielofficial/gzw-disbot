"""/trader — vendor dossiers (Handshake, Gunny, Lab Rat, Artisan, Banshee)."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from ..utils.embeds import embed_trader, embed_error
from ._shared import _fuzzy_pick, store


class Traders(commands.GroupCog, name="trader", description="Trader dossiers"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="info", description="Show a trader's dossier")
    @app_commands.describe(name="Trader name")
    async def info(self, interaction: discord.Interaction, name: str) -> None:
        st = store(self.bot)
        target = next(
            (t for t in st.traders if t.get("name", "").lower() == name.lower()),
            None,
        )
        if not target:
            await interaction.response.send_message(
                embed=embed_error(f"Unknown trader '{name}'."), ephemeral=True
            )
            return
        # Augment with task counts from cached tasks
        tcount = sum(1 for x in st.tasks if (x.get("trader") or "").lower() == name.lower())
        target = {**target, "task_count": tcount or target.get("task_count")}
        await interaction.response.send_message(embed=embed_trader(target))

    @info.autocomplete("name")
    async def _ac(self, interaction: discord.Interaction, current: str):
        st = store(self.bot)
        items = [(t.get("name", "?"), t.get("name", "")) for t in st.traders]
        return _fuzzy_pick(items, current)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Traders(bot))
