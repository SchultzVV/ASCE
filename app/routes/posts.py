"""REST API routes for creating and scheduling individual posts.

``POST /posts`` – create a post job for a single product.
``GET  /posts``  – list scheduled/recent jobs (stub, for health-checks).
"""

from __future__ import annotations

import logging
import uuid
from typing import List

from fastapi import APIRouter, HTTPException, status

from app.models.post import (
    CreatePostRequest,
    PostJob,
    PostResponse,
    PostStatus,
)
from app.services.caption_generator import CaptionGenerator
from app.services.media_composer import MediaComposer
from app.services.music_analyzer import MusicAnalyzer
from app.services.scheduler import PostScheduler

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/posts", tags=["posts"])

# ── Shared service instances (request-scoped in production would use DI) ────
_music_analyzer = MusicAnalyzer()
_caption_gen = CaptionGenerator()
_media_composer = MediaComposer()
_scheduler = PostScheduler()


@router.post(
    "",
    response_model=PostResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a new Instagram post job",
)
async def create_post(payload: CreatePostRequest) -> PostResponse:
    """Create an Instagram post for a single product.

    **Flow**:
    1. Generate caption (LLM)
    2. Pick best trending music
    3. Compose media (image → reel)
    4. Schedule post for next available window

    Args:
        payload: Product details.

    Returns:
        :class:`~app.models.post.PostResponse` with job metadata.
    """
    job_id = str(uuid.uuid4())
    job = PostJob(
        job_id=job_id,
        product_id=payload.product_id,
        title=payload.title,
        price=payload.price,
        image_url=payload.image_url,
        status=PostStatus.PENDING,
    )

    try:
        # 1. Caption
        job.caption = await _caption_gen.generate(
            product_name=job.title, price=job.price
        )

        # 2. Music
        tracks = await _music_analyzer.get_top_tracks(top_n=1)
        job.music = tracks[0] if tracks else None

        # 3. Media
        job = await _media_composer.compose(job)

        # 4. Schedule
        from app.services.instagram_publisher import InstagramPublisher
        publisher = InstagramPublisher()
        _scheduler.schedule_job(job, publisher.publish)

    except Exception as exc:
        logger.exception("Error creating post job %s", job_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create post: {exc}",
        ) from exc

    return PostResponse(
        job_id=job.job_id,
        status=job.status,
        scheduled_time=job.scheduled_time,
        caption=job.caption,
        music=job.music.name if job.music else None,
    )


@router.get(
    "",
    response_model=List[dict],
    summary="List scheduled post jobs",
)
async def list_posts() -> List[dict]:
    """Return a list of currently scheduled post jobs."""
    jobs = _scheduler.list_pending()
    return [
        {
            "id": j.id,
            "next_run": j.next_run_time.isoformat() if j.next_run_time else None,
        }
        for j in jobs
    ]
