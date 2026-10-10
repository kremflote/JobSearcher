"""HMAC signing for Finn's app gateway (spike 04 §Signering).

Message: ``METHOD;PATH?QUERY;SERVICE;BODY``, HMAC-SHA512, standard base64, sent in the
``FINN-GW-KEY`` header. The key is decoded from the Android APK (v261006-ec709768); if Finn
rotates it, decompile a new APK and update HMAC_KEY (see spike 04).
"""

from __future__ import annotations

import base64
import hashlib
import hmac

import httpx

HMAC_KEY = b"d45ff03c-b783-44d9-b94a-bb28dbc016a6"


def finn_gw_key(
    method: str, encoded_path: str, encoded_query: str, service: str, body: bytes = b""
) -> str:
    """Signature exactly as `HmacSigningInterceptor.calculateHmac` in the app."""
    path = "" if encoded_path == "/" else encoded_path
    query = f"?{encoded_query}" if encoded_query else ""
    msg = f"{method.upper()};{path}{query};{service};".encode() + body
    return base64.b64encode(hmac.new(HMAC_KEY, msg, hashlib.sha512).digest()).decode("ascii")


def sign_url(method: str, url: str, service: str, body: bytes = b"") -> str:
    """Sign a full URL as httpx will send it (encoded path and query)."""
    raw = httpx.URL(url).raw_path.decode("ascii")
    path, _, query = raw.partition("?")
    return finn_gw_key(method, path, query, service, body)
