"""
gemini_client.py
----------------
Wraps all interactions with the Gemini Vision API.

Responsibilities:
- Configure the SDK from the environment variable.
- Send image + exercise prompt to Gemini.
- Parse and validate the JSON response with Pydantic.
- Retry once on malformed JSON before surfacing a clean error.
- Never expose raw stack traces — raise typed exceptions instead.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env anchored to this file's directory — works regardless of where
# Streamlit is launched from. override=True ensures it wins over any stale env.
load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

import google.generativeai as genai
from PIL import Image
from pydantic import BaseModel, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic models — define the exact contract we expect from Gemini
# ---------------------------------------------------------------------------

class Flaw(BaseModel):
    area: str = Field(..., description="Body region, e.g. 'Lower Back'")
    issue: str = Field(..., description="Concise description of the problem")
    severity: str = Field(..., description="one of: low, medium, high")

    @field_validator("severity")
    @classmethod
    def severity_must_be_valid(cls, v: str) -> str:
        allowed = {"low", "medium", "high"}
        if v.lower() not in allowed:
            raise ValueError(f"severity must be one of {allowed}, got '{v}'")
        return v.lower()


class FormAnalysis(BaseModel):
    overall_score: int = Field(..., ge=0, le=100)
    grade: str = Field(..., description="A / B / C / D / F")
    flaws: list[Flaw] = Field(default_factory=list)
    fix_tips: list[str] = Field(default_factory=list)
    image_quality: str = Field(..., description="ok | blurry | no_person | partial_frame")
    summary: str = Field(..., description="One-sentence overall assessment")

    @field_validator("grade")
    @classmethod
    def grade_must_be_valid(cls, v: str) -> str:
        allowed = {"A", "B", "C", "D", "F"}
        if v.upper() not in allowed:
            raise ValueError(f"grade must be one of {allowed}, got '{v}'")
        return v.upper()

    @field_validator("image_quality")
    @classmethod
    def image_quality_must_be_valid(cls, v: str) -> str:
        allowed = {"ok", "blurry", "no_person", "partial_frame"}
        if v.lower() not in allowed:
            raise ValueError(f"image_quality must be one of {allowed}, got '{v}'")
        return v.lower()


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class GeminiClientError(Exception):
    """Raised for configuration or connectivity issues."""


class GeminiParseError(Exception):
    """Raised when Gemini's response cannot be parsed into FormAnalysis."""
    def __init__(self, message: str, raw_response: str = ""):
        super().__init__(message)
        self.raw_response = raw_response


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

_MODEL_NAME = "gemini-3.6-flash"
_MAX_RETRIES = 2
_RETRY_DELAY_SECONDS = 2

# Gemini 3-series models spend part of their output token budget on internal
# "thinking" before writing the final answer. If max_output_tokens is too low,
# thinking can eat the whole budget and truncate the actual JSON response.
# We raise the ceiling AND turn thinking down since this task needs structured
# output, not deep reasoning.
_MAX_OUTPUT_TOKENS = 2048


def _configure_sdk() -> None:
    """Read GEMINI_API_KEY from env and configure the SDK."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise GeminiClientError(
            "GEMINI_API_KEY environment variable is not set. "
            "Copy .env.example → .env and add your key from aistudio.google.com"
        )
    genai.configure(api_key=api_key)


def _extract_json(text: str) -> str:
    """Strip markdown code fences if Gemini wraps its JSON anyway, and grab
    just the {...} block in case there's stray text around it."""
    text = text.strip()

    if text.startswith("```"):
        lines = text.splitlines()
        # Drop the first fence line (```json or ```) and the last ``` line
        if len(lines) >= 2 and lines[-1].strip().startswith("```"):
            text = "\n".join(lines[1:-1]).strip()
        else:
            text = "\n".join(lines[1:]).strip()

    # If there's still stray text before/after, isolate the outermost {...}
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]

    return text.strip()


def _parse_response(raw: str) -> FormAnalysis:
    """Parse raw Gemini text into a validated FormAnalysis model."""
    cleaned = _extract_json(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise GeminiParseError(
            f"Gemini returned non-JSON text: {exc}", raw_response=raw
        ) from exc

    try:
        return FormAnalysis(**data)
    except (ValidationError, TypeError) as exc:
        raise GeminiParseError(
            f"Gemini JSON did not match expected schema: {exc}", raw_response=raw
        ) from exc


def _build_generation_config() -> "genai.types.GenerationConfig":
    """Build the generation config, disabling/lowering 'thinking' where the
    installed SDK version supports it, so token budget goes to the JSON
    output instead of internal reasoning."""
    kwargs = dict(
        temperature=0.2,
        max_output_tokens=_MAX_OUTPUT_TOKENS,
        response_mime_type="application/json",
    )

    # thinking_config is only available on newer SDK versions. Guard it so
    # older installs don't crash — they'll just skip this and rely on the
    # higher max_output_tokens instead.
    try:
        kwargs["thinking_config"] = genai.types.ThinkingConfig(thinking_level="low")
    except AttributeError:
        logger.info(
            "ThinkingConfig not available in this SDK version — "
            "relying on max_output_tokens=%d only.",
            _MAX_OUTPUT_TOKENS,
        )

    return genai.types.GenerationConfig(**kwargs)


def analyse_form(image: Image.Image, exercise_prompt: str) -> FormAnalysis:
    """
    Send a PIL image + exercise prompt to Gemini and return a FormAnalysis.

    Parameters
    ----------
    image : PIL.Image.Image
        The user's captured photo (already preprocessed by utils.py).
    exercise_prompt : str
        The full system prompt for the selected exercise (from prompts.py).

    Returns
    -------
    FormAnalysis
        Validated Pydantic model with score, flaws, tips, etc.

    Raises
    ------
    GeminiClientError
        If the API key is missing or the SDK fails to initialise.
    GeminiParseError
        If Gemini's response cannot be parsed after retries.
    """
    _configure_sdk()

    model = genai.GenerativeModel(model_name=_MODEL_NAME)
    generation_config = _build_generation_config()

    last_error: Optional[Exception] = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            logger.info("Gemini request attempt %d/%d", attempt, _MAX_RETRIES)
            response = model.generate_content(
                [exercise_prompt, image],
                generation_config=generation_config,
            )

            # Diagnostic: confirms whether truncation (MAX_TOKENS) is the
            # cause of any parse failure, versus a genuine formatting issue.
            try:
                finish_reason = response.candidates[0].finish_reason
                logger.info("Gemini finish_reason: %s", finish_reason)
                if str(finish_reason) in ("2", "MAX_TOKENS"):
                    logger.warning(
                        "Response was truncated by MAX_TOKENS on attempt %d — "
                        "consider raising _MAX_OUTPUT_TOKENS further.",
                        attempt,
                    )
            except (IndexError, AttributeError):
                pass

            return _parse_response(response.text)

        except GeminiParseError as exc:
            logger.warning("Parse error on attempt %d: %s", attempt, exc)
            last_error = exc
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_DELAY_SECONDS)

        except Exception as exc:
            logger.error("Gemini API error on attempt %d: %s", attempt, exc)
            last_error = GeminiClientError(
                f"Gemini API call failed: {type(exc).__name__}: {exc}"
            )
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_DELAY_SECONDS)

    if isinstance(last_error, GeminiParseError):
        raise last_error
    raise last_error or GeminiClientError("Unknown error during Gemini request")