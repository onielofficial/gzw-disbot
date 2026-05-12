"""/faction — PMC + hostile faction dossiers."""
from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from ..utils.embeds import embed_faction, embed_search_results, embed_error
from ._shared import _fuzzy_pick, store


class Factions(commands.GroupCog, name="faction", description="Faction dossiers"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="info", description="Show a faction dossier")
    @app_commands.describe(name="Faction name")
    async def info(self, interaction: discord.Interaction, name: str) -> None:
        st = store(self.bot)
        target = next(
            (f for f in st.factions if name.lower() in f.get("name", "").lower()),
            None,
        )
        if not target:
            await interaction.response.send_message(
                embed=embed_error(f"Unknown faction '{name}'."), ephemeral=True
            )
            return
        await interaction.response.send_message(embed=embed_faction(target))

    @info.autocomplete("name")
    async def _ac(self, interaction: discord.Interaction, current: str):
        st = store(self.bot)
        items = [(f.get("name", "?"), f.get("name", "")) for f in st.factions]
        return _fuzzy_pick(items, current)

    @app_commands.command(name="list", description="List PMC or hostile factions")
    @app_commands.describe(type="pmc or hostile")
    async def list_(self, interaction: discord.Interaction, type: Optional[str] = None) -> None:
        st = store(self.bot)
        items = st.factions
        if type:
            items = [f for f in items if (f.get("type") or "").lower() == type.lower()]
        hits = [
            {"kind": (f.get("type") or "?").upper(), "name": f.get("name", "?"), "ref": f.get("name", ""), "score": None}
            for f in items
        ]
        embed = embed_search_results(f"type={type or '*'}", hits)
        embed.title = f"❖  Factions · {len(items)} known"
        await interaction.response.send_message(embed=embed)

    @list_.autocomplete("type")
    async def _ac_type(self, interaction: discord.Interaction, current: str):
        return _fuzzy_pick([("PMC", "pmc"), ("Hostile", "hostile")], current)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Factions(bot))
