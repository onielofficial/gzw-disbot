"""/search — fuzzy search across tasks/keys/places/traders/factions."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from ..utils.embeds import embed_search_results
from ._shared import store


class Search(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="search", description="Search everything (tasks/keys/places/traders/factions)")
    @app_commands.describe(query="Anything", limit="How many results (1-15)")
    async def search(
        self,
        interaction: discord.Interaction,
        query: str,
        limit: app_commands.Range[int, 1, 15] = 10,
    ) -> None:
        st = store(self.bot)
        hits = st.search(query, limit=limit)
        await interaction.response.send_message(embed=embed_search_results(query, hits))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Search(bot))
