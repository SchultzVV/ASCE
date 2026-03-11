"""Image utility helpers."""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def download_image(url: str, dest_dir: Optional[str] = None) -> str:
    """Download an image from *url* and return the local file path.

    Args:
        url: HTTP(S) URL of the image.
        dest_dir: Directory to save the file.  Uses a temp dir if omitted.

    Returns:
        Absolute path to the downloaded file.

    Raises:
        RuntimeError: When the download fails.
    """
    import httpx

    dest = dest_dir or tempfile.mkdtemp(prefix="ig_")
    os.makedirs(dest, exist_ok=True)

    ext = Path(url.split("?")[0]).suffix or ".jpg"
    out_path = os.path.join(dest, f"product{ext}")

    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            Path(out_path).write_bytes(resp.content)
        logger.debug("Downloaded image to %s", out_path)
        return out_path
    except Exception as exc:
        raise RuntimeError(f"Failed to download image from {url}: {exc}") from exc


def add_price_overlay(
    image_path: str,
    price: float,
    discount: Optional[float] = None,
    output_path: Optional[str] = None,
) -> str:
    """Overlay price (and optional discount badge) on a product image.

    Uses Pillow when available; falls back to returning the original image
    unchanged when Pillow is not installed.

    Args:
        image_path: Path to the source image.
        price: Current price to display.
        discount: Optional discount percentage.
        output_path: Where to save the result.  Defaults to a temp file.

    Returns:
        Path to the output image.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.warning("Pillow not installed; skipping price overlay")
        return image_path

    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix="_price.jpg", prefix="ig_")
        os.close(fd)

    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)

    # ── Price banner ──────────────────────────────────────────────────────
    w, h = img.size
    banner_h = max(50, h // 8)
    banner_rect = [(0, h - banner_h), (w, h)]

    draw.rectangle(banner_rect, fill=(0, 0, 0, 180))

    price_text = f"R$ {price:.2f}"
    if discount and discount > 0:
        price_text = f"{discount:.0f}% OFF  |  {price_text}"

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
    except OSError:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), price_text, font=font)
    text_w = bbox[2] - bbox[0]
    text_x = (w - text_w) // 2
    text_y = h - banner_h + (banner_h - (bbox[3] - bbox[1])) // 2
    draw.text((text_x, text_y), price_text, fill="white", font=font)

    img.save(output_path, "JPEG", quality=90)
    logger.debug("Price overlay saved to %s", output_path)
    return output_path


def resize_for_instagram(
    image_path: str,
    size: Tuple[int, int] = (1080, 1080),
    output_path: Optional[str] = None,
) -> str:
    """Resize and crop an image to Instagram square format (1080×1080).

    Args:
        image_path: Source image path.
        size: Target (width, height) tuple.
        output_path: Destination file.  Defaults to a temp file.

    Returns:
        Path to the resized image.
    """
    try:
        from PIL import Image, ImageOps
    except ImportError:
        logger.warning("Pillow not installed; skipping resize")
        return image_path

    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix="_sq.jpg", prefix="ig_")
        os.close(fd)

    img = Image.open(image_path).convert("RGB")
    img = ImageOps.fit(img, size, method=Image.LANCZOS)
    img.save(output_path, "JPEG", quality=92)
    logger.debug("Resized image saved to %s", output_path)
    return output_path
