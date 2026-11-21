from .env import env


def load() -> dict:
    e = env()
    return {
        "max_file_mb": float(e.get("MAX_FILE_MB", "20")),
    }
