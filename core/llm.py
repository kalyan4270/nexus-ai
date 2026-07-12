"""Shared Groq LLM client with rate-limit fallback."""

from __future__ import annotations

import re
from functools import lru_cache

from groq import Groq, RateLimitError

from core.config import get_settings
from core.exceptions import LLMRateLimitError
from core.logging import get_logger

logger = get_logger(__name__)

_RETRY_AFTER_RE = re.compile(r"try again in (\d+m[\d.]*s|\d+s)", re.IGNORECASE)


@lru_cache
def get_groq_client() -> Groq:
    settings = get_settings()
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not configured")
    return Groq(api_key=settings.groq_api_key)


def _model_chain(preferred: str | None = None) -> list[str]:
    settings = get_settings()
    primary = preferred or settings.groq_model
    chain: list[str] = [primary]
    for model in settings.groq_fallback_models:
        if model not in chain:
            chain.append(model)
    return chain


def _parse_retry_after(message: str) -> str | None:
    match = _RETRY_AFTER_RE.search(message)
    return match.group(1) if match else None


def _raise_rate_limit(last_error: RateLimitError, models_tried: list[str]) -> None:
    detail = str(last_error)
    retry_after = _parse_retry_after(detail)
    raise LLMRateLimitError(
        detail=detail,
        models_tried=models_tried,
        retry_after=retry_after,
    ) from last_error


def complete(
    prompt: str,
    *,
    temperature: float = 0.3,
    max_tokens: int = 1024,
    model: str | None = None,
) -> str:
    client = get_groq_client()
    models = _model_chain(model)
    last_rate_limit: RateLimitError | None = None

    for idx, candidate in enumerate(models):
        try:
            response = client.chat.completions.create(
                model=candidate,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            if idx > 0:
                logger.warning("Primary model rate-limited; succeeded with fallback %s", candidate)
            content = response.choices[0].message.content
            return content.strip() if content else ""
        except RateLimitError as exc:
            last_rate_limit = exc
            if idx < len(models) - 1:
                logger.warning("Rate limit on %s, trying fallback model", candidate)
                continue
            _raise_rate_limit(exc, models)

    if last_rate_limit is not None:
        _raise_rate_limit(last_rate_limit, models)

    return ""
