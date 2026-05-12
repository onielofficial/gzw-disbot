"""/track — personal task & key progress tracker, persisted in SQLite."""
from __future__ import annotations

import json
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from ..config import load
from ..utils import db as dbu
from ..utils.embeds import embed_tracker, embed_error, embed_search_results
from ..utils.text import slugify
from ._shared import _fuzzy_pick, store


class Tracker(commands.GroupCog, name="track", description="Personal progress tracker"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.s = load()

    # -------- /track me --------
    @app_commands.command(name="me", description="Show your operator progress")
    async def me(self, interaction: discord.Interaction) -> None:
        st = store(self.bot)
        async with dbu.open_db(self.s.db_path, dbu.TRACKER_SCHEMA) as db:
            cur = await db.execute(
                "SELECT task_slug, status FROM task_progress WHERE user_id=?",
                (str(interaction.user.id),),
            )
            rows = await cur.fetchall()
            cur2 = await db.execute(
                "SELECT key_slug FROM owned_keys WHERE user_id=?",
                (str(interaction.user.id),),
            )
            keys = await cur2.fetchall()
            cur3 = await db.execute(
                "SELECT faction FROM users WHERE user_id=?", (str(interaction.user.id),)
            )
            user_row = await cur3.fetchone()

        done_tasks = sum(1 for r in rows if r["status"] == "done")
        recent = []
        for r in rows[-8:]:
            slug = r["task_slug"]
            t = st.task_by_slug(slug)
            recent.append({"name": (t.get("name") if t else slug), "done": r["status"] == "done"})

        summary = {
            "total_tasks": len(st.tasks),
            "done_tasks": done_tasks,
            "total_keys": len(st.keys),
            "owned_keys": len(keys),
            "faction": user_row["faction"] if user_row else None,
            "recent": recent,
        }
        await interaction.response.send_message(
            embed=embed_tracker(interaction.user.display_name, summary), ephemeral=True
        )

    # -------- /track set --------
    @app_commands.command(name="set", description="Mark a task or key as done / in_progress / abandoned")
    @app_commands.describe(
        kind="task or key",
        target="task slug or key slug (use the autocomplete)",
        status="done | in_progress | abandoned (tasks); owned | drop (keys)",
    )
    async def set_(
        self,
        interaction: discord.Interaction,
        kind: str,
        target: str,
        status: str,
    ) -> None:
        kind = kind.lower().strip()
        target = slugify(target)
        async with dbu.open_db(self.s.db_path, dbu.TRACKER_SCHEMA) as db:
            uid = str(interaction.user.id)
            # ensure user row
            await db.execute(
                "INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,)
            )
            if kind == "task":
                if status not in ("done", "in_progress", "abandoned"):
                    await interaction.response.send_message(
                        embed=embed_error("status must be done | in_progress | abandoned"),
                        ephemeral=True,
                    )
                    return
                await db.execute(
                    """INSERT INTO task_progress (user_id, task_slug, status)
                       VALUES (?, ?, ?)
                       ON CONFLICT(user_id, task_slug) DO UPDATE SET
                           status=excluded.status, updated_at=datetime('now')""",
                    (uid, target, status),
                )
            elif kind == "key":
                if status == "owned":
                    await db.execute(
                        "INSERT OR IGNORE INTO owned_keys (user_id, key_slug) VALUES (?, ?)",
                        (uid, target),
                    )
                elif status in ("drop", "lost"):
                    await db.execute(
                        "DELETE FROM owned_keys WHERE user_id=? AND key_slug=?", (uid, target)
                    )
                else:
                    await interaction.response.send_message(
                        embed=embed_error("status must be owned or drop"), ephemeral=True
                    )
                    return
            else:
                await interaction.response.send_message(
                    embed=embed_error("kind must be task or key"), ephemeral=True
                )
                return
            await db.commit()
        await interaction.response.send_message(
            content=f"✓  `{kind}` `{target}` → `{status}`", ephemeral=True
        )

    @set_.autocomplete("kind")
    async def _ac_kind(self, interaction: discord.Interaction, current: str):
        return _fuzzy_pick([("task", "task"), ("key", "key")], current)

    @set_.autocomplete("status")
    async def _ac_status(self, interaction: discord.Interaction, current: str):
        return _fuzzy_pick(
            [
                ("done (task)", "done"),
                ("in_progress (task)", "in_progress"),
                ("abandoned (task)", "abandoned"),
                ("owned (key)", "owned"),
                ("drop (key)", "drop"),
            ],
            current,
        )

    @set_.autocomplete("target")
    async def _ac_target(self, interaction: discord.Interaction, current: str):
        st = store(self.bot)
        # Suggest both tasks and keys; user knows which kind they picked.
        items = (
            [(t.get("name", "?") + "  · task", t.get("slug", "")) for t in st.tasks]
            + [(k.get("name", "?") + "  · key", k.get("slug", "")) for k in st.keys]
        )
        return _fuzzy_pick(items, current)

    # -------- /track faction --------
    @app_commands.command(name="faction", description="Set your operator's PMC faction")
    @app_commands.describe(name="LRI, Mithras, or CSI")
    async def faction(self, interaction: discord.Interaction, name: str) -> None:
        if not name:
            await interaction.response.send_message(embed=embed_error("name required"), ephemeral=True)
            return
        async with dbu.open_db(self.s.db_path, dbu.TRACKER_SCHEMA) as db:
            await db.execute(
                """INSERT INTO users (user_id, faction) VALUES (?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET faction=excluded.faction, updated_at=datetime('now')""",
                (str(interaction.user.id), name),
            )
            await db.commit()
        await interaction.response.send_message(content=f"Faction set: **{name}**", ephemeral=True)

    @faction.autocomplete("name")
    async def _ac_fac(self, interaction: discord.Interaction, current: str):
        return _fuzzy_pick([("LRI", "LRI"), ("Mithras", "Mithras"), ("CSI", "CSI")], current)

    # -------- /track reset --------
    @app_commands.command(name="reset", description="Wipe your tracker data (cannot be undone)")
    async def reset(self, interaction: discord.Interaction) -> None:
        uid = str(interaction.user.id)
        async with dbu.open_db(self.s.db_path, dbu.TRACKER_SCHEMA) as db:
            await db.execute("DELETE FROM task_progress WHERE user_id=?", (uid,))
            await db.execute("DELETE FROM objective_progress WHERE user_id=?", (uid,))
            await db.execute("DELETE FROM owned_keys WHERE user_id=?", (uid,))
            await db.execute("DELETE FROM users WHERE user_id=?", (uid,))
            await db.commit()
        await interaction.response.send_message(
            content="Tracker wiped. Stay frosty.", ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Tracker(bot))
