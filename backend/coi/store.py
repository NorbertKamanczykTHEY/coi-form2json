"""Storage on SQLAlchemy 2 (layout: app/docs/storage.md). DATABASE_URL picks the database; SQLite on the volume by default.
Other modules (coi/dictionaries/) declare models on Base and use Store.engine / Store.session()."""
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import JSON, String, create_engine, make_url, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")  # ISO text: sorts and serialises the same on every backend


class Form(Base):
    __tablename__ = "forms"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(500))
    filename: Mapped[str] = mapped_column(String(250))
    sha256: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[str] = mapped_column(String(32), default=_now, index=True)
    updated_by: Mapped[str | None] = mapped_column(String(255))
    updated_at: Mapped[str | None] = mapped_column(String(32))
    form: Mapped[dict] = mapped_column(JSON)
    report: Mapped[dict] = mapped_column(JSON)
    editor: Mapped[dict] = mapped_column(JSON)

    META = ("id", "title", "filename", "sha256", "created_by", "created_at", "updated_by", "updated_at")

    def to_dict(self, *cols: str) -> dict:
        return {c: getattr(self, c) for c in cols or (*self.META, "form", "report", "editor")}


class Store:
    def __init__(self, url: str):
        u = make_url(url)
        if u.get_backend_name() == "sqlite" and u.database not in (None, "", ":memory:"):
            Path(u.database).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(u)
        self._session = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def session(self) -> Iterator[Session]:
        """`with current_app.config["STORE"].session() as s:` commits on success, rolls back on error, always closes."""
        with self._session.begin() as s:
            yield s

    def init(self) -> None:
        """create_all for every model imported so far on Base; no migrations."""
        Base.metadata.create_all(self.engine)

    def add_form(self, *, filename: str, sha256: str, user: str, form: dict, report: dict, editor: dict) -> str:
        with self.session() as s:
            f = Form(title=form.get("title", ""), filename=filename, sha256=sha256, created_by=user, form=form, report=report, editor=editor)
            s.add(f)
            s.flush()
            return f.id

    def list_forms(self) -> list[dict]:
        with self.session() as s:
            return [f.to_dict(*Form.META) for f in s.scalars(select(Form).order_by(Form.created_at.desc()))]

    def get_form(self, fid: str) -> dict | None:
        with self.session() as s:
            f = s.get(Form, fid)
            return f and f.to_dict()

    def update_form(self, fid: str, form: dict, user: str) -> bool:
        with self.session() as s:
            if (f := s.get(Form, fid)) is None:
                return False
            f.form, f.title, f.updated_by, f.updated_at = form, form.get("title", ""), user, _now()
        return True
