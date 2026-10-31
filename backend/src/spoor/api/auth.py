"""Bearer-token auth with per-site RBAC (PRD §4, §7.4), signed short-lived media links, and a simple rate limit.

Hackathon scope: tokens come from a private JSON file. A production deployment replaces this with an identity
provider; the role/site checks stay the same.
"""

import hashlib
import hmac
import json
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, status

from spoor.contracts import Role


@dataclass(frozen=True)
class Principal:
    user_id: str
    role: Role
    site_ids: frozenset[str]
    also: frozenset[Role] = frozenset()  # further roles (the single demo supervisor holds all of them)

    def require_site(self, site_id: str) -> None:
        if site_id not in self.site_ids:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "no access to this site")

    def require_role(self, *roles: Role) -> None:
        if self.role not in roles and not self.also.intersection(roles):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"requires role {[r.value for r in roles]}")


class TokenRegistry:
    def __init__(self, tokens: dict[str, Principal]):
        self._tokens = tokens

    @classmethod
    def from_file(cls, path: Path) -> "TokenRegistry":
        raw = json.loads(path.read_text(encoding="utf-8"))["tokens"]
        return cls({t: Principal(v["user_id"], Role(v["role"]), frozenset(v["site_ids"]), frozenset(Role(r) for r in v.get("roles", [])))
                    for t, v in raw.items()})  # fmt: skip

    def resolve(self, token: str) -> Principal | None:
        for known, principal in self._tokens.items():
            if hmac.compare_digest(known.encode(), token.encode()):
                return principal
        return None


class UrlSigner:
    def __init__(self, secret: bytes | None = None, ttl_s: int = 300):
        self.secret = secret or secrets.token_bytes(32)
        self.ttl_s = ttl_s

    def _mac(self, resource: str, exp: int) -> str:
        return hmac.new(self.secret, f"{resource}|{exp}".encode(), hashlib.sha256).hexdigest()

    def sign(self, resource: str, now: float | None = None) -> tuple[int, str]:
        exp = int((now or time.time()) + self.ttl_s)
        return exp, self._mac(resource, exp)

    def check(self, resource: str, exp: int, sig: str, now: float | None = None) -> None:
        if (now or time.time()) > exp:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "link expired")
        if not hmac.compare_digest(self._mac(resource, exp), sig):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "invalid signature")


class RateLimiter:
    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self.hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= self.per_minute:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate limit exceeded")
        q.append(now)
