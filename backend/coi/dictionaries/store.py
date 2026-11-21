"""Catalog queries and seeding. Every function takes an open Session (Store.session()) so callers own the transaction."""
import gzip
import json
from pathlib import Path

from sqlalchemy import delete, func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..store import _now
from .matcher import canonical
from .models import Dictionary, Item, norm

HERE = Path(__file__).parent
CATALOG = json.loads((HERE / "catalog.json").read_text())["dictionaries"]


class Conflict(Exception):
    pass


def seed(store) -> list[str]:
    """Load catalog.json + seed/<id>.json.gz for dictionaries the database does not have yet; never overwrites edits."""
    added = []
    for d in CATALOG:
        try:
            with store.session() as s:  # one transaction per dictionary keeps a crash from leaving half a TERYT
                if s.get(Dictionary, d["id"]):
                    continue
                s.add(Dictionary(**{k: d[k] for k in ("id", "name", "description", "origin", "levels", "aliases")}))
                s.flush()
                items = json.loads(gzip.decompress((HERE / "seed" / f"{d['id']}.json.gz").read_bytes()))
                _insert(s, d["id"], items)
            added.append(d["id"])
        except IntegrityError:  # another worker seeded it first
            continue
    return added


def _insert(s: Session, did: str, items: list[dict]) -> None:
    rows = [{"dictionary_id": did, "id": str(i["id"]), "parent": i.get("parent"), "name": i["name"], "value": i.get("value"),
             "level": i.get("level", 1), "pos": n, "norm": norm(i["name"])} for n, i in enumerate(items)]
    for k in range(0, len(rows), 5000):
        s.execute(insert(Item), rows[k:k + 5000])


def counts(s: Session) -> dict[str, int]:
    return dict(s.execute(select(Item.dictionary_id, func.count()).group_by(Item.dictionary_id)).all())


def catalog(s: Session) -> list[dict]:
    n = counts(s)
    return [d.to_dict() | {"items": n.get(d.id, 0)} for d in s.scalars(select(Dictionary).order_by(Dictionary.origin.desc(), Dictionary.id))]


def items(s: Session, did: str, *, q: str = "", parent: str | None = None, limit: int = 50, offset: int = 0) -> tuple[int, list[dict]]:
    """Children of `parent` (roots when None), or, with q, matches anywhere in the tree with their ancestor path."""
    where = [Item.dictionary_id == did]
    if q:
        where.append(Item.norm.contains(norm(q)))
        if parent:
            where.append(Item.parent == parent)
        order = (func.length(Item.name), Item.level, Item.pos)  # shortest name first puts the exact hit on top
    else:
        where.append(Item.parent == parent if parent else Item.parent.is_(None))
        order = (Item.pos,)
    total = s.scalar(select(func.count()).select_from(Item).where(*where))
    rows = s.scalars(select(Item).where(*where).order_by(*order).limit(limit).offset(offset)).all()
    out = [r.to_dict() for r in rows]
    if q:
        _paths(s, did, out)
    return total, out


def _paths(s: Session, did: str, out: list[dict]) -> None:
    """Adds path = ancestor names, root first, so 'Nowa Wieś' hits can be told apart. One query per tree level."""
    for o in out:
        o["path"] = []
    pending: dict[str, list] = {}
    for o in out:
        if o["parent"]:
            pending.setdefault(o["parent"], []).append(o)
    while pending:
        found = s.scalars(select(Item).where(Item.dictionary_id == did, Item.id.in_(pending))).all()
        nxt: dict[str, list] = {}
        for it in found:
            for o in pending[it.id]:
                o["path"].insert(0, it.name)
                if it.parent:
                    nxt.setdefault(it.parent, []).append(o)
        pending = nxt


def get(s: Session, did: str) -> Dictionary | None:
    return s.get(Dictionary, canonical(did))


def create(s: Session, d: dict, user: str, origin: str = "user") -> Dictionary:
    if get(s, d["id"]):
        raise Conflict(f"Dictionary {d['id']} already exists")
    row = Dictionary(id=d["id"], name=d["name"], description=d.get("description", ""), origin=origin,
                     levels=d.get("levels") or ["pozycja"], aliases=d.get("aliases", []), created_by=user)
    s.add(row)
    s.flush()
    _check_tree(d.get("items", []))
    _insert(s, row.id, d.get("items", []))
    return row


