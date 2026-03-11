"""Instagram data client for detecting trending reels music.

Uses the Meta Graph API to inspect recent reels and surface the most
frequently used audio tracks.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any, Dict, List

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.facebook.com/v19.0"


class InstagramClient:
    """Fetches Instagram reels and extracts trending audio data."""

    def __init__(self) -> None:
        settings = get_settings()
        self._token = settings.access_token
        self._ig_user_id = settings.instagram_business_id
        self._timeout = httpx.Timeout(20.0)

    async def fetch_trending_music(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return trending music tracks found in recent Instagram reels.

        Queries the business account's media and aggregates audio metadata.

        Args:
            limit: Number of recent media items to inspect (default 50).

        Returns:
            List of dicts with ``name``, ``artist``, ``usage_count`` keys,
            sorted by usage_count descending.  Returns empty list when the
            account credentials are not configured.
        """
        if not self._token or not self._ig_user_id:
            logger.warning("Instagram credentials not configured; skipping IG music fetch")
            return []

        url = f"{GRAPH_BASE}/{self._ig_user_id}/media"
        params = {
            "fields": "id,media_type,timestamp,music_metadata",
            "limit": limit,
            "access_token": self._token,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to fetch Instagram media: %s", exc)
            return []

        return self._aggregate_tracks(data.get("data", []))

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _aggregate_tracks(media_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Aggregate audio track usage from media items."""
        counter: Counter = Counter()
        meta_map: Dict[str, Dict[str, Any]] = {}

        for item in media_items:
            music = item.get("music_metadata", {})
            audio = music.get("audio_asset", {})
            name = audio.get("title") or audio.get("display_name")
            artist = audio.get("artist_name", "")
            if not name:
                continue
            key = f"{name}|{artist}"
            counter[key] += 1
            if key not in meta_map:
                meta_map[key] = {"name": name, "artist": artist}

        results = []
        for key, count in counter.most_common():
            entry = dict(meta_map[key])
            entry["usage_count"] = count
            entry["growth_rate"] = 0.5  # placeholder; real growth needs time-series data
            results.append(entry)

        return results
