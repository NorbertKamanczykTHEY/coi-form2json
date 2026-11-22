from .env import env


def load() -> dict:
    e = env()
    return {
        "max_file_mb": float(e.get("MAX_FILE_MB", "20")),
        # POST /forms and /forms/validate work without a token (stored as created_by="anonymous"); a token that is sent must still be valid.
        # Set false in production: then every endpoint needs a JWT. Optional-auth endpoints: OpenAPI shows security as optional.
        "auth_public_convert": e.get("AUTH_PUBLIC_CONVERT", "true").strip().lower() not in ("0", "false", "no", "off"),
    }