def update(s: Session, row: Dictionary, d: dict, user: str) -> Dictionary:
    for k in ("name", "description", "levels", "aliases"):
        if k in d:
            setattr(row, k, d[k])
    if "items" in d:  # PUT with items replaces them all
        _check_tree(d["items"])
        s.execute(delete(Item).where(Item.dictionary_id == row.id))
        _insert(s, row.id, d["items"])
    row.updated_by, row.updated_at = user, _now()
    return row


def remove(s: Session, row: Dictionary) -> None:
    if row.origin == "materials":
        raise PermissionError(f"{row.id} comes from the task materials and cannot be deleted")
    s.execute(delete(Item).where(Item.dictionary_id == row.id))  # no reliance on SQLite foreign_keys pragma
    s.delete(row)


def _check_tree(items: list[dict]) -> None:
    ids = [str(i["id"]) for i in items]
    if len(set(ids)) != len(ids):
        raise Conflict("Item ids must be unique within a dictionary")
    if bad := {i["parent"] for i in items if i.get("parent")} - set(ids):
        raise Conflict(f"Unknown parent ids: {sorted(bad)[:5]}")


def add_item(s: Session, row: Dictionary, it: dict, user: str) -> dict:
    if s.get(Item, (row.id, it["id"])):
        raise Conflict(f"Item {it['id']} already exists")
    parent = _parent(s, row.id, it.get("parent"))
    pos = (s.scalar(select(func.max(Item.pos)).where(Item.dictionary_id == row.id)) or 0) + 1
    item = Item(dictionary_id=row.id, id=it["id"], parent=it.get("parent"), name=it["name"], value=it.get("value"),
                level=parent.level + 1 if parent else 1, pos=pos, norm=norm(it["name"]))
    s.add(item)
    row.updated_by, row.updated_at = user, _now()
    return item.to_dict()


def update_item(s: Session, row: Dictionary, item: Item, it: dict, user: str) -> dict:
    if "parent" in it and it["parent"] != item.parent:
        if it["parent"] == item.id:
            raise Conflict("An item cannot be its own parent")
        item.parent = it["parent"]
        p = _parent(s, row.id, it["parent"])
        item.level = p.level + 1 if p else 1
    if "name" in it:
        item.name, item.norm = it["name"], norm(it["name"])
    if "value" in it:
        item.value = it["value"]
    row.updated_by, row.updated_at = user, _now()
    return item.to_dict()


def remove_item(s: Session, row: Dictionary, item: Item, user: str) -> None:
    if s.scalar(select(func.count()).select_from(Item).where(Item.dictionary_id == row.id, Item.parent == item.id)):
        raise Conflict(f"Item {item.id} has children; delete them first")
    s.delete(item)
    row.updated_by, row.updated_at = user, _now()


def _parent(s: Session, did: str, pid: str | None) -> Item | None:
    if not pid:
        return None
    if p := s.get(Item, (did, pid)):
        return p
    raise Conflict(f"Unknown parent {pid}")


def flatten(tree: list, parent: str | None = None, level: int = 1) -> list[dict]:
    """Proposal items [{name, children?} | "name"] -> flat items with ids 1, 1.2, ... (parent first)."""
    out = []
    for n, node in enumerate(tree, 1):
        node = {"name": node} if isinstance(node, str) else node
        nid = str(node.get("id") or (f"{parent}.{n}" if parent else n))
        out.append({"id": nid, "name": node["name"], "parent": parent, "level": level} | ({"value": node["value"]} if node.get("value") else {}))
        out += flatten(node.get("children", []), nid, level + 1)
    return out


def from_proposal(s: Session, p: dict, user: str) -> Dictionary:
    """report.proposed_dictionaries entry -> catalog entry. A catalog-origin proposal is promoted in place (origin user, items replaced)."""
    d = {"id": p["id"], "name": p["name"], "description": p.get("description", ""), "levels": p.get("levels") or ["pozycja"],
         "aliases": p.get("aliases", []), "items": flatten(p.get("items", []))}
    if not d["items"]:
        raise Conflict("A proposal without items cannot become a dictionary (rule: new dictionaries only with a list of items)")
    row = s.get(Dictionary, d["id"])
    if row is None:
        return create(s, d, user)
    if row.origin != "catalog":
        raise Conflict(f"Dictionary {d['id']} already exists")
    row.origin = "user"
    d["aliases"] = list(dict.fromkeys(row.aliases + d["aliases"]))  # a proposal rarely carries aliases; keep the catalog's
    return update(s, row, d, user)
