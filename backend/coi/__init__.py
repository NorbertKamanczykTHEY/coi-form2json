from flask import Flask

from .config import Config


def create_app() -> Flask:
    """Minimal app factory. Business endpoints (upload, JWT) come in a separate thread and call coi.parsing.parse()."""
    app = Flask(__name__)
    cfg = Config.load()
    app.config["COI"] = cfg
    app.config["MAX_CONTENT_LENGTH"] = int(cfg.max_file_mb * 1024 * 1024) + 64 * 1024  # multipart overhead

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
