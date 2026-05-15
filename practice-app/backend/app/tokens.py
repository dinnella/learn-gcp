"""Single-use submission tokens for leaderboard writes.

When a game session legitimately ends (time runs out, question pool
exhausted, mock completed, all strikes used), the server mints an
unguessable token, stores it on the session document with a TTL, and
returns it to the client exactly once.

To post a leaderboard entry, the client must present that token. The
leaderboard document is keyed by ``sha256(token)`` and written with
``create()`` (write-once), so:

* No leaderboard entry can ever be modified after it is written.
* No two sessions can collide on the same leaderboard slot.
* Anyone who didn't actually finish a game has no way to get a token
  and therefore no way to add an entry.
* A stolen token is usable for at most ``TOKEN_TTL_SECONDS`` and
  exactly once.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone


TOKEN_TTL_SECONDS = 3600  # 1 hour


def mint_submit_token() -> tuple[str, str]:
    """Return ``(raw_token, expires_at_iso)`` for a freshly minted token."""
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(seconds=TOKEN_TTL_SECONDS)
    return token, expires.isoformat()


def hash_submit_token(token: str) -> str:
    """Stable hex digest used as the leaderboard document ID and as the
    session-doc's stored token shadow. The raw token is never persisted."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_hash_matches(stored_hash: str | None, presented_raw: str | None) -> bool:
    """Constant-time check: does sha256(presented) equal the stored hash?

    Used to validate a presented raw token against the hash stored on the
    session document. Because only the hash is persisted, an attacker who
    can read the session doc cannot recover a usable token.
    """
    if not stored_hash or not presented_raw:
        return False
    presented_hash = hash_submit_token(presented_raw)
    return hmac.compare_digest(stored_hash, presented_hash)


def mint_session_secret() -> tuple[str, str]:
    """Return ``(raw_secret, sha256_hex)`` for a per-session abandon secret.

    The raw secret is returned to the client exactly once (in the start
    response). Only the hash is persisted on the session document.
    """
    raw = secrets.token_urlsafe(24)
    return raw, hashlib.sha256(raw.encode("utf-8")).hexdigest()


def secret_matches(stored_hash: str | None, presented_raw: str | None) -> bool:
    """Constant-time check for the abandon/session secret."""
    if not stored_hash or not presented_raw:
        return False
    presented_hash = hashlib.sha256(presented_raw.encode("utf-8")).hexdigest()
    return hmac.compare_digest(stored_hash, presented_hash)


def token_expired(expires_at: str | None) -> bool:
    if not expires_at:
        return True
    try:
        exp = datetime.fromisoformat(expires_at)
    except ValueError:
        return True
    return datetime.now(timezone.utc) >= exp
