# GZW Tac DisBot — Design

This is the architecture cheat-sheet. Read this first if you're going to
extend the bot, change the scraper, or tweak the UI.

## Goals

1. Surface gzwtacmap.com data (tasks, keys, places, groups) inside Discord with **zero website navigation** required.
2. Look like a Gray Zone Warfare in-game tactical briefing, using **Discord Embeds only** — no HTML/CSS, no images required.
3. Stay polite to gzwtacmap.com (low concurrency, jittered delays, cached snapshots).
4. Survive layout changes without crashing — defensive parsing, soft failures, last-good snapshot wins.
5. Give the player something the website doesn't: a **per-user operator tracker** with task/key progress.

## High-level flow

```
       ┌──────────────────────────────────────────┐
       │             Discord users                 │
       └──────────────────────┬───────────────────┘
                              │  slash commands
                              ▼
                    ┌────────────────────┐
                    │   GZWBot (main)    │
                    │  cogs/* registered │
                    └─────────┬──────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
   ┌─────────┐          ┌────────────┐        ┌──────────┐
   │ GZWStore │  ←load── │ snapshot   │  ←save─│ scrape_all │
   │ (memory) │          │ .json      │        │ scheduler  │
   └─────────┘          └────────────┘        └──────────┘
                              ▲                     │
                              │                     ▼
                              │           ┌────────────────────┐
                              │           │   gzwtacmap.com    │
                              │           │ (Next.js __NEXT_DATA__│
                              │           │  + HTML fallback)   │
                              │           └────────────────────┘
                              │
                       per-user data
                              ▼
                   ┌────────────────────┐
                   │  tracker.sqlite    │
                   │  (task / key state)│
                   └────────────────────┘
```

## Modules at a glance

- **`bot.main`** — wires Discord client + cogs + scheduler. Loads the snapshot at boot, kicks off a background refresh.
- **`bot.config`** — single source of truth for env vars / paths.
- **`bot.scrapers.gzwtacmap`** — async scraper. Prefers `__NEXT_DATA__`, falls back to HTML, never raises across the public API.
- **`bot.utils.cache.GZWStore`** — in-memory store + fuzzy search. The bot reads from this; the scheduler atomically replaces it.
- **`bot.utils.embeds`** — every embed flows through here. Re-skinning the bot = touching one file.
- **`bot.utils.db`** — SQLite helpers + schemas. `cache.sqlite` (scraped) and `tracker.sqlite` (per-user) are separate.
- **`bot.cogs.*`** — one `discord.py` cog per command group. Cogs are *thin*: parse args → look up in store → render via embeds.

## Why Discord Embeds only

Discord renders ASCII codeblocks consistently across desktop, web, and mobile. We lean on:

- Author line as a **classification banner** (`GZW · INTEL · TASK`)
- Title with a glyph prefix (`◉  Incognito`)
- Description = `banner()` + `kv_table()` HUD block, sometimes followed by prose
- Fields for objectives / rewards / prerequisites
- Footer for source citation + freshness timestamp

The result reads like an in-game intel briefing without any image hosting.

## Data refresh

- **Boot** — load `data/snapshot.json` if present.
- **Empty snapshot** — kick off `scrape_all()` immediately.
- **Cron** — `REFRESH_CRON` (default `0 */6 * * *`) re-runs `scrape_all()`. Failures are logged and ignored — the bot keeps serving the last good snapshot.
- **`/refresh`** — owner-only manual refresh.

## Polite-scraping rules

- Single shared `aiohttp.ClientSession`
- `asyncio.Semaphore` capping concurrency (default 4)
- Jittered delay between requests (default 400 ms ± 0–200 ms)
- Exponential backoff on transient errors (0.8 → 1.6 → 3.2 s)
- User-Agent identifies the bot + a contact email

## Failure modes

- **Scraper returns nothing** → snapshot stays as-is; commands keep working.
- **Discord API error** → cog logs and replies with `embed_error`.
- **DB locked** → SQLite WAL mode handles concurrent reads; tracker is per-user so write contention is rare.
- **Token missing / invalid** → `bot.main` raises at startup; user sees clear error.

## Extending

- New entity? Add a model in `bot/data/models.py`, scrape it in `bot/scrapers/gzwtacmap.py`, expose it on `GZWStore`, render via `bot/utils/embeds.py`, wire one cog under `bot/cogs/`. Append the cog to `COGS` in `bot/cogs/__init__.py`.
- New command? Subclass `commands.GroupCog` (for grouped) or `commands.Cog` (for top-level). Use `_fuzzy_pick` from `bot/cogs/_shared.py` for autocompletes.
- Different look? Edit `bot/utils/colors.py` + `bot/utils/embeds.py`. Don't touch cogs.
