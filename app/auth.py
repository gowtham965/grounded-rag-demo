"""Request guards: bearer-token auth (shared or per-customer) and the per-user rate limit."""
import time
from collections import defaultdict, deque

from fastapi import HTTPException

from .config import settings

_hits: dict[str, deque] = defaultdict(deque)


def require_token(authorization: str | None, expected: str):
    if not expected:
        raise HTTPException(500, "Server token not configured")
    if authorization != f"Bearer {expected}":
        raise HTTPException(401, "Unauthorized")


def require_admin(authorization: str | None):
    require_token(authorization, settings.admin_token)


def require_customer(authorization: str | None, customer_id: str):
    """With CUSTOMER_TOKENS set, a token may only query the customer it belongs to.
    Without it, the shared API_TOKEN (demo only) can query any customer."""
    if not settings.customer_tokens:
        return require_token(authorization, settings.api_token)
    token = authorization[7:] if authorization and authorization.startswith("Bearer ") else None
    owner = settings.customer_tokens.get(token) if token else None
    if owner is None:
        raise HTTPException(401, "Unauthorized")
    if owner != customer_id:
        raise HTTPException(403, "This token can't access that customer")


def throttle(user: str):
    """At most RATE_LIMIT_PER_MIN questions per user in any 60 s window (in-memory, one process)."""
    now, q = time.time(), _hits[user]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= settings.rate_limit_per_min:
        raise HTTPException(429, "Too many questions - try again in a minute")
    q.append(now)
