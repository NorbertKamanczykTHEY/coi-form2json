"""Dictionaries (extensions I and II): catalog tables, seed, matcher, REST blueprint. Docs: app/docs/dictionaries.md.

The generator calls `match(session, label, source_label, type, options)` with a session from Store.session()."""
from .matcher import DictMatch, canonical, match

__all__ = ["DictMatch", "canonical", "init_app", "match"]


def init_app(app) -> None:
    """Tables, seed (only dictionaries the database lacks), blueprint."""
    from ..store import Base
    from . import api, store

    s = app.config["STORE"]
    Base.metadata.create_all(s.engine)
    store.seed(s)
    app.register_blueprint(api.bp)
