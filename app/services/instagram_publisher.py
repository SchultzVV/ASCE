"""Instagram publisher service.

Wraps the two-step Meta Graph API flow:
    1. Create a media container (``POST /{ig-user-id}/media``)
    2. Publish the container  (``POST /{ig-user-id}/media_publish``)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.clients.meta_api import MetaAPIClient
from app.models.post import PostJob, PostStatus

logger = logging.getLogger(__name__)

# Maximum seconds to wait for IG to finish processing a video container
_VIDEO_PROCESSING_TIMEOUT = 120
_VIDEO_POLL_INTERVAL = 5


class InstagramPublisher:
    """Publishes :class:`~app.models.post.PostJob` items to Instagram.

    Supports both IMAGE and REELS media types.
    """

    def __init__(self) -> None:
        self._client = MetaAPIClient()

    async def publish(self, job: PostJob, public_media_url: Optional[str] = None) -> PostJob:
        """Publish *job* to Instagram and update its status fields.

        Args:
            job: The post job to publish.
            public_media_url: Publicly accessible URL to the media file
                (required by the Graph API).  When ``None`` and
                ``job.media_path`` is set, callers must upload the file to
                MinIO or another CDN first and pass the URL here.

        Returns:
            The updated *job* with ``ig_container_id``, ``ig_media_id``
            and ``status`` set.
        """
        caption = job.caption or ""
        media_url = public_media_url or job.image_url

        # Determine media type
        is_video = media_url.lower().endswith((".mp4", ".mov"))
        media_type = "REELS" if is_video else "IMAGE"

        try:
            # Step 1 – create container
            container_id = await self._client.create_media_container(
                image_url=None if is_video else media_url,
                video_url=media_url if is_video else None,
                caption=caption,
                media_type=media_type,
            )
            job.ig_container_id = container_id

            # Step 2 – wait for video processing if needed
            if is_video:
                await self._wait_for_processing(container_id)

            # Step 3 – publish
            media_id = await self._client.publish_container(container_id)
            job.ig_media_id = media_id
            job.status = PostStatus.PUBLISHED
            logger.info("Job %s published as IG media %s", job.job_id, media_id)

        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to publish job %s: %s", job.job_id, exc)
            job.status = PostStatus.FAILED
            job.error = str(exc)

        return job

    # ── Helpers ───────────────────────────────────────────────────────────

    async def _wait_for_processing(self, container_id: str) -> None:
        """Poll until IG finishes processing a video container.

        Raises:
            TimeoutError: When the container does not reach FINISHED state
                within :data:`_VIDEO_PROCESSING_TIMEOUT` seconds.
            RuntimeError: When the container enters an ERROR state.
        """
        elapsed = 0
        while elapsed < _VIDEO_PROCESSING_TIMEOUT:
            status_data = await self._client.get_container_status(container_id)
            code = status_data.get("status_code", "")
            logger.debug("Container %s status: %s", container_id, code)

            if code == "FINISHED":
                return
            if code == "ERROR":
                raise RuntimeError(
                    f"Instagram container {container_id} entered ERROR state"
                )

            await asyncio.sleep(_VIDEO_POLL_INTERVAL)
            elapsed += _VIDEO_POLL_INTERVAL

        raise TimeoutError(
            f"Container {container_id} did not finish processing within "
            f"{_VIDEO_PROCESSING_TIMEOUT}s"
        )
