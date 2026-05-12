# Deployment

## 1) Local (dev)

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env             # fill DISCORD_TOKEN + DEV_GUILD_IDS
python scripts/seed_from_fixtures.py
python -m bot.main
```

Slash commands sync to `DEV_GUILD_IDS` instantly. Leave the env empty for global sync (~1h).

## 2) systemd (Linux)

```ini
# /etc/systemd/system/gzw-disbot.service
[Unit]
Description=GZW Tac DisBot
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/gzw-disbot
EnvironmentFile=/opt/gzw-disbot/.env
ExecStart=/opt/gzw-disbot/.venv/bin/python -m bot.main
Restart=on-failure
RestartSec=5
User=gzw

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now gzw-disbot
journalctl -u gzw-disbot -f
```

## 3) Docker

`Dockerfile` (already in repo):

```bash
docker build -t gzw-disbot .
docker run --rm --name gzw-disbot \
    --env-file .env \
    -v $PWD/data:/app/data \
    gzw-disbot
```

Persisting `./data` keeps the cache snapshot + tracker DB across container restarts.

## 4) Discord application setup

1. https://discord.com/developers/applications → New Application.
2. **Bot** tab → Reset Token → put it in `.env`.
3. **Privileged Intents** — none required. (We use slash commands only.)
4. **OAuth2 → URL Generator** → scopes: `bot`, `applications.commands`. Bot Permissions: *Send Messages*, *Embed Links*, *Use Slash Commands*. Invite to your test guild.

## 5) Health checks

- `journalctl -u gzw-disbot -f` shows `loaded cog`, `synced N commands`, `refresh ok — {…}` on a healthy boot.
- `data/snapshot.json` updates every refresh.
- `/ping` returns latency.
- `/refresh` (owner) forces a re-scrape and reports new entity counts.
