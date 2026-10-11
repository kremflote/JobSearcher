"""HttpClient politeness (no network)."""

from __future__ import annotations

import httpx

from jobsearcher.sources import http as H
from jobsearcher.sources.http import HttpClient


def test_interval_range_is_jittered():
    c = HttpClient(per_domain_interval_s={"a.example": (2.0, 4.0)}, transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    values = [c._interval("a.example") for _ in range(100)]
    assert all(2.0 <= v <= 4.0 for v in values)
    assert len(set(values)) > 50
    assert c._interval("other.example") == 1.0
    c.set_interval("other.example", 0)
    assert c._interval("other.example") == 0.0


def test_wait_turn_sleeps_between_requests(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr(H.time, "sleep", slept.append)
    c = HttpClient(per_domain_interval_s={"a.example": (5.0, 10.0)}, retries=0,
                   transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    c.get("https://a.example/1", respect_robots=False)
    c.get("https://a.example/2", respect_robots=False)
    assert len(slept) == 1 and 4.9 <= slept[0] <= 10.0


def test_robots_uses_caller_headers():
    seen: list[httpx.Request] = []

    def handler(r: httpx.Request) -> httpx.Response:
        seen.append(r)
        if r.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private/\n")
        return httpx.Response(200)

    c = HttpClient(min_interval_s=0, retries=0, transport=httpx.MockTransport(handler))
    c.get("https://a.example/ok", headers={"User-Agent": "Test/1"})
    assert seen[0].url.path == "/robots.txt" and seen[0].headers["User-Agent"] == "Test/1"
    try:
        c.get("https://a.example/private/x")
    except H.RobotsDisallowed:
        pass
    else:
        raise AssertionError("robots.txt not respected")
