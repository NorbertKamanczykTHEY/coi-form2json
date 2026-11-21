"""Dictionary tables on the shared Base (coi.store). Layout and rules: app/docs/dictionaries.md."""
import re
import unicodedata

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..store import Base, _now

ORIGINS = ("materials", "catalog", "user")  # materials: named in the task, protected; catalog: our offline proposal; user: created via API


def norm(s: str) -> str:
    """Search/compare key: casefold, no diacritics (ł too), punctuation as spaces."""
    s = unicodedata.normalize("NFKD", s.casefold().replace("ł", "l"))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^\w]+", " ", s).split())


class Dictionary(Base):
    __tablename__ = "dictionaries"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # = dictionaryName in the form JSON
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    origin: Mapped[str] = mapped_column(String(16))
    levels: Mapped[list] = mapped_column(JSON, default=list)  # one name per tree level; len > 1 means multiLevelTree
    aliases: Mapped[list] = mapped_column(JSON, default=list)  # field labels that mean this dictionary (matcher input)
    created_by: Mapped[str] = mapped_column(String(255), default="system")
    created_at: Mapped[str] = mapped_column(String(32), default=_now)
    updated_by: Mapped[str | None] = mapped_column(String(255))
    updated_at: Mapped[str | None] = mapped_column(String(32))

    META = ("id", "name", "description", "origin", "levels", "aliases", "created_by", "created_at", "updated_by", "updated_at")

    def to_dict(self) -> dict:
        return {c: getattr(self, c) for c in self.META} | {"protected": self.origin == "materials"}


class Item(Base):
    __tablename__ = "dictionary_items"
    dictionary_id: Mapped[str] = mapped_column(ForeignKey("dictionaries.id", ondelete="CASCADE"), primary_key=True)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # official code where there is one (TERYT, ISO 3166)
    parent: Mapped[str | None] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(500))
    value: Mapped[str | None] = mapped_column(String(100))  # stored value when it differs from the name (+48)
    level: Mapped[int] = mapped_column(Integer, default=1)
    pos: Mapped[int] = mapped_column(Integer, default=0)  # display order among siblings
    norm: Mapped[str] = mapped_column(String(500))

    __table_args__ = (Index("dictionary_items_children", "dictionary_id", "parent", "pos"), Index("dictionary_items_norm", "norm"))

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "parent": self.parent, "level": self.level} | ({"value": self.value} if self.value else {})
