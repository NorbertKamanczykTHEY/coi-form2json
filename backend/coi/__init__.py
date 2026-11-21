import logging
from io import BytesIO

from apiflask import APIFlask
from flask import Request

from .config import Config, _env
from .store import Store

__version__ = "0.1.0"


class InMemoryRequest(Request):
    """Uploads stay in RAM (Werkzeug spools files > 500 KB to disk); MAX_CONTENT_LENGTH bounds the size."""

    def _get_file_stream(self, *args, **kwargs):
        return BytesIO()


def create_app() -> APIFlask:
    from . import api

    e = _env()
    logging.basicConfig(level=e.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = APIFlask(__name__, title="COI Formularze API", version=__version__, docs_path="/docs")
    app.request_class = InMemoryRequest
    cfg = Config.load()
    app.config.update(
        COI=cfg,
        VERSION=__version__,
        MAX_CONTENT_LENGTH=int(cfg.max_file_mb * 2**20) + 64 * 1024,  # multipart overhead
        MAX_FILENAME_LEN=int(e.get("MAX_FILENAME_LEN", "250")),
        VALIDATION_ERROR_STATUS_CODE=400,
        JWT_ALG=e.get("JWT_ALG", "HS256"),
        JWT_SECRET=e.get("JWT_SECRET", ""),
        JWT_JWKS_URL=e.get("JWT_JWKS_URL", ""),
        JWT_ISSUER=e.get("JWT_ISSUER", ""),
        JWT_AUDIENCE=e.get("JWT_AUDIENCE", ""),
        JWT_LEEWAY_S=float(e.get("JWT_LEEWAY_S", "30")),
        STORE=Store(e.get("DB_PATH", "/data/coi.sqlite")),
    )
    app.config["STORE"].init()
    app.error_processor(api.problem)
    app.register_blueprint(api.bp)

    @app.get("/healthz")
    @app.get("/health")
    @app.doc(summary="Liveness (no token needed)")
    def health():
        return {"status": "ok"}

    return app
