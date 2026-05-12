# What it can do — and what it can't

This is the honest list. Cross-checked against the actual code in `bot/`.

## ✓ Can do

- **Task lookup** by name with fuzzy matching, autocomplete on every text input.
- **Task filtering** by trader (Handshake / Gunny / Lab Rat / Artisan / Banshee), type (main / side / contract), faction (LRI / Mithras / CSI).
- **Key lookup** by name + region filter; embeds list every door each key opens.
- **Place / POI lookup** by numeric ID (`1373`) or name; embeds include nearest LZ + related tasks.
- **Landing Zones (`/lz`)** and **Combat Outposts (`/cop`)** convenience listings.
- **Trader dossiers** with role, callsign, faction, specialties, derived task counts.
- **Faction dossiers** for both PMCs and hostile groups, with HQ / area-of-responsibility / threat.
- **Universal fuzzy `/search`** across tasks/keys/places/traders/factions in a single embed.
- **Per-user operator tracker** — task progress + key wallet, persisted in SQLite, ephemeral replies so it doesn't spam channels.
- **GZW-themed embeds** — military palette, ASCII banners, HUD-aligned key/value blocks, classification footers, glyph-prefixed titles. No HTML/CSS used; all rendering goes through `discord.Embed`.
- **Cron-scheduled refresh** of the snapshot every 6h (configurable). On-demand `/refresh` for owners.
- **Defensive scraping** — Next.js `__NEXT_DATA__` first, regex sniffing of streamed Next chunks second, BeautifulSoup HTML last.
- **Polite scraping** — concurrency cap, jittered delays, exponential backoff, identifiable User-Agent.
- **Snapshot cache** — JSON on disk; bot keeps serving last-known-good data if a refresh fails.
- **Local fixtures** — seed the bot fully offline via `scripts/seed_from_fixtures.py` for development or demos.

## ✗ Cannot do

- **No image rendering of the map.** The interactive map is a Canvas WebGL view; we link to it instead. Discord won't render it as-is.
- **Won't bypass paywalls / login.** gzwtacmap.com is public; if it ever requires auth, the scraper just fails and we serve the cached snapshot.
- **No video guides inline.** The website embeds YouTube videos; we surface the URL, Discord renders the unfurl, but the bot itself doesn't play media.
- **No party / clan-wide tracker.** The tracker is per-user. Cross-user dashboards aren't implemented (DB schema can be extended easily — see `bot/utils/db.py`).
- **No notifications when a task changes.** Refresh is silent. A diff-and-announce feature would need a new cog and a `last_run` table — not built yet.
- **No database migrations.** Schemas are idempotent CREATEs; if you add columns, drop the local SQLite files or write a manual ALTER.
- **No multi-map support.** `MAP_SLUG` is a single value (default `lamang`). When a second map ships in-game, you'll add a slug parameter to commands.
- **Doesn't host gzwtacmap.com data.** The bot scrapes once per refresh; it does not redistribute the dataset, mirror images, or expose a public API.

## Soft limits / tuning knobs

| Setting                | Default       | Effect                                       |
|------------------------|---------------|----------------------------------------------|
| `SCRAPE_CONCURRENCY`   | 4             | Max in-flight requests to gzwtacmap.com.     |
| `SCRAPE_DELAY_MS`      | 400           | Base inter-request delay (jittered).         |
| `CACHE_TTL_HOURS`      | 12            | Hint for refresh logic (cron is the truth).  |
| `REFRESH_CRON`         | `0 */6 * * *` | Cron schedule for the periodic refresh.      |
| `DEV_GUILD_IDS`        | _empty_       | Comma-separated guild IDs for instant sync.  |

## Discord limits we respect

- Embed title ≤ 256, description ≤ 4096, field value ≤ 1024 (`safe_field()` truncates).
- Autocomplete returns ≤ 25 choices.
- Slash commands per guild ≤ 100 (we ship ~20).

## Things we deliberately did **not** do

- A web dashboard. The bot is Discord-only by design; if you want a dashboard, point a different app at the same SQLite files.
- Posting embeds with custom HTML/CSS. Discord doesn't support it. The "tactical UI" is built entirely with embed primitives + ASCII inside codeblocks.
- Logging into gzwtacmap.com to read protected data. There is no protected data on that site, and we don't impersonate users.
