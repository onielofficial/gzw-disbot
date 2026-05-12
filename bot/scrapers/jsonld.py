"""Helpers to extract data embedded in modern web apps.

gzwtacmap.com is a Next.js app, so the data we want is almost always in:
  - <script id="__NEXT_DATA__" type="application/json">{...}</script>
  - <script type="application/ld+json">{...}</script> (JSON-LD)
  - <script>self.__next_f.push([...])</script>  (Next.js streaming chunks)

These helpers find and parse those payloads. They never raise on bad data,
they return {} so the scraper can fall back to HTML parsing.
"""
from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup

NEXT_DATA_RE = re.compile(
    r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)
NEXT_F_PUSH_RE = re.compile(
    r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', re.DOTALL
)


def parse_next_data(html: str) -> dict:
    m = NEXT_DATA_RE.search(html)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return {}


def parse_jsonld(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "{}")
            if isinstance(data, list):
                out.extend(d for d in data if isinstance(d, dict))
            elif isinstance(data, dict):
                out.append(data)
        except json.JSONDecodeError:
            continue
    return out


def parse_next_streamed(html: str) -> list[Any]:
    """Extract the JSON chunks that Next.js streams via `self.__next_f.push`.

    Returns a list of decoded items (often strings/objects). Caller is
    responsible for sniffing what's relevant.
    """
    chunks: list[Any] = []
    for m in NEXT_F_PUSH_RE.finditer(html):
        raw = m.group(1)
        # Unescape \" \\ \n that Next.js emits in the streamed strings.
        try:
            unescaped = bytes(raw, "utf-8").decode("unicode_escape")
        except UnicodeDecodeError:
            unescaped = raw
        chunks.append(unescaped)
    return chunks


def deep_find_lists(obj: Any, *, key_hints: tuple[str, ...]) -> list[list[dict]]:
    """Walk a nested structure and yank out all list[dict] values whose key
    name contains any of the hints (case-insensitive). Used to sniff
    `tasks`, `keys`, `places` arrays without knowing the exact shape.
    """
    found: list[list[dict]] = []
    hints = tuple(h.lower() for h in key_hints)

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if (
                    isinstance(v, list)
                    and v
                    and isinstance(v[0], dict)
                    and any(h in str(k).lower() for h in hints)
                ):
                    found.append(v)
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(obj)
    return found
