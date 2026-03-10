"""Meta Graph API low-level HTTP client."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.facebook.com/v19.0"


class MetaAPIClient:
    """Thin wrapper around the Meta Graph API."""

    def __init__(self) -> None:
        settings = get_settings()
        self._token = settings.access_token
        self._ig_user_id = settings.instagram_business_id
        self._timeout = httpx.Timeout(30.0)

    # ── Media container ───────────────────────────────────────────────────

    async def create_media_container(
        self,
        image_url: Optional[str] = None,
        video_url: Optional[str] = None,
        caption: str = "",
        media_type: str = "IMAGE",
    ) -> str:
        """Create an IG media container and return its container ID.

        Args:
            image_url: Public URL to a JPEG/PNG image (for IMAGE posts).
            video_url: Public URL to an MP4 video (for REELS posts).
            caption: Post caption.
            media_type: ``"IMAGE"`` or ``"REELS"``.

        Returns:
            The ``id`` string of the created container.

        Raises:
            httpx.HTTPStatusError: On non-2xx responses from the API.
            ValueError: If neither image_url nor video_url is provided.
        """
        if media_type == "REELS" and not video_url:
            raise ValueError("video_url is required for REELS media type")
        if media_type == "IMAGE" and not image_url:
            raise ValueError("image_url is required for IMAGE media type")

        url = f"{GRAPH_BASE}/{self._ig_user_id}/media"
        payload: Dict[str, Any] = {
            "caption": caption,
            "access_token": self._token,
            "media_type": media_type,
        }
        if media_type == "REELS":
            payload["video_url"] = video_url
            payload["share_to_feed"] = True
        else:
            payload["image_url"] = image_url

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, data=payload)
            resp.raise_for_status()
            data = resp.json()

        container_id: str = data["id"]
        logger.info("Created IG media container %s", container_id)
        return container_id

    # ── Publish ───────────────────────────────────────────────────────────

    async def publish_container(self, container_id: str) -> str:
        """Publish a previously created media container.

        Args:
            container_id: The container ID returned by :meth:`create_media_container`.

        Returns:
            The ``id`` of the published media object.

        Raises:
            httpx.HTTPStatusError: On non-2xx responses from the API.
        """
        url = f"{GRAPH_BASE}/{self._ig_user_id}/media_publish"
        payload = {
            "creation_id": container_id,
            "access_token": self._token,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, data=payload)
            resp.raise_for_status()
            data = resp.json()

        media_id: str = data["id"]
        logger.info("Published IG media %s", media_id)
        return media_id

    # ── Insights / status ─────────────────────────────────────────────────

    async def get_container_status(self, container_id: str) -> Dict[str, Any]:
        """Poll the status of a media container (useful for video processing).

        Args:
            container_id: The container ID to check.

        Returns:
            A dict with ``status_code`` and optional ``status`` fields.
        """
        url = f"{GRAPH_BASE}/{container_id}"
        params = {
            "fields": "status_code,status",
            "access_token": self._token,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
