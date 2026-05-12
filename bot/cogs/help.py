"""/help — main briefing embed."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from ..utils.embeds import embed_help


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show GZW Tac DisBot briefing")
    async def help_cmd(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(embed=embed_help(), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Help(bot))
