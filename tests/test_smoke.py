"""Smoke tests — designed to run with only stdlib + bs4 + lxml available.

These don't need discord.py / pydantic / aiohttp / rapidfuzz; they exercise
the parts of the bot that have no external runtime deps.

Run with:
    python -m unittest tests.test_smoke
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TextHelpers(unittest.TestCase):
    def test_slugify(self):
        from bot.utils.text import slugify
        self.assertEqual(slugify("Tiger Bay Armory Key"), "tiger-bay-armory-key")
        self.assertEqual(slugify("Hunter's Paradise"), "hunter-s-paradise")
        self.assertEqual(slugify("YBL-1   Bunker"), "ybl-1-bunker")

    def test_truncate(self):
        from bot.utils.text import truncate
        self.assertEqual(truncate("hello", 10), "hello")
        self.assertTrue(truncate("a" * 100, 20).endswith("…"))
        self.assertLessEqual(len(truncate("a" * 100, 20)), 20)

    def test_kv_table(self):
        from bot.utils.text import kv_table
        s = kv_table([("TRADER", "Gunny"), ("TYPE", "main")])
        self.assertIn("TRADER", s)
        self.assertIn("Gunny", s)
        self.assertIn("```", s)

    def test_progress_bar(self):
        from bot.utils.text import progress_bar
        self.assertIn("0%", progress_bar(0, 0))
        self.assertIn("50%", progress_bar(5, 10))
        self.assertIn("100%", progress_bar(10, 10))

    def test_safe_field(self):
        from bot.utils.text import safe_field
        self.assertEqual(safe_field(None), "—")
        self.assertEqual(safe_field(""), "—")
        self.assertEqual(safe_field("x"), "x")
        long = "a" * 2000
        self.assertLessEqual(len(safe_field(long, limit=1024)), 1024)

    def test_banner(self):
        from bot.utils.text import banner
        out = banner("intel — task brief")
        self.assertIn("INTEL — TASK BRIEF", out)


class JsonldHelpers(unittest.TestCase):
    def test_parse_next_data(self):
        from bot.scrapers.jsonld import parse_next_data
        html = """
        <html><body>
        <script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"task":{"name":"Incognito"}}}}</script>
        </body></html>
        """
        out = parse_next_data(html)
        self.assertEqual(out["props"]["pageProps"]["task"]["name"], "Incognito")

    def test_parse_next_data_missing(self):
        from bot.scrapers.jsonld import parse_next_data
        self.assertEqual(parse_next_data("<html></html>"), {})

    def test_deep_find_lists(self):
        from bot.scrapers.jsonld import deep_find_lists
        node = {
            "props": {
                "pageProps": {
                    "tasks": [{"slug": "a", "name": "A"}, {"slug": "b", "name": "B"}],
                    "extras": {
                        "items": [{"slug": "c", "name": "C"}],
                    },
                }
            }
        }
        out = deep_find_lists(node, key_hints=("tasks",))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][0]["slug"], "a")


class FixturesShape(unittest.TestCase):
    def _load(self, name):
        return json.loads((ROOT / "fixtures" / name).read_text(encoding="utf-8"))

    def test_tasks(self):
        items = self._load("sample_tasks.json")
        self.assertGreater(len(items), 0)
        for t in items:
            self.assertIn("slug", t)
            self.assertIn("name", t)

    def test_keys(self):
        items = self._load("sample_keys.json")
        for k in items:
            self.assertIn("slug", k)
            self.assertIn("name", k)
            self.assertIsInstance(k.get("doors", []), list)

    def test_places(self):
        items = self._load("sample_places.json")
        for p in items:
            self.assertIn("id", p)
            self.assertIn("name", p)


class StaticData(unittest.TestCase):
    def test_traders(self):
        from bot.data.static import TRADERS
        names = {t["name"] for t in TRADERS}
        for required in ("Handshake", "Gunny", "Lab Rat", "Artisan", "Banshee"):
            self.assertIn(required, names)

    def test_factions(self):
        from bot.data.static import FACTIONS
        types = {f["type"] for f in FACTIONS}
        self.assertEqual(types, {"pmc", "hostile"})


class ColorPalette(unittest.TestCase):
    def test_trader_colors(self):
        from bot.utils.colors import color_for_trader, GZW_OLIVE
        self.assertIsInstance(color_for_trader("Gunny"), int)
        self.assertEqual(color_for_trader(None), GZW_OLIVE)
        self.assertEqual(color_for_trader("UNKNOWN_TRADER"), GZW_OLIVE)

    def test_task_type_colors(self):
        from bot.utils.colors import color_for_task_type, GZW_OLIVE
        self.assertEqual(color_for_task_type(None), GZW_OLIVE)
        self.assertNotEqual(color_for_task_type("contract"), GZW_OLIVE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
