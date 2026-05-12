"""/key — search keys + their door locations."""
from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from ..config import load
from ..utils.embeds import embed_key, embed_search_results, embed_error
from ._shared import _fuzzy_pick, store


class Keys(commands.GroupCog, name="key", description="Look up GZW keys"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.s = load()

    @app_commands.command(name="search", description="Find a key by name")
    @app_commands.describe(query="Key name (partial match works)")
    async def search(self, interaction: discord.Interaction, query: str) -> None:
        st = store(self.bot)
        k = st.key_by_slug(query)
        if not k:
            hits = [h for h in st.search(query) if h["kind"] == "key"]
            if not hits:
                await interaction.response.send_message(
                    embed=embed_error(f"No key matched '{query}'."), ephemeral=True
                )
                return
            if len(hits) > 1 and hits[0]["score"] < 90:
                await interaction.response.send_message(embed=embed_search_results(query, hits))
                return
            k = st.key_by_slug(hits[0]["ref"])
        if not k:
            await interaction.response.send_message(embed=embed_error("Key not found."), ephemeral=True)
            return
        await interaction.response.send_message(embed=embed_key(k, base_url=self.s.base_url))

    @search.autocomplete("query")
    async def _ac(self, interaction: discord.Interaction, current: str):
        st = store(self.bot)
        items = [(k.get("name", k.get("slug", "?")), k.get("slug", "")) for k in st.keys]
        return _fuzzy_pick(items, current)

    @app_commands.command(name="list", description="List keys, optionally by region")
    @app_commands.describe(region="Region name (e.g. Tiger Bay)", limit="Max items (1-25)")
    async def list_(
        self,
        interaction: discord.Interaction,
        region: Optional[str] = None,
        limit: app_commands.Range[int, 1, 25] = 10,
    ) -> None:
        st = store(self.bot)
        items = st.keys
        if region:
            r = region.lower()
            items = [k for k in items if (k.get("region") or "").lower() == r]
        items = items[:limit]
        if not items:
            await interaction.response.send_message(
                embed=embed_error("No keys match those filters."), ephemeral=True
            )
            return
        hits = [{"kind": "key", "name": k.get("name", "?"), "ref": k.get("slug", ""), "score": None} for k in items]
        embed = embed_search_results(f"region={region or '*'}", hits)
        embed.title = f"⌬  Key list · {len(items)} hits"
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Keys(bot))
