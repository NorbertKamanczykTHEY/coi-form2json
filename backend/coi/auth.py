"""Bearer JWT verification only (no login): HS256 with JWT_SECRET or RS256 with keys from JWT_JWKS_URL."""
import logging
from functools import cache

import jwt
from apiflask import HTTPTokenAuth, abort
from flask import current_app

log = logging.getLogger(__name__)
auth = HTTPTokenAuth(scheme="Bearer", description="JWT (HS256 shared secret or RS256 from the IdP's JWKS). Demo token: `python -m coi.make_token`.")


@cache
def _jwks(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url, cache_keys=True)


def decode(token: str, c: dict) -> dict:
    alg = c["JWT_ALG"]
    if alg == "HS256":
        if not c["JWT_SECRET"]:
            raise jwt.InvalidKeyError("JWT_SECRET is not set")
        key = c["JWT_SECRET"]
    elif alg == "RS256":
        if not c["JWT_JWKS_URL"]:
            raise jwt.InvalidKeyError("JWT_JWKS_URL is not set")
        key = _jwks(c["JWT_JWKS_URL"]).get_signing_key_from_jwt(token).key
    else:
        raise jwt.InvalidAlgorithmError(f"JWT_ALG {alg} not supported")
    return jwt.decode(
        token, key, algorithms=[alg],
        issuer=c["JWT_ISSUER"] or None, audience=c["JWT_AUDIENCE"] or None, leeway=c["JWT_LEEWAY_S"],
        options={"require": ["exp", "sub"], "verify_aud": bool(c["JWT_AUDIENCE"])},
    )


@auth.verify_token
def verify(token: str) -> dict | None:
    if not token:
        return None  # -> 401 via the app error processor
    try:
        return decode(token, current_app.config)
    except jwt.PyJWTError as e:
        log.info("rejected token: %s", type(e).__name__)  # never the token itself
        abort(401, f"Invalid token: {e}", extra_data={"code": "invalid_token"}, headers={"WWW-Authenticate": 'Bearer error="invalid_token"'})


def user() -> str:
    return auth.current_user["sub"]
