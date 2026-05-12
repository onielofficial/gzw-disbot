"""/task — search, list, filter Gray Zone Warfare tasks."""
from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from ..config import load
from ..utils.embeds import embed_task, embed_search_results, embed_error
from ..utils.map_render import render_task_map
from ._shared import _fuzzy_pick, store

logger = logging.getLogger(__name__)


def _objective_points(task: dict, places: list[dict]) -> list[tuple[float, float]]:
    """Resolve (x, y) pixel coords for a task's objectives.

    Prefers per-objective ``x``/``y`` (filled by the Playwright scraper).
    Falls back to looking up the linked Place's ``coords`` string ("x,y").
    Silently skips any objective whose coords can't be resolved.
    """
    by_id = {str(p.get("id")): p for p in places if p.get("id") is not None}
    points: list[tuple[float, float]] = []
    for o in task.get("objectives") or []:
        x, y = o.get("x"), o.get("y")
        if x is not None and y is not None:
            try:
                points.append((float(x), float(y)))
                continue
            except (TypeError, ValueError):
                pass
        pid = o.get("place_id")
        if not pid:
            continue
        place = by_id.get(str(pid))
        if not place or not place.get("coords"):
            continue
        parts = str(place["coords"]).split(",")
        if len(parts) != 2:
            continue
        try:
            points.append((float(parts[0].strip()), float(parts[1].strip())))
        except ValueError:
            continue
    return points


class Tasks(commands.GroupCog, name="task", description="Look up GZW tasks"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.s = load()

    async def _maybe_attach_map(self, interaction: discord.Interaction, task: dict) -> None:
        """Render and follow-up with the objective map crop. No-op on failure."""
        st = store(self.bot)
        points = _objective_points(task, st.places)
        if not points:
            return
        try:
            file = await render_task_map(
                points,
                data_dir=self.s.data_dir,
                map_slug=self.s.map_slug,
                base_image_url=self.s.map_base_image_url or None,
                user_agent=self.s.user_agent,
                filename=f"{task.get('slug') or 'task'}-map.png",
            )
        except Exception:
            logger.exception("map render crashed for %s", task.get("slug"))
            return
        if file is None:
            return
        try:
            await interaction.followup.send(file=file)
        except discord.HTTPException as exc:
            logger.warning("failed to send map for %s: %s", task.get("slug"), exc)

    # -------- /task search --------
    @app_commands.command(name="search", description="Find a task by name")
    @app_commands.describe(query="Task name (partial match works)")
    async def search(self, interaction: discord.Interaction, query: str) -> None:
        st = store(self.bot)
        # exact slug first
        t = st.task_by_slug(query)
        if not t:
            hits = [h for h in st.search(query) if h["kind"] == "task"]
            if not hits:
                await interaction.response.send_message(
                    embed=embed_error(f"No task matched '{query}'."), ephemeral=True
                )
                return
            if len(hits) > 1 and hits[0]["score"] < 90:
                await interaction.response.send_message(embed=embed_search_results(query, hits))
                return
            t = st.task_by_slug(hits[0]["ref"])
        if not t:
            await interaction.response.send_message(embed=embed_error("Task not found."), ephemeral=True)
            return
        await interaction.response.send_message(embed=embed_task(t, base_url=self.s.base_url))
        await self._maybe_attach_map(interaction, t)

    @search.autocomplete("query")
    async def _ac_search(self, interaction: discord.Interaction, current: str):
        st = store(self.bot)
        items = [(t.get("name") or t.get("slug", "?"), t.get("slug", "")) for t in st.tasks]
        return _fuzzy_pick(items, current)

    # -------- /task list --------
    @app_commands.command(name="list", description="List tasks filtered by trader/type/faction")
    @app_commands.describe(
        trader="e.g. Handshake, Gunny, Lab Rat, Artisan, Banshee",
        type="main, side, contract",
        faction="LRI, Mithras, CSI",
        limit="How many to show (max 25)",
    )
    async def list_(
        self,
        interaction: discord.Interaction,
        trader: Optional[str] = None,
        type: Optional[str] = None,
        faction: Optional[str] = None,
        limit: app_commands.Range[int, 1, 25] = 10,
    ) -> None:
        st = store(self.bot)
        items = st.filter_tasks(trader=trader, type_=type, faction=faction)
        if not items:
            await interaction.response.send_message(
                embed=embed_error("No tasks match those filters."), ephemeral=True
            )
            return
        items = items[:limit]
        hits = [
            {"kind": "task", "name": f"{(t.get('type') or 'main')[:1].upper()}  {t.get('name','?')}",
             "ref": t.get("slug", ""), "score": None}
            for t in items
        ]
        embed = embed_search_results(
            f"trader={trader or '*'} type={type or '*'} faction={faction or '*'}", hits
        )
        embed.title = f"❉  Task list · {len(items)} hits"
        await interaction.response.send_message(embed=embed)

    @list_.autocomplete("trader")
    async def _ac_trader(self, interaction: discord.Interaction, current: str):
        names = ["Handshake", "Gunny", "Lab Rat", "Artisan", "Banshee"]
        return _fuzzy_pick([(n, n) for n in names], current)

    @list_.autocomplete("type")
    async def _ac_type(self, interaction: discord.Interaction, current: str):
        return _fuzzy_pick([("Main", "main"), ("Side", "side"), ("Contract", "contract")], current)

    @list_.autocomplete("faction")
    async def _ac_faction(self, interaction: discord.Interaction, current: str):
        return _fuzzy_pick([("LRI", "LRI"), ("Mithras", "Mithras"), ("CSI", "CSI")], current)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Tasks(bot))
