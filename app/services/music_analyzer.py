"""Music analyzer service.

Aggregates trending music signals from TikTok and Instagram, scores each
track and returns an ordered list of the top N candidates.
"""

from __future__ import annotations

import logging
from typing import List

from app.clients.instagram_client import InstagramClient
from app.clients.tiktok_client import TikTokClient
from app.models.post import TrackInfo

logger = logging.getLogger(__name__)


class MusicAnalyzer:
    """Discovers and ranks trending music tracks.

    Score formula::

        viral_score = usage_count_norm * 0.5 + growth_rate_norm * 0.3 + regional_usage * 0.2

    Values are normalised to [0, 1] relative to the maximum observed value
    in the current batch.
    """

    def __init__(self) -> None:
        self._tiktok = TikTokClient()
        self._instagram = InstagramClient()

    async def get_top_tracks(self, top_n: int = 5) -> List[TrackInfo]:
        """Fetch, merge, score and return the top *top_n* trending tracks.

        Args:
            top_n: Number of tracks to return (default 5).

        Returns:
            List of :class:`~app.models.post.TrackInfo` objects sorted by
            ``viral_score`` descending.
        """
        tiktok_data, ig_data = await self._fetch_all()

        # Merge – TikTok tracks take the "tiktok" source, IG get "instagram"
        raw = []
        for item in tiktok_data:
            raw.append({**item, "source": "tiktok", "regional_usage": 0.5})
        for item in ig_data:
            raw.append({**item, "source": "instagram", "regional_usage": 0.7})

        if not raw:
            logger.warning("No trending music data available; returning empty list")
            return []

        tracks = self._score_tracks(raw)
        tracks.sort(key=lambda t: t.viral_score, reverse=True)
        return tracks[:top_n]

    # ── Internal helpers ──────────────────────────────────────────────────

    async def _fetch_all(self):
        """Concurrently fetch from all sources."""
        import asyncio

        tiktok_task = asyncio.create_task(self._tiktok.fetch_trending_sounds())
        ig_task = asyncio.create_task(self._instagram.fetch_trending_music())
        tiktok_data, ig_data = await asyncio.gather(tiktok_task, ig_task)
        return tiktok_data, ig_data

    @staticmethod
    def _score_tracks(raw: list) -> List[TrackInfo]:
        """Normalise raw signals and compute viral_score for each track."""
        max_usage = max((r.get("usage_count", 0) for r in raw), default=1) or 1
        max_growth = max((r.get("growth_rate", 0) for r in raw), default=1) or 1

        tracks: List[TrackInfo] = []
        for r in raw:
            usage_norm = r.get("usage_count", 0) / max_usage
            growth_norm = r.get("growth_rate", 0) / max_growth
            regional = r.get("regional_usage", 0.5)

            score = usage_norm * 0.5 + growth_norm * 0.3 + regional * 0.2

            tracks.append(
                TrackInfo(
                    name=r.get("name", "Unknown"),
                    artist=r.get("artist", ""),
                    source=r.get("source", ""),
                    usage_count=int(r.get("usage_count", 0)),
                    growth_rate=float(r.get("growth_rate", 0)),
                    regional_usage=float(regional),
                    viral_score=round(score, 4),
                )
            )
        return tracks
