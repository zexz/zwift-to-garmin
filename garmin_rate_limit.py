#!/usr/bin/env python3
"""Retry helpers for transient Garmin rate limits (HTTP 429)."""

from __future__ import annotations

import random
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable, Optional, TypeVar


T = TypeVar("T")


def _status_code_from_exception(exc: Exception) -> Optional[int]:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int):
        return status_code
    return None


def is_rate_limited(exc: Exception) -> bool:
    status_code = _status_code_from_exception(exc)
    if status_code == 429:
        return True

    message = str(exc).lower()
    return "429" in message or "too many requests" in message


def _parse_retry_after_seconds(value: str) -> Optional[float]:
    raw = (value or "").strip()
    if not raw:
        return None

    try:
        seconds = float(raw)
        if seconds >= 0:
            return seconds
    except ValueError:
        pass

    try:
        when = parsedate_to_datetime(raw)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        delta = (when - datetime.now(timezone.utc)).total_seconds()
        return max(0.0, delta)
    except Exception:
        return None


def retry_after_seconds(exc: Exception) -> Optional[float]:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if not headers:
        return None

    value = headers.get("Retry-After")
    if not value:
        return None

    return _parse_retry_after_seconds(value)


def call_with_rate_limit_retry(
    func: Callable[[], T],
    *,
    action_label: str,
    max_attempts: int = 5,
    base_delay: float = 5.0,
    max_delay: float = 120.0,
    jitter_ratio: float = 0.2,
) -> T:
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    for attempt in range(1, max_attempts + 1):
        try:
            return func()
        except Exception as exc:
            if not is_rate_limited(exc) or attempt >= max_attempts:
                raise

            retry_after = retry_after_seconds(exc)
            fallback_delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            delay = retry_after if retry_after is not None else fallback_delay

            jitter_low = max(0.0, 1.0 - jitter_ratio)
            jitter_high = max(jitter_low, 1.0 + jitter_ratio)
            delay *= random.uniform(jitter_low, jitter_high)
            delay = min(max_delay, delay)

            print(
                f"Rate limited while trying to {action_label} (attempt {attempt}/{max_attempts}). "
                f"Waiting {delay:.1f}s before retrying..."
            )
            time.sleep(delay)

    raise RuntimeError("Retry loop exited unexpectedly")
