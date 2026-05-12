"""Text helpers — ASCII tactical UI, pagination, fuzzy matching, slugs."""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable, List, Sequence


# --- ASCII / tactical decoration ---------------------------------------------

CLASSIFIED_BAR = "▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱"
DASH_BAR = "─" * 28
HEAVY_BAR = "━" * 28


def banner(label: str, *, width: int = 28) -> str:
    """Tactical-looking centered banner: ── INTEL — TASK ──"""
    label = f" {label.upper()} "
    pad = max(0, (width - len(label))) // 2
    return "─" * pad + label + "─" * (width - pad - len(label))


def code_block(text: str, lang: str = "") -> str:
    """Wrap in a Discord codeblock. Empty lang = no syntax."""
    return f"```{lang}\n{text}\n```"


def kv_table(pairs: Sequence[tuple[str, str]], *, key_w: int = 12) -> str:
    """Aligned key/value pairs inside a code block — feels like a HUD."""
    rows = []
    for k, v in pairs:
        k = (k or "").strip()
        v = (v or "—").strip()
        rows.append(f"{k.ljust(key_w)} {v}")
    return code_block("\n".join(rows))


def progress_bar(done: int, total: int, *, width: int = 16) -> str:
    if total <= 0:
        return "░" * width + "  0%"
    pct = max(0.0, min(1.0, done / total))
    filled = int(round(pct * width))
    return "█" * filled + "░" * (width - filled) + f"  {int(pct*100):>3}%"


# --- Slug / search helpers ---------------------------------------------------

def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value


def truncate(s: str, limit: int, suffix: str = "…") -> str:
    if len(s) <= limit:
        return s
    return s[: max(0, limit - len(suffix))].rstrip() + suffix


def chunk(seq: Sequence, size: int) -> Iterable[List]:
    for i in range(0, len(seq), size):
        yield list(seq[i : i + size])


def safe_field(value: str | None, *, limit: int = 1024) -> str:
    """Discord embed field values cap at 1024. Always returns a non-empty string."""
    if not value:
        return "—"
    return truncate(value, limit)
