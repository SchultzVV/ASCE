"""REST API route for viral post creation.

``POST /viral-post`` – select the most viral product from a list,
generate content, and schedule/publish it.
"""

from __future__ import annotations

import logging
import uuid
from typing import List

from fastapi import APIRouter, HTTPException, status

from app.models.post import (
    PostJob,
    PostStatus,
    ProductInput,
    ViralPostRequest,
    ViralPostResponse,
)
from app.services.caption_generator import CaptionGenerator
from app.services.instagram_publisher import InstagramPublisher
from app.services.media_composer import MediaComposer
from app.services.music_analyzer import MusicAnalyzer
from app.services.scheduler import PostScheduler

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/viral-post", tags=["viral"])

_music_analyzer = MusicAnalyzer()
_caption_gen = CaptionGenerator()
_media_composer = MediaComposer()
_scheduler = PostScheduler()
_publisher = InstagramPublisher()


@router.post(
    "",
    response_model=ViralPostResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Select and schedule the most viral product",
)
async def create_viral_post(payload: ViralPostRequest) -> ViralPostResponse:
    """Select the best product from *products*, generate content, and schedule.

    **Viral scoring formula**::

        viral_score = discount_weight * 0.40
                    + price_attractiveness * 0.25
                    + historical_performance * 0.20
                    + trend_factor * 0.15

    Args:
        payload: List of product candidates.

    Returns:
        :class:`~app.models.post.ViralPostResponse` with selected product
        details and scheduling info.
    """
    if not payload.products:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one product is required",
        )

    # 1. Score each product
    scored = _rank_products(payload.products)
    best = scored[0]
    logger.info(
        "Selected product '%s' with viral score %.3f",
        best["product"].title,
        best["score"],
    )

    # 2. Build PostJob
    product: ProductInput = best["product"]
    job_id = str(uuid.uuid4())
    job = PostJob(
        job_id=job_id,
        product_id=product.product_id,
        title=product.title,
        price=product.price,
        discount=product.discount,
        image_url=product.image_url,
        status=PostStatus.PENDING,
    )

    try:
        # 3. Caption
        job.caption = await _caption_gen.generate(
            product_name=job.title,
            price=job.price,
            discount=job.discount,
        )

        # 4. Music
        tracks = await _music_analyzer.get_top_tracks(top_n=1)
        job.music = tracks[0] if tracks else None

        # 5. Media
        job = await _media_composer.compose(job)

        # 6. Schedule
        _scheduler.schedule_job(job, _publisher.publish)

    except Exception as exc:
        logger.exception("Error in viral post pipeline for job %s", job_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Viral post pipeline failed: {exc}",
        ) from exc

    return ViralPostResponse(
        selected_product=product.title,
        viral_score=round(best["score"], 4),
        scheduled_time=job.scheduled_time,
        music=job.music.name if job.music else None,
        caption=job.caption,
        job_id=job.job_id,
        status=job.status,
    )


# ── Viral scoring ─────────────────────────────────────────────────────────────

def _rank_products(products: List[ProductInput]) -> List[dict]:
    """Score and sort *products* by virality potential.

    Returns a list of dicts ``{"product": ProductInput, "score": float}``
    sorted by score descending.
    """
    max_price = max(p.price for p in products) or 1.0

    scored = []
    for p in products:
        discount_weight = (p.discount / 100) * 0.40
        price_attractiveness = (1 - p.price / max_price) * 0.25
        # Placeholders – real values come from historical data / trending APIs
        historical_performance = 0.5 * 0.20
        trend_factor = 0.5 * 0.15

        score = discount_weight + price_attractiveness + historical_performance + trend_factor
        scored.append({"product": p, "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored
