# GZW Tac DisBot

A Discord bot that mirrors the intel on **gzwtacmap.com** for *Gray Zone Warfare* players, served as a Discord-Embed-only tactical briefing styled after the in-game UI.

> ป้อน `/help` ใน Discord หลังเชิญบอทเข้าเซิร์ฟเวอร์เพื่อดู briefing เต็ม

## Quick start

```bash
git clone <this repo>
cd gzw-disbot

python -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # ใส่ DISCORD_TOKEN + DEV_GUILD_IDS
python scripts/seed_from_fixtures.py   # (ทางเลือก) seed snapshot เพื่อทดลองใช้
python -m bot.main
```

## Highlights

- 11 slash-command groups: `/task`, `/key`, `/place`, `/lz`, `/cop`, `/trader`, `/faction`, `/search`, `/track`, `/map`, `/refresh`
- **Discord Embed-only** UI styled after Grayzone Warfare HUD — military olive palette, ASCII tactical banners, `kv_table`-shaped HUD fields, classification footers
- Fuzzy autocomplete on every searchable parameter (rapidfuzz)
- Async scraper that prefers Next.js `__NEXT_DATA__` and falls back to HTML/regex sniffing — survives most layout changes
- Persistent SQLite cache + JSON snapshot, refreshed on a cron (default every 6h)
- Per-user **operator tracker** — task progress + key wallet, kept in a separate SQLite db

## Project layout

```
bot/
  main.py            entry point (asyncio + apscheduler)
  config.py          env loader / paths
  cogs/              one slash-command group per file
  data/              pydantic models + curated static dossiers
  scrapers/          gzwtacmap scraper + Next.js helpers
  utils/             colors, embeds, text, db, cache
fixtures/            sample JSON for offline demo
scripts/
  scrape.py          one-shot scraper CLI
  seed_from_fixtures.py
docs/                DESIGN, CAPABILITIES, COMMANDS, DEPLOYMENT
flow.html            interactive setup checklist (open in browser)
```

ดู `docs/DESIGN.md`, `docs/COMMANDS.md`, และ `docs/CAPABILITIES.md` สำหรับรายละเอียดทั้งหมด
และเปิด `flow.html` ในเบราเซอร์เพื่อใช้ checklist ติดตั้ง / รันแบบกดทีละขั้น
