"""/api/v1/dictionaries: catalog, items (tree, search, paging), CRUD, match, from-proposal. Errors: RFC 9457 via the app error processor."""
from apiflask import APIBlueprint, Schema, abort
from apiflask.fields import Integer, List, Nested, Raw, String
from apiflask.validators import Length, OneOf, Range, Regexp
from flask import current_app
from marshmallow import INCLUDE

from ..auth import auth, user
from . import store as ds
from .matcher import match as match_field
from .models import Item

bp = APIBlueprint("dictionaries", __name__, url_prefix="/api/v1/dictionaries", tag="Słowniki")
ID = Regexp(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
ITEM_ID = Regexp(r"^[A-Za-z0-9_.:-]{1,64}$")


class ItemIn(Schema):
    id = String(required=True, validate=ITEM_ID)
    name = String(required=True, validate=Length(1, 500))
    parent = String(load_default=None, allow_none=True, metadata={"description": "Parent item id (tree dictionaries such as TERYT)"})
    value = String(load_default=None, allow_none=True, validate=Length(0, 100), metadata={"description": "Stored value when it differs from the name, e.g. +48"})


class ItemPatch(Schema):
    name = String(validate=Length(1, 500))
    parent = String(allow_none=True)
    value = String(allow_none=True, validate=Length(0, 100))


class DictionaryIn(Schema):
    id = String(required=True, validate=ID, metadata={"description": "dictionaryName used in the form JSON"})
    name = String(required=True, validate=Length(1, 200))
    description = String(load_default="")
    levels = List(String(validate=Length(1, 100)), load_default=lambda: ["pozycja"], metadata={"description": "Level names; more than one means multiLevelTree"})
    aliases = List(String(validate=Length(1, 200)), load_default=list, metadata={"description": "Field labels the matcher should map to this dictionary"})
    items = List(Nested(ItemIn), load_default=list)


class DictionaryPatch(Schema):
    name = String(validate=Length(1, 200))
    description = String()
    levels = List(String(validate=Length(1, 100)))
    aliases = List(String(validate=Length(1, 200)))
    items = List(Nested(ItemIn), metadata={"description": "When present, replaces all items"})


class ItemsQuery(Schema):
    q = String(load_default="", metadata={"description": "Search in names (no diacritics/case needed); hits carry path = ancestor names"})
    parent = String(load_default=None, metadata={"description": "Children of this item; without it: top level"})
    limit = Integer(load_default=50, validate=Range(1, 500))
    offset = Integer(load_default=0, validate=Range(0))


class MatchIn(Schema):
    label = String(required=True, validate=Length(0, 500))
    source_label = String(load_default="")
    type = String(load_default="", validate=OneOf(["", "TEXT_FIELD", "TEXTAREA", "SELECT", "RADIO", "CHECKBOX", "NUMBER", "DATE", "EMAIL"]))
    options = List(String(), load_default=list)


class Proposal(Schema):
    """An entry of report.proposed_dictionaries; items: [{name, children?}] or plain names."""
    class Meta:
        unknown = INCLUDE

    id = String(required=True, validate=ID)
    name = String(required=True, validate=Length(1, 200))
    description = String(load_default="")
    levels = List(String(), load_default=lambda: ["pozycja"])
    aliases = List(String(), load_default=list)
    items = List(Raw(), required=True)


def _dict(s, did: str):
    return ds.get(s, did) or abort(404, f"Dictionary {did} not found")


def _conflict(e: ds.Conflict):
    abort(409, str(e))


def _store():
    return current_app.config["STORE"]


@bp.get("")
@bp.auth_required(auth)
@bp.doc(summary="Dictionary catalog: materials (protected), our catalog proposals, user dictionaries; items = item count")
def list_dictionaries():
    with _store().session() as s:
        return {"items": ds.catalog(s)}


@bp.get("/<did>")
@bp.auth_required(auth)
@bp.input(ItemsQuery, location="query")
@bp.doc(summary="One dictionary with a page of items", responses={404: "Not found"},
        description="Without `q`: children of `parent` (top level when absent), in display order. With `q`: matches anywhere in the tree, shortest first, each with `path`.")
def get_dictionary(did, query_data):
    with _store().session() as s:
        d = _dict(s, did)
        total, items = ds.items(s, d.id, **query_data)
        return {"dictionary": d.to_dict(), "total": total, "items": items}


@bp.post("")
@bp.auth_required(auth)
@bp.input(DictionaryIn, location="json")
@bp.doc(summary="Create a dictionary", responses={201: "Created", 409: "Id exists, duplicate item ids or unknown parent"})
def create_dictionary(json_data):
    try:
        with _store().session() as s:
            return ds.create(s, json_data, user()).to_dict(), 201
    except ds.Conflict as e:
        _conflict(e)


@bp.put("/<did>")
@bp.auth_required(auth)
@bp.input(DictionaryPatch, location="json")
@bp.doc(summary="Update a dictionary (fields given are replaced; items replaces all items)", responses={404: "Not found", 409: "Bad items"})
def update_dictionary(did, json_data):
    try:
        with _store().session() as s:
            return ds.update(s, _dict(s, did), json_data, user()).to_dict()
    except ds.Conflict as e:
        _conflict(e)


@bp.delete("/<did>")
@bp.auth_required(auth)
@bp.doc(summary="Delete a dictionary and its items", responses={204: "Deleted", 404: "Not found", 409: "Dictionary from the task materials (protected)"})
def delete_dictionary(did):
    try:
        with _store().session() as s:
            ds.remove(s, _dict(s, did))
    except PermissionError as e:
        abort(409, str(e), extra_data={"code": "protected_dictionary"})
    return "", 204


@bp.post("/<did>/items")
@bp.auth_required(auth)
@bp.input(ItemIn, location="json")
@bp.doc(summary="Add an item", responses={201: "Created", 404: "Dictionary not found", 409: "Id exists or unknown parent"})
def add_item(did, json_data):
    try:
        with _store().session() as s:
            return ds.add_item(s, _dict(s, did), json_data, user()), 201
    except ds.Conflict as e:
        _conflict(e)


@bp.put("/<did>/items/<iid>")
@bp.auth_required(auth)
@bp.input(ItemPatch, location="json")
@bp.doc(summary="Update an item (name, parent, value)", responses={404: "Not found", 409: "Unknown parent"})
def update_item(did, iid, json_data):
    try:
        with _store().session() as s:
            d = _dict(s, did)
            item = s.get(Item, (d.id, iid)) or abort(404, f"Item {iid} not found")
            return ds.update_item(s, d, item, json_data, user())
    except ds.Conflict as e:
        _conflict(e)


@bp.delete("/<did>/items/<iid>")
@bp.auth_required(auth)
@bp.doc(summary="Delete an item without children", responses={204: "Deleted", 404: "Not found", 409: "Item has children"})
def delete_item(did, iid):
    try:
        with _store().session() as s:
            d = _dict(s, did)
            ds.remove_item(s, d, s.get(Item, (d.id, iid)) or abort(404, f"Item {iid} not found"), user())
    except ds.Conflict as e:
        _conflict(e)
    return "", 204


@bp.post("/match")
@bp.auth_required(auth)
@bp.input(MatchIn, location="json")
@bp.doc(summary="Which dictionary fits a field (same function the generator calls)",
        description="`match` is null (no dictionary) or {dictionaryName, decision existing|new, score, reason, component, multiLevelTree, searchEnabled, proposal}.")
def match(json_data):
    with _store().session() as s:
        m = match_field(s, json_data["label"], json_data["source_label"], json_data["type"], json_data["options"])
        return {"match": m.to_dict() if m else None}


@bp.post("/from-proposal")
@bp.auth_required(auth)
@bp.input(Proposal, location="json")
@bp.doc(summary="Accept a proposal from report.proposed_dictionaries into the catalog", responses={201: "Created", 409: "Id taken or no items"},
        description="A proposal of one of our catalog dictionaries promotes it to a user dictionary (items replaced by the proposal's). Later forms match it as existing.")
def from_proposal(json_data):
    try:
        with _store().session() as s:
            return ds.from_proposal(s, json_data, user()).to_dict(), 201
    except ds.Conflict as e:
        _conflict(e)
