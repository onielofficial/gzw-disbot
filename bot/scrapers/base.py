"""Base async HTTP fetcher with retries, polite delay, and error wrapping."""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)


class FetchError(Exception):
    pass


class HttpFetcher:
    """Polite async HTTP client.

    - one shared session
    - configurable concurrency via semaphore
    - jittered delay between requests
    - simple retry-with-backoff on transient errors
    """

    def __init__(
        self,
        *,
        user_agent: str,
        concurrency: int = 4,
        delay_ms: int = 400,
        timeout_s: int = 20,
    ) -> None:
        self._user_agent = user_agent
        self._sema = asyncio.Semaphore(concurrency)
        self._delay_ms = delay_ms
        self._timeout = aiohttp.ClientTimeout(total=timeout_s)
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> "HttpFetcher":
        self._session = aiohttp.ClientSession(
            timeout=self._timeout,
            headers={
                "User-Agent": self._user_agent,
                "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.7",
            },
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def get_text(self, url: str, *, retries: int = 3) -> str:
        if not self._session:
            raise RuntimeError("HttpFetcher used outside of `async with`")
        backoff = 0.8
        last_exc: Exception | None = None
        async with self._sema:
            for attempt in range(1, retries + 1):
                try:
                    async with self._session.get(url) as resp:
                        if resp.status >= 400:
                            raise FetchError(f"{resp.status} {url}")
                        text = await resp.text()
                        await asyncio.sleep((self._delay_ms / 1000) + random.uniform(0, 0.2))
                        return text
                except (aiohttp.ClientError, asyncio.TimeoutError, FetchError) as exc:
                    last_exc = exc
                    logger.warning("fetch %s attempt %d/%d failed: %s", url, attempt, retries, exc)
                    await asyncio.sleep(backoff)
                    backoff *= 2
            raise FetchError(f"giving up: {last_exc} ({url})")
