"""One-shot scraper CLI.

    python scripts/scrape.py            # scrape and save snapshot.json
    python scripts/scrape.py --dump out.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Allow `python scripts/scrape.py` from project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot import config  # noqa: E402
from bot.scrapers.gzwtacmap import scrape_all  # noqa: E402


async def _run(out: Path | None) -> int:
    s = config.load()
    payload = await scrape_all(s)
    target = out or s.snapshot_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {target} — {sum(len(v) for v in payload.values() if isinstance(v, list))} entities")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dump", type=Path, default=None, help="alternate output path")
    args = p.parse_args()
    return asyncio.run(_run(args.dump))


if __name__ == "__main__":
    raise SystemExit(main())
