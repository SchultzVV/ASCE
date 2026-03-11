"""Pydantic data models for instagram_service."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, HttpUrl, Field


# ── Enums ────────────────────────────────────────────────────────────────────

class PostStatus(str, Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"


# ── Product input ─────────────────────────────────────────────────────────────

class ProductInput(BaseModel):
    """A single product supplied by the caller."""

    product_id: str = Field(..., alias="id", description="Unique product identifier")
    title: str = Field(..., description="Product name / title")
    price: float = Field(..., gt=0, description="Current price in local currency")
    discount: float = Field(0, ge=0, le=100, description="Discount percentage (0-100)")
    image_url: str = Field(..., description="Publicly accessible product image URL")

    model_config = {"populate_by_name": True}


class CreatePostRequest(BaseModel):
    """Payload for POST /posts."""

    product_id: str
    title: str
    price: float = Field(..., gt=0)
    image_url: str


# ── Music ─────────────────────────────────────────────────────────────────────

class TrackInfo(BaseModel):
    """Represents a trending music track."""

    name: str
    artist: str = ""
    source: str = ""          # "tiktok" | "instagram" | "manual"
    usage_count: int = 0
    growth_rate: float = 0.0
    regional_usage: float = 0.0
    viral_score: float = 0.0


# ── Post ─────────────────────────────────────────────────────────────────────

class PostJob(BaseModel):
    """Internal representation of a post job travelling through the pipeline."""

    job_id: str
    product_id: str
    title: str
    price: float
    discount: float = 0.0
    image_url: str
    caption: Optional[str] = None
    music: Optional[TrackInfo] = None
    media_path: Optional[str] = None
    ig_container_id: Optional[str] = None
    ig_media_id: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    status: PostStatus = PostStatus.PENDING
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PostResponse(BaseModel):
    """API response for a single post job."""

    job_id: str
    status: PostStatus
    scheduled_time: Optional[datetime] = None
    caption: Optional[str] = None
    music: Optional[str] = None


# ── Viral post ────────────────────────────────────────────────────────────────

class ViralPostRequest(BaseModel):
    """Payload for POST /viral-post."""

    products: List[ProductInput]


class ViralPostResponse(BaseModel):
    """Response from POST /viral-post."""

    selected_product: str
    viral_score: float
    scheduled_time: Optional[datetime] = None
    music: Optional[str] = None
    caption: Optional[str] = None
    job_id: str
    status: PostStatus
