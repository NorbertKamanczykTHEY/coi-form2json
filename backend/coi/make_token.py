"""Demo token signed with JWT_SECRET (HS256). Usage: python -m coi.make_token [sub] [--hours N]"""
import argparse
from datetime import UTC, datetime, timedelta

import jwt

from .config import _env


def make(secret: str, sub: str = "demo", hours: float = 8, iss: str = "", aud: str = "") -> str:
    now = datetime.now(UTC)
    claims = {"sub": sub, "iat": now, "exp": now + timedelta(hours=hours)} | ({"iss": iss} if iss else {}) | ({"aud": aud} if aud else {})
    return jwt.encode(claims, secret, algorithm="HS256")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("sub", nargs="?", default="demo")
    p.add_argument("--hours", type=float, default=8)
    a = p.parse_args()
    e = _env()
    if not e.get("JWT_SECRET"):
        raise SystemExit("JWT_SECRET is not set (app/.env or environment)")
    print(make(e["JWT_SECRET"], a.sub, a.hours, e.get("JWT_ISSUER", ""), e.get("JWT_AUDIENCE", "")))
