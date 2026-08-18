"""
utils.py
--------
Image preprocessing and st.session_state helpers.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import TYPE_CHECKING

from PIL import Image, ImageOps

if TYPE_CHECKING:
    import streamlit as st
    from gemini_client import FormAnalysis

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_HISTORY_SIZE = 3          # keep last N attempts in session state
MAX_IMAGE_DIMENSION = 1024    # resize to this if larger (saves API bandwidth)
JPEG_QUALITY = 85             # re-encode quality for resized images


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

def bytes_to_pil(image_bytes: bytes) -> Image.Image:
    """Convert raw bytes (from st.camera_input or file_uploader) to PIL."""
    return Image.open(io.BytesIO(image_bytes))


def preprocess_image(image: Image.Image) -> Image.Image:
    """
    Prepare a PIL image for the Gemini Vision API.

    Steps:
    1. Convert to RGB (strips alpha channel if PNG/WEBP).
    2. Auto-rotate based on EXIF orientation data.
    3. Resize so the longest side is ≤ MAX_IMAGE_DIMENSION (preserves aspect).
    """
    # 1. Ensure RGB
    image = image.convert("RGB")

    # 2. Apply EXIF orientation (phones often store rotation metadata)
    image = ImageOps.exif_transpose(image)

    # 3. Resize if too large
    w, h = image.size
    max_dim = max(w, h)
    if max_dim > MAX_IMAGE_DIMENSION:
        scale = MAX_IMAGE_DIMENSION / max_dim
        new_size = (int(w * scale), int(h * scale))
        image = image.resize(new_size, Image.LANCZOS)

    return image


# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------

def init_session_state(state: "st.session_state") -> None:  # type: ignore[type-arg]
    """Initialise all required session state keys if they don't exist yet.

    Call this once at the top of app.py before any widgets render.
    """
    if "attempt_history" not in state:
        state.attempt_history = []          # list[AttemptRecord]
    if "last_analysis" not in state:
        state.last_analysis = None          # FormAnalysis | None
    if "last_exercise" not in state:
        state.last_exercise = None          # str | None


def record_attempt(
    state: "st.session_state",  # type: ignore[type-arg]
    exercise: str,
    analysis: "FormAnalysis",
) -> None:
    """Append the latest analysis to history, keeping the last N entries."""
    record = {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "exercise": exercise,
        "score": analysis.overall_score,
        "grade": analysis.grade,
        "summary": analysis.summary,
    }
    state.attempt_history.append(record)
    # Trim to MAX_HISTORY_SIZE most-recent entries
    if len(state.attempt_history) > MAX_HISTORY_SIZE:
        state.attempt_history = state.attempt_history[-MAX_HISTORY_SIZE:]


def get_score_delta(state: "st.session_state") -> int | None:  # type: ignore[type-arg]
    """Return the delta between the last two attempt scores, or None if <2 attempts."""
    history = state.attempt_history
    if len(history) < 2:
        return None
    return history[-1]["score"] - history[-2]["score"]


# ---------------------------------------------------------------------------
# Grade colour helper (used by app.py for conditional styling)
# ---------------------------------------------------------------------------

GRADE_COLOURS: dict[str, str] = {
    "A": "#2ecc71",   # green
    "B": "#27ae60",   # dark green
    "C": "#f39c12",   # orange
    "D": "#e67e22",   # dark orange
    "F": "#e74c3c",   # red
}


def grade_colour(grade: str) -> str:
    """Return a hex colour string for the given grade letter."""
    return GRADE_COLOURS.get(grade.upper(), "#95a5a6")


# ---------------------------------------------------------------------------
# Severity badge helper
# ---------------------------------------------------------------------------

SEVERITY_EMOJI: dict[str, str] = {
    "low": "🟡",
    "medium": "🟠",
    "high": "🔴",
}


def severity_emoji(severity: str) -> str:
    """Return a coloured circle emoji for the given severity level."""
    return SEVERITY_EMOJI.get(severity.lower(), "⚪")
