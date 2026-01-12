# src/http_client.py
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

from .config import (
    BASE_URL,
    HTTP_HEADERS,
    HTTP_RETRIES,
    HTTP_RETRY_DELAY,
    HTTP_TIMEOUT,
)

logger = logging.getLogger("http")


class HttpClientError(Exception):
    """Raised when HTTP client cannot fetch a valid HTML document."""


@dataclass(frozen=True)
class HttpResult:
    """Optional helper for debugging/metrics (can be removed if not needed)."""
    url: str
    status_code: int
    content_type: str
    text_len: int


# One shared session for connection reuse (faster, fewer handshakes).
_session = requests.Session()


def _build_url(path: str) -> str:
    """
    Convert relative path like 'cg352.htm' to full URL based on BASE_URL.
    If a full URL is provided, returns it as-is.
    """
    p = (path or "").strip()
    if not p:
        raise HttpClientError("Empty path provided to HTTP client")

    if p.startswith("http://") or p.startswith("https://"):
        return p

    # Avoid accidental double slashes: BASE_URL usually ends with '/', path may start with '/'
    return BASE_URL.rstrip("/") + "/" + p.lstrip("/")


def _should_retry(status_code: Optional[int], exc: Optional[BaseException]) -> bool:
    """
    Decide whether we should retry a request.
    - Retry on network errors/timeouts.
    - Retry on 5xx and 429.
    - Do NOT retry on 403/404 (usually permanent for our use-case).
    """
    if exc is not None:
        # Any requests-related transport issue is usually transient
        return True

    if status_code is None:
        return True

    if status_code == 429:
        return True

    if 500 <= status_code <= 599:
        return True

    # 403/404 are typically not recoverable by retrying
    return False


def _request_once(url: str) -> requests.Response:
    """
    Perform a single HTTP GET request. No retries here.
    """
    return _session.get(
        url,
        headers=HTTP_HEADERS,
        timeout=HTTP_TIMEOUT,
    )


def _validate_html_response(url: str, resp: requests.Response) -> None:
    """
    Ensure the response looks like HTML and is non-empty.
    """
    status = resp.status_code
    if status != 200:
        raise HttpClientError(f"Non-200 status for {url}: {status}")

    content_type = (resp.headers.get("Content-Type") or "").lower()
    # Some servers include charset, so we check substring.
    if content_type and ("text/html" not in content_type):
        raise HttpClientError(f"Unexpected Content-Type for {url}: {content_type}")

    text = (resp.text or "").strip()
    if not text:
        raise HttpClientError(f"Empty HTML for {url}")


def _request_with_retry(url: str) -> requests.Response:
    """
    Perform HTTP GET with retries. Total attempts = 1 + HTTP_RETRIES.
    """
    last_exc: Optional[BaseException] = None
    last_status: Optional[int] = None

    total_attempts = 1 + int(HTTP_RETRIES)

    for attempt in range(1, total_attempts + 1):
        try:
            resp = _request_once(url)
            last_status = resp.status_code

            if resp.status_code == 200:
                return resp

            # If non-200, decide whether to retry
            if not _should_retry(resp.status_code, None):
                # No retry — fail fast
                raise HttpClientError(f"Non-retriable status for {url}: {resp.status_code}")

            logger.warning(
                "HTTP %s for %s (attempt %d/%d) — will retry",
                resp.status_code,
                url,
                attempt,
                total_attempts,
            )

        except requests.RequestException as e:
            last_exc = e
            if not _should_retry(None, e):
                # Should not happen with current logic, but keep for completeness
                raise HttpClientError(f"Non-retriable request error for {url}: {e}") from e

            logger.warning(
                "HTTP error for %s (attempt %d/%d): %s — will retry",
                url,
                attempt,
                total_attempts,
                repr(e),
            )

        # Sleep before next attempt (but not after the last one)
        if attempt < total_attempts:
            time.sleep(HTTP_RETRY_DELAY)

    # Retries exhausted
    if last_status is not None:
        raise HttpClientError(f"Failed to fetch {url} after retries (last status: {last_status})")
    if last_exc is not None:
        raise HttpClientError(f"Failed to fetch {url} after retries (last error: {last_exc})") from last_exc

    raise HttpClientError(f"Failed to fetch {url} after retries (unknown reason)")


def get_html(path: str) -> str:
    
    url = _build_url(path)
    resp = _request_with_retry(url)

    # 🔧 FIX: правильная кодировка
    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding  # requests сам угадывает по байтам

    _validate_html_response(url, resp)
    return resp.text
    

def get_html_safe(path: str) -> Optional[str]:
    """
    Safe version: returns None on any HttpClientError instead of raising.
    Useful in runner.py where you want to continue processing other groups.
    """
    try:
        return get_html(path)
    except HttpClientError as e:
        logger.error("Failed to fetch %s: %s", path, e)
        return None


def fetch_debug_info(path: str) -> HttpResult:
    """
    Optional helper to support debugging/metrics. Not required for MVP.
    Returns basic metadata about the response. Still validates for HTML.
    """
    url = _build_url(path)
    resp = _request_with_retry(url)
    _validate_html_response(url, resp)
    content_type = (resp.headers.get("Content-Type") or "")
    return HttpResult(
        url=url,
        status_code=resp.status_code,
        content_type=content_type,
        text_len=len(resp.text or ""),
    )



