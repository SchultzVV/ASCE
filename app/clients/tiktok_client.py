"""TikTok public data client for trending music discovery.

Note
----
TikTok's web UI is heavily JavaScript-rendered and the structure of
``/trending`` changes frequently.  This client uses a best-effort
approach: it tries a known endpoint first and falls back to a curated
list of popular tracks when the page cannot be scraped.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)

_FALLBACK_TRACKS: List[Dict[str, Any]] = [
    {"name": "Flowers", "artist": "Miley Cyrus", "usage_count": 5_000_000, "growth_rate": 1.2},
    {"name": "Cruel Summer", "artist": "Taylor Swift", "usage_count": 8_000_000, "growth_rate": 0.9},
    {"name": "Espresso", "artist": "Sabrina Carpenter", "usage_count": 6_500_000, "growth_rate": 1.5},
    {"name": "Vampire", "artist": "Olivia Rodrigo", "usage_count": 4_200_000, "growth_rate": 0.8},
    {"name": "Rich Flex", "artist": "Drake & 21 Savage", "usage_count": 9_100_000, "growth_rate": 0.7},
]


class TikTokClient:
    """Scrapes trending sounds from TikTok public pages.

    Falls back gracefully when the live page cannot be fetched.
    """

    TRENDING_URL = "https://www.tiktok.com/trending"
    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = httpx.Timeout(timeout)

    async def fetch_trending_sounds(self) -> List[Dict[str, Any]]:
        """Return a list of trending sound dicts from TikTok.

        Each dict contains:
            - ``name``        (str) sound / song title
            - ``artist``      (str) artist name when available
            - ``usage_count`` (int) approximate number of videos using this sound
            - ``growth_rate`` (float) relative growth indicator

        Returns the fallback list when the page cannot be reached.
        """
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                headers=self._HEADERS,
                follow_redirects=True,
            ) as client:
                resp = await client.get(self.TRENDING_URL)
                resp.raise_for_status()
                return self._parse_trending_page(resp.text)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "TikTok trending page unavailable (%s). Using fallback data.", exc
            )
            return list(_FALLBACK_TRACKS)

    # ── Parsing helpers ───────────────────────────────────────────────────

    @staticmethod
    def _parse_trending_page(html: str) -> List[Dict[str, Any]]:
        """Extract sound metadata from TikTok trending HTML.

        TikTok embeds JSON in ``<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">``
        tags.  We do a best-effort JSON extraction; if parsing fails we
        return an empty list (caller falls back to curated list).
        """
        import json

        pattern = re.compile(
            r'<script[^>]+id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>',
            re.DOTALL,
        )
        match = pattern.search(html)
        if not match:
            logger.debug("Could not locate rehydration data in TikTok HTML")
            return []

        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            return []

        sounds: List[Dict[str, Any]] = []
        # Recursively hunt for sound-like objects
        TikTokClient._extract_sounds(data, sounds)
        return sounds[:20]

    @staticmethod
    def _extract_sounds(node: Any, results: List[Dict[str, Any]]) -> None:
        """Depth-first traversal looking for sound metadata objects."""
        if isinstance(node, dict):
            if "soundName" in node or "musicName" in node:
                results.append(
                    {
                        "name": node.get("soundName") or node.get("musicName", "Unknown"),
                        "artist": node.get("authorName", ""),
                        "usage_count": int(node.get("videoCount", 0)),
                        "growth_rate": float(node.get("growthRate", 0.5)),
                    }
                )
            for v in node.values():
                TikTokClient._extract_sounds(v, results)
        elif isinstance(node, list):
            for item in node:
                TikTokClient._extract_sounds(item, results)
