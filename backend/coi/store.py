"""SQLite store (stdlib, no ORM). Layout and rationale: app/docs/storage.md. One short-lived connection per call, so threads (SSE) are safe.
Other modules (coi/dictionaries/) share the same database file through Store.connect() / Store.db() and own their own tables."""
import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS forms (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    filename TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_by TEXT,
    updated_at TEXT,
    form TEXT NOT NULL,
    report TEXT NOT NULL,
    editor TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS forms_created_at ON forms (created_at);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str | Path):
        self.path = str(path)

    def connect(self) -> sqlite3.Connection:
        """A new connection to the shared database (rows as sqlite3.Row). The caller commits and closes; db() does both."""
        con = sqlite3.connect(self.path, timeout=10)
        con.row_factory = sqlite3.Row
        return con

    @contextmanager
    def db(self) -> Iterator[sqlite3.Connection]:
        """`with current_app.config["STORE"].db() as con:` commits on success, rolls back on error, always closes."""
        with closing(self.connect()) as con, con:
            yield con

    def init(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.db() as con:
            con.executescript(SCHEMA)

    def add_form(self, *, filename: str, sha256: str, user: str, form: dict, report: dict, editor: dict) -> str:
        fid = str(uuid.uuid4())
        with self.db() as con:
            con.execute(
                "INSERT INTO forms (id, title, filename, sha256, created_by, created_at, form, report, editor) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (fid, form.get("title", ""), filename, sha256, user, _now(), *(json.dumps(x, ensure_ascii=False) for x in (form, report, editor))),
            )
        return fid

    def list_forms(self) -> list[dict]:
        with self.db() as con:
            rows = con.execute("SELECT id, title, filename, sha256, created_by, created_at, updated_by, updated_at FROM forms ORDER BY created_at DESC, rowid DESC")
            return [dict(r) for r in rows]

    def get_form(self, fid: str) -> dict | None:
        with self.db() as con:
            r = con.execute("SELECT * FROM forms WHERE id = ?", (fid,)).fetchone()
        if r is None:
            return None
        return dict(r) | {k: json.loads(r[k]) for k in ("form", "report", "editor")}

    def update_form(self, fid: str, form: dict, user: str) -> bool:
        with self.db() as con:
            cur = con.execute("UPDATE forms SET form = ?, title = ?, updated_by = ?, updated_at = ? WHERE id = ?",
                              (json.dumps(form, ensure_ascii=False), form.get("title", ""), user, _now(), fid))
        return cur.rowcount == 1
