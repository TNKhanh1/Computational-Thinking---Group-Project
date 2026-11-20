"""
Layer 4 Authentication, Multi-Tenant Workspace Isolation & CORS Configuration (P3.1).

Uses Python standard library HS256 JWT signing (`hmac`, `hashlib`, `base64`, `json`)
with zero external auth dependencies. Strictly isolated to Layer 4 (`web/`) to preserve
INV-1..INV-6.

Environment Variables:
  - `SMARTSCHEDULE_SECRET_KEY`: HMAC signing key for JWT bearer tokens.
  - `SMARTSCHEDULE_AUTH_REQUIRED`: Set to "true"/"1" to enforce Bearer auth on state/telemetry routes.
  - `SMARTSCHEDULE_ALLOWED_ORIGINS`: Comma-separated CORS origins (default: localhost/127.0.0.1 ports 8000 & 8010).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Request

_DEFAULT_DEV_SECRET = "smartschedule-local-dev-secret-change-in-prod"
_DEFAULT_ALLOWED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://127.0.0.1:8010",
    "http://localhost:8010",
]


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode((text + padding).encode("ascii"))


def _get_secret_key() -> bytes:
    secret = os.environ.get("SMARTSCHEDULE_SECRET_KEY", "").strip() or _DEFAULT_DEV_SECRET
    return secret.encode("utf-8")


def is_auth_required() -> bool:
    val = os.environ.get("SMARTSCHEDULE_AUTH_REQUIRED", "").strip().lower()
    return val in {"1", "true", "yes", "on"}


def get_allowed_origins() -> List[str]:
    raw = os.environ.get("SMARTSCHEDULE_ALLOWED_ORIGINS", "").strip()
    if not raw:
        return list(_DEFAULT_ALLOWED_ORIGINS)
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    return origins or list(_DEFAULT_ALLOWED_ORIGINS)


def issue_access_token(
    user_id: str,
    email: str,
    display_name: str = "",
    ttl_seconds: int = 7 * 24 * 3600,
) -> str:
    """Issue a compact HS256 JWT signed with SMARTSCHEDULE_SECRET_KEY."""
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user_id),
        "email": str(email),
        "name": str(display_name or email),
        "iat": now,
        "exp": now + max(60, int(ttl_seconds)),
    }
    h_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{h_b64}.{p_b64}".encode("ascii")
    sig = hmac.new(_get_secret_key(), signing_input, hashlib.sha256).digest()
    return f"{h_b64}.{p_b64}.{_b64url_encode(sig)}"


def verify_access_token(token: str) -> Dict[str, Any]:
    """Verify HS256 JWT signature and expiration. Raises ValueError on any failure."""
    parts = (token or "").strip().split(".")
    if len(parts) != 3:
        raise ValueError("Malformed bearer token.")
    h_b64, p_b64, s_b64 = parts
    signing_input = f"{h_b64}.{p_b64}".encode("ascii")
    expected_sig = hmac.new(_get_secret_key(), signing_input, hashlib.sha256).digest()
    try:
        provided_sig = _b64url_decode(s_b64)
        payload = json.loads(_b64url_decode(p_b64).decode("utf-8"))
    except Exception as exc:
        raise ValueError("Invalid token encoding.") from exc

    if not hmac.compare_digest(expected_sig, provided_sig):
        raise ValueError("Invalid token signature.")

    exp = payload.get("exp")
    if not isinstance(exp, (int, float)) or int(time.time()) >= int(exp):
        raise ValueError("Token has expired.")
    if not payload.get("sub"):
        raise ValueError("Token missing subject.")
    return payload


def extract_bearer_claims(request: Request) -> Optional[Dict[str, Any]]:
    """Extract and verify Bearer JWT from Authorization header, or return None if absent."""
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    if not auth_header.strip():
        return None
    parts = auth_header.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header format. Expected 'Bearer <token>'.")
    try:
        return verify_access_token(parts[1])
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def resolve_workspace_id(request: Request, requested_workspace_id: str = "default") -> str:
    """
    Resolve effective tenant workspace_id:
      - Authenticated request -> strictly scoped to `user:<user_id>` (ignores spoofed workspace_id).
      - Unauthenticated request when SMARTSCHEDULE_AUTH_REQUIRED=true -> HTTP 401.
      - Unauthenticated local/dev request -> preserves requested_workspace_id (default: "default").
    """
    claims = extract_bearer_claims(request)
    if claims is not None:
        return f"user:{claims['sub']}"
    if is_auth_required():
        raise HTTPException(status_code=401, detail="Authentication required. Provide a valid Bearer token.")
    return (requested_workspace_id or "default").strip() or "default"
