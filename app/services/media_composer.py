"""Media composer service.

Combines a product image with a price overlay and background music to
produce a short MP4 reel ready for Instagram.
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Optional

from app.models.post import PostJob
from app.utils.image_utils import add_price_overlay, download_image, resize_for_instagram
from app.utils.video_utils import compose_reel

logger = logging.getLogger(__name__)


class MediaComposer:
    """Orchestrates the media pipeline: download → overlay → compose reel.

    The output is a local MP4 file path stored in ``job.media_path``.
    """

    def __init__(self, output_dir: Optional[str] = None) -> None:
        self._output_dir = output_dir or tempfile.mkdtemp(prefix="ig_media_")
        os.makedirs(self._output_dir, exist_ok=True)

    async def compose(
        self,
        job: PostJob,
        audio_path: Optional[str] = None,
        reel_duration: float = 7.0,
    ) -> PostJob:
        """Run the full media composition pipeline for *job*.

        Steps:
            1. Download product image from ``job.image_url``.
            2. Resize to 1080×1080 Instagram square format.
            3. Add price / discount overlay.
            4. Compose into a short MP4 reel (optionally with music).

        Args:
            job: The :class:`~app.models.post.PostJob` to enrich.
            audio_path: Optional local path to a music file.
            reel_duration: Reel duration in seconds (default 7).

        Returns:
            The same *job* instance with ``media_path`` populated.
        """
        try:
            # Step 1 – download
            img_path = await _async_download(job.image_url, self._output_dir)

            # Step 2 – resize
            resized = resize_for_instagram(img_path, output_path=_tmp_path(self._output_dir, "_sq.jpg"))

            # Step 3 – price overlay
            overlayed = add_price_overlay(
                resized,
                price=job.price,
                discount=job.discount if job.discount else None,
                output_path=_tmp_path(self._output_dir, "_overlay.jpg"),
            )

            # Step 4 – reel
            reel_path = _tmp_path(self._output_dir, f"_{job.job_id}_reel.mp4")
            compose_reel(
                overlayed,
                audio_path=audio_path,
                duration=reel_duration,
                output_path=reel_path,
            )
            job.media_path = reel_path
            logger.info("Media composed for job %s: %s", job.job_id, reel_path)

        except Exception as exc:  # noqa: BLE001
            logger.error("MediaComposer failed for job %s: %s", job.job_id, exc)
            # Fall back: use the raw image as media
            job.media_path = None
            job.error = f"MediaComposer error: {exc}"

        return job


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _async_download(url: str, dest_dir: str) -> str:
    """Run :func:`download_image` in a thread pool to keep the event loop free."""
    import asyncio

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, download_image, url, dest_dir)


def _tmp_path(directory: str, suffix: str) -> str:
    """Return a unique temp file path inside *directory*."""
    fd, path = tempfile.mkstemp(suffix=suffix, dir=directory)
    os.close(fd)
    return path
