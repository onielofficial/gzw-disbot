"""/lz and /cop — landing zones + combat outposts."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from ..config import load
from ..utils.embeds import embed_lz, embed_search_results, embed_error
from ._shared import store


def _list_for_group(places: list[dict], group_name: str) -> list[dict]:
    return [p for p in places if (p.get("group") or "").lower() == group_name.lower()]


class Zones(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.s = load()

    @app_commands.command(name="lz", description="List Landing Zones on Lamang")
    async def lz(self, interaction: discord.Interaction) -> None:
        st = store(self.bot)
        items = _list_for_group(st.places, "Landing Zones") or _list_for_group(st.places, "1")
        if not items:
            await interaction.response.send_message(
                embed=embed_error("No LZs cached yet — try `/refresh` (admin)."), ephemeral=True
            )
            return
        hits = [{"kind": "lz", "name": p.get("name", "?"), "ref": str(p.get("id")), "score": None} for p in items[:25]]
        embed = embed_search_results("group=Landing Zones", hits)
        embed.title = f"▲  Landing Zones · {len(items)} known"
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="cop", description="List Combat Outposts on Lamang")
    async def cop(self, interaction: discord.Interaction) -> None:
        st = store(self.bot)
        items = _list_for_group(st.places, "Combat Outposts") or _list_for_group(st.places, "38")
        if not items:
            await interaction.response.send_message(
                embed=embed_error("No COPs cached yet — try `/refresh` (admin)."), ephemeral=True
            )
            return
        hits = [{"kind": "cop", "name": p.get("name", "?"), "ref": str(p.get("id")), "score": None} for p in items[:25]]
        embed = embed_search_results("group=Combat Outposts", hits)
        embed.title = f"■  Combat Outposts · {len(items)} known"
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Zones(bot))
