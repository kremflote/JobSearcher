"""Shared HTTP layer for sources (ARCHITECTURE §4.1).

Rate limit per domain (with random jitter), retry with backoff, conditional requests (ETag/Last-Modified),
robots.txt, and raw response caching in DATA_DIR/cache.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from jobsearcher.config import env

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
RETRY_STATUS = {429, 500, 502, 503, 504}
ROBOTS_AGENT = "JobSearcher"

Interval = float | tuple[float, float]
"""Seconds between requests to one host: fixed, or (min, max) drawn at random per request."""


class RobotsDisallowed(Exception):
    pass


class HttpClient:
    """Thin wrapper over httpx.Client. One instance per pipeline run is enough."""

    def __init__(
        self,
        *,
        min_interval_s: Interval = 1.0,
        per_domain_interval_s: dict[str, Interval] | None = None,
        retries: int = 3,
        backoff_s: float = 2.0,
        headers: dict[str, str] | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            timeout=DEFAULT_TIMEOUT,
            headers=headers or {},
            follow_redirects=True,
            transport=transport,
        )
        self._min_interval = min_interval_s
        self._per_domain = dict(per_domain_interval_s or {})
        self._retries = retries
        self._backoff = backoff_s
        self._last: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser | None] = {}
        self._lock = threading.Lock()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # --- politeness ------------------------------------------------------------

    def set_interval(self, host: str, interval: Interval) -> None:
        """Set the spacing for one host (sources call this for their own domains)."""
        self._per_domain[host] = interval

    def _interval(self, host: str) -> float:
        interval = self._per_domain.get(host, self._min_interval)
        if isinstance(interval, tuple | list):
            lo, hi = float(interval[0]), float(interval[1])
            return random.uniform(lo, max(lo, hi))
        return float(interval)

    def _wait_turn(self, host: str) -> None:
        interval = self._interval(host)
        with self._lock:
            now = time.monotonic()
            wait = self._last.get(host, 0.0) + interval - now
            self._last[host] = max(now, now + wait)
        if wait > 0:
            time.sleep(wait)

    def allowed(self, url: str, headers: dict[str, str] | None = None) -> bool:
        """robots.txt check for ROBOTS_AGENT. The robots.txt request itself goes out with the
        caller's headers, so it looks like the rest of that source's traffic."""
        parts = urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        if base not in self._robots:
            rp: RobotFileParser | None = RobotFileParser()
            try:
                self._wait_turn(parts.netloc)
                r = self._client.get(f"{base}/robots.txt", headers=headers or {})
                if r.status_code >= 400:
                    rp = None  # no robots.txt → everything allowed
                else:
                    rp.parse(r.text.splitlines())
            except httpx.HTTPError:
                rp = None
            self._robots[base] = rp
        rp = self._robots[base]
        return rp is None or rp.can_fetch(ROBOTS_AGENT, url)

    # --- requests --------------------------------------------------------------

    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict | list | None = None,
        headers: dict[str, str] | None = None,
        etag: str | None = None,
        last_modified: str | None = None,
        respect_robots: bool = True,
        timeout: float | None = None,
        retries: int | None = None,
    ) -> httpx.Response:
        """Send a request with rate limit and retry. 304 and 4xx are returned, not raised."""
        if respect_robots and not self.allowed(url, headers):
            raise RobotsDisallowed(url)
        hdrs = dict(headers or {})
        if etag:
            hdrs["If-None-Match"] = etag
        if last_modified:
            hdrs["If-Modified-Since"] = last_modified
        host = urlsplit(url).netloc
        max_retries = self._retries if retries is None else retries
        attempt = 0
        while True:
            attempt += 1
            self._wait_turn(host)
            try:
                r = self._client.request(
                    method,
                    url,
                    params=params,
                    headers=hdrs,
                    timeout=httpx.Timeout(timeout, connect=10.0) if timeout else httpx.USE_CLIENT_DEFAULT,
                )
            except httpx.TransportError as e:
                if attempt > max_retries:
                    raise
                log.warning("http retry %s %s: %s", method, url, e)
            else:
                if r.status_code not in RETRY_STATUS or attempt > max_retries:
                    return r
                log.warning("http retry %s %s: %s", method, url, r.status_code)
                retry_after = r.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    time.sleep(min(int(retry_after), 60))
                    continue
            time.sleep(self._backoff * 2 ** (attempt - 1))

    def get(self, url: str, **kwargs) -> httpx.Response:
        return self.request("GET", url, **kwargs)


def save_raw(source: str, name: str, content: str | bytes) -> str:
    """Store a raw response under DATA_DIR/cache/<source>/<YYYY-MM-DD>/<name>.

    Returns the path relative to DATA_DIR (for job_sources.raw_path).
    """
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
    path: Path = env().cache_dir / source / day / safe
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_bytes(content)
    return path.relative_to(env().data_dir).as_posix()
