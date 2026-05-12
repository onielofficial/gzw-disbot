"""/place — POI / objective location lookup."""
from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from ..config import load
from ..data.static import REGIONS
from ..utils.embeds import embed_place, embed_search_results, embed_error
from ._shared import _fuzzy_pick, store


class Places(commands.GroupCog, name="place", description="Look up GZW places (POIs)"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.s = load()

    @app_commands.command(name="search", description="Find a place by name or ID")
    @app_commands.describe(query="Place name or numeric place id (e.g. 1373)")
    async def search(self, interaction: discord.Interaction, query: str) -> None:
        st = store(self.bot)
        # numeric? -> id lookup
        p = st.place_by_id(query) if query.isdigit() else None
        if not p:
            hits = [h for h in st.search(query) if h["kind"] == "place"]
            if not hits:
                await interaction.response.send_message(
                    embed=embed_error(f"No place matched '{query}'."), ephemeral=True
                )
                return
            if len(hits) > 1 and hits[0]["score"] < 90:
                await interaction.response.send_message(embed=embed_search_results(query, hits))
                return
            p = st.place_by_id(hits[0]["ref"])
        if not p:
            await interaction.response.send_message(embed=embed_error("Place not found."), ephemeral=True)
            return
        await interaction.response.send_message(embed=embed_place(p, base_url=self.s.base_url))

    @search.autocomplete("query")
    async def _ac(self, interaction: discord.Interaction, current: str):
        st = store(self.bot)
        items = [(p.get("name", "?"), str(p.get("id", ""))) for p in st.places]
        return _fuzzy_pick(items, current)

    @app_commands.command(name="list", description="List places by region or group")
    @app_commands.describe(region="Region name", group="Group name (e.g. Landing Zones)", limit="Max 25")
    async def list_(
        self,
        interaction: discord.Interaction,
        region: Optional[str] = None,
        group: Optional[str] = None,
        limit: app_commands.Range[int, 1, 25] = 12,
    ) -> None:
        st = store(self.bot)
        items = st.filter_places(group=group, region=region)[:limit]
        if not items:
            await interaction.response.send_message(
                embed=embed_error("No places match."), ephemeral=True
            )
            return
        hits = [{"kind": "place", "name": p.get("name", "?"), "ref": str(p.get("id")), "score": None} for p in items]
        embed = embed_search_results(f"region={region or '*'} group={group or '*'}", hits)
        embed.title = f"◬  Place list · {len(items)} hits"
        await interaction.response.send_message(embed=embed)

    @list_.autocomplete("region")
    async def _ac_region(self, interaction: discord.Interaction, current: str):
        return _fuzzy_pick([(r, r) for r in REGIONS], current)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Places(bot))
