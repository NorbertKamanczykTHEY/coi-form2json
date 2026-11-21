from .env import env

PROVIDERS = ("eden", "local")


def load() -> dict:
    e = env()
    provider = e.get("LLM_PROVIDER", "eden").strip().lower()
    if provider not in PROVIDERS:
        raise ValueError(f"LLM_PROVIDER must be one of {PROVIDERS}, got {provider!r}")
    return {
        "provider": provider,  # eden | local (air gap: no outbound traffic, no Eden key)
        "base_url": e.get("LLM_BASE_URL", ""),  # empty = the provider's default
        "api_key": e.get("LLM_API_KEY", ""),  # eden falls back to EDENAI_API_KEY
        "eden_api_key": e.get("EDENAI_API_KEY", ""),
        "timeout_s": float(e.get("LLM_TIMEOUT_S", "90")),  # one call; a timeout fails that ladder rung, the ladder escalates
    }
