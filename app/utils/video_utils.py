"""Video utility helpers (ffmpeg + moviepy wrappers)."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _check_ffmpeg() -> bool:
    """Return True when ffmpeg is available on PATH."""
    return shutil.which("ffmpeg") is not None


def image_to_video(
    image_path: str,
    duration: float = 7.0,
    output_path: Optional[str] = None,
) -> str:
    """Convert a static image to a short MP4 suitable for an Instagram Reel.

    Uses ffmpeg when available, otherwise raises :exc:`RuntimeError`.

    Args:
        image_path: Path to the source JPEG/PNG.
        duration: Video duration in seconds (default 7).
        output_path: Destination MP4 path.  Defaults to a temp file.

    Returns:
        Path to the generated MP4 file.

    Raises:
        RuntimeError: When ffmpeg is not found.
    """
    if not _check_ffmpeg():
        raise RuntimeError(
            "ffmpeg not found on PATH. Install ffmpeg to generate videos."
        )

    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix=".mp4", prefix="ig_")
        os.close(fd)

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-c:v", "libx264",
        "-t", str(duration),
        "-pix_fmt", "yuv420p",
        "-vf", "scale=1080:1080:force_original_aspect_ratio=decrease,"
               "pad=1080:1080:(ow-iw)/2:(oh-ih)/2,setsar=1",
        output_path,
    ]
    _run_ffmpeg(cmd)
    logger.debug("image_to_video: %s -> %s", image_path, output_path)
    return output_path


def add_audio_to_video(
    video_path: str,
    audio_path: str,
    output_path: Optional[str] = None,
    audio_volume: float = 0.5,
) -> str:
    """Mix an audio track into a video file.

    Args:
        video_path: Source MP4 path.
        audio_path: Source audio (MP3/AAC/etc.) path.
        output_path: Destination MP4 path.
        audio_volume: Audio volume multiplier (0.0 – 1.0, default 0.5).

    Returns:
        Path to the output MP4 with mixed audio.

    Raises:
        RuntimeError: When ffmpeg is not found.
    """
    if not _check_ffmpeg():
        raise RuntimeError("ffmpeg not found on PATH.")

    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix="_audio.mp4", prefix="ig_")
        os.close(fd)

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-filter:a", f"volume={audio_volume}",
        "-shortest",
        output_path,
    ]
    _run_ffmpeg(cmd)
    logger.debug("add_audio_to_video: %s + %s -> %s", video_path, audio_path, output_path)
    return output_path


def compose_reel(
    image_path: str,
    audio_path: Optional[str] = None,
    duration: float = 7.0,
    output_path: Optional[str] = None,
) -> str:
    """High-level helper: image → MP4 reel, optionally with background audio.

    Args:
        image_path: Product image (JPEG/PNG).
        audio_path: Optional background music file.
        duration: Reel duration in seconds.
        output_path: Final output MP4 path.

    Returns:
        Path to the finished reel MP4.
    """
    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix="_reel.mp4", prefix="ig_")
        os.close(fd)

    video_path = image_to_video(image_path, duration=duration)

    if audio_path and Path(audio_path).exists():
        final = add_audio_to_video(video_path, audio_path, output_path=output_path)
        # Clean up intermediate silent video
        try:
            os.remove(video_path)
        except OSError:
            pass
        return final

    # No audio: just move the silent video to the desired output path
    shutil.move(video_path, output_path)
    return output_path


# ── ffmpeg runner ─────────────────────────────────────────────────────────────

def _run_ffmpeg(cmd: list) -> None:
    """Run an ffmpeg command, raising :exc:`RuntimeError` on failure."""
    logger.debug("Running: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"ffmpeg failed (exit {result.returncode}):\n{stderr}")
