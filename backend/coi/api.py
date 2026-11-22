"""REST API /api/v1 (app/docs/api-assumptions.md A1-A12). Errors are RFC 9457 problem+json with a `code` field."""
import hashlib
import json
import logging
import queue
import threading
from http import HTTPStatus

import openai
from apiflask import APIBlueprint, HTTPError, Schema, abort
from apiflask.fields import Boolean, File, List, Raw, String
from flask import Response, current_app, request
from kreuzberg import KreuzbergError
from marshmallow import INCLUDE
from marshmallow.validate import Length

from . import pipeline
from .auth import auth, user
from .extraction.extract import ExtractionError
from .generator import validate
from .parsing import TooLarge, UnsupportedType
from .parsing.detect import ALLOWED

log = logging.getLogger(__name__)
bp = APIBlueprint("api", __name__, url_prefix="/api/v1", tag="COI")
FORBIDDEN = ";:><\\/|'*%$"
CODES = {400: "bad_request", 401: "unauthorized", 404: "not_found", 405: "method_not_allowed", 409: "conflict", 413: "file_too_large",
         415: "unsupported_type", 422: "unprocessable", 500: "internal_error", 502: "llm_error", 504: "llm_timeout"}


def problem_body(e: HTTPError) -> dict:
    status = e.status_code
    body = {"type": "about:blank", "title": HTTPStatus(status).phrase, "status": status, "detail": e.message, "code": CODES.get(status, "error")}
    if e.detail:  # webargs validation messages: {location: {field: [msg]}}
        body["errors"] = e.detail
    return body | (e.extra_data or {})


def problem(e: HTTPError):
    return problem_body(e), e.status_code, (e.headers or {}) | {"Content-Type": "application/problem+json"}


# schemas
class Upload(Schema):
    file = File(required=True, metadata={"description": "Exactly one file: " + ", ".join(sorted(ALLOWED))})


class Variant(Schema):
    report = Boolean(load_default=False, metadata={"description": "Return the envelope {id, form, report}"})
    editor = Boolean(load_default=False, metadata={"description": "Add editor {source, field_map} to the envelope"})


class Form(Schema):
    """COI form JSON (importowanyPlikJsonSchemat); checked against the JSON Schema, not here."""
    class Meta:
        unknown = INCLUDE

    title = Raw(allow_none=True)
    tabs = Raw(allow_none=True)
    flow = Raw(allow_none=True)


# helpers
def violations(form) -> list[dict]:
    return validate(form)  # JSON Schema + rules 1-6 of "Reguły techniczne" + JSONata references


def _body(fid: str, form: dict, report: dict, editor: dict, q: dict):
    if not (q["report"] or q["editor"]):
        return form
    return {"id": fid, "form": form, "report": report} | ({"editor": editor} if q["editor"] else {})


def _convert(data: bytes, name: str, on_event, cfg, store) -> pipeline.Result:
    try:
        return pipeline.convert(data, name, on_event, cfg, store)
    except TooLarge as e:
        abort(413, str(e))
    except UnsupportedType as e:
        abort(415, str(e))
    except ExtractionError as e:
        abort(502, f"Field extraction failed: {e}")
    except openai.APITimeoutError:
        abort(504, "LLM timed out")
    except openai.APIError as e:
        abort(502, f"LLM error: {type(e).__name__}")
    except (KreuzbergError, OSError, ValueError) as e:  # broken or unreadable file
        log.warning("convert failed: %s", type(e).__name__)
        abort(422, f"Could not read the form: {type(e).__name__}", extra_data={"code": "unreadable_form"})


def _sse(event: str, payload, fid: str | None = None) -> str:
    return (f"id: {fid}\n" if fid else "") + f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _stream(work) -> Response:
    """Runs work(on_event) in a thread; stage/escalation/warning events, then result (id: = form id) or error (problem body)."""
    events: queue.Queue = queue.Queue()

    def target():
        try:
            fid, body = work(lambda ev, p: events.put(_sse(ev, p)))
            events.put(_sse("result", body, fid))
        except HTTPError as e:
            events.put(_sse("error", problem_body(e)))
        except Exception:
            log.exception("convert failed")
            events.put(_sse("error", problem_body(HTTPError(500))))
        events.put(None)

    threading.Thread(target=target, daemon=True).start()
    return Response(iter(events.get, None), mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


ERRORS = {400: "No file, more than one file, or a bad file name", 413: "File too large", 415: "Extension not allowed or MIME does not match it",
          422: "The file could not be read", 502: "LLM error", 504: "LLM timeout"}


def optional_security(spec: dict) -> dict:
    """OpenAPI: Authorization is optional on the two public-convert endpoints (`{}` = no auth is an allowed alternative)."""
    for path in ("/api/v1/forms", "/api/v1/forms/validate"):
        op = spec["paths"][path]["post"]
        op["security"] = [{}, *op.get("security", [])]
    return spec


# endpoints
@bp.post("/forms")
@bp.auth_required(auth, optional=True)  # AUTH_PUBLIC_CONVERT: without the header it runs as "anonymous"; a bad token is still 401
@bp.input(Variant, location="query")
@bp.input(Upload, location="files")
@bp.doc(summary="Convert one file into COI form JSON", responses={200: "COI form JSON (or the envelope with ?report / ?editor)", **ERRORS},
        description="With `Accept: text/event-stream` the response is an SSE stream: `stage`, `escalation`, `warning` events, "
                    "then `result` (data = the same body as the plain call, SSE `id:` = form id) or `error` (problem body). "
                    "The uploaded file lives only in memory for the request; only the result is stored.")
def create_form(query_data, files_data):
    c = current_app.config
    if len(list(request.files.items(multi=True))) != 1:
        abort(400, "Send exactly one file in the field `file`")
    f = request.files["file"]
    name = f.filename or ""
    if not name or len(name) > c["MAX_FILENAME_LEN"] or set(name) & set(FORBIDDEN):
        abort(400, f"Invalid file name: 1-{c['MAX_FILENAME_LEN']} characters, none of {FORBIDDEN}", extra_data={"code": "invalid_filename"})
    data = f.read()
    cfg, store, uid = c["COI"], c["STORE"], user(public=True)
    if len(data) > cfg.max_file_mb * 2**20:
        abort(413, f"File is larger than {cfg.max_file_mb} MB")
    sha = hashlib.sha256(data).hexdigest()
    log.info("convert sha256=%s size=%d user=%s", sha[:12], len(data), uid)  # no file name or content in logs

    def work(on_event):
        r = _convert(data, name, on_event, cfg, store)
        fid = store.add_form(filename=name, sha256=sha, user=uid, form=r.form, report=r.report, editor=r.editor)
        return fid, _body(fid, r.form, r.report, r.editor, query_data)

    if "text/event-stream" in request.headers.get("Accept", ""):
        return _stream(work)
    fid, body = work(lambda *_: None)
    return body, 200, {"Location": f"/api/v1/forms/{fid}"}


@bp.get("/forms")
@bp.auth_required(auth)
@bp.doc(summary="List stored forms (newest first, metadata only)")
def list_forms():
    return {"items": current_app.config["STORE"].list_forms()}


@bp.get("/forms/<form_id>")
@bp.auth_required(auth)
@bp.input(Variant, location="query")
@bp.doc(summary="One stored form (same ?report / ?editor as POST)", responses={200: "COI form JSON or envelope", 404: "Not found"})
def get_form(form_id, query_data):
    row = current_app.config["STORE"].get_form(form_id) or abort(404, "Form not found")
    return _body(form_id, row["form"], row["report"], row["editor"], query_data)


@bp.put("/forms/<form_id>")
@bp.auth_required(auth)
@bp.input(Form, location="json")
@bp.doc(summary="Save a corrected form JSON (validated first)", responses={200: "Saved form", 404: "Not found", 422: "Form JSON is invalid (errors[])"})
def put_form(form_id, json_data):
    store = current_app.config["STORE"]
    if store.get_form(form_id) is None:
        abort(404, "Form not found")
    if errors := violations(json_data):
        abort(422, "Form JSON is invalid", extra_data={"code": "invalid_form", "errors": errors})
    store.update_form(form_id, json_data, user())
    return json_data


@bp.delete("/forms/<form_id>")
@bp.auth_required(auth)
@bp.output({}, status_code=204)
@bp.doc(summary="Delete a stored form", responses={204: "Deleted", 404: "Not found"})
def delete_form(form_id):
    if not current_app.config["STORE"].delete_form(form_id):
        abort(404, "Form not found")
    return ""


class Resolved(Schema):
    resolved = List(String(validate=Length(1, 300)), required=True,
                    metadata={"description": "Review keys the clerk fixed or accepted: report.needs_review[].field_id, else .key. Replaces the list."})


@bp.put("/forms/<form_id>/resolved")
@bp.auth_required(auth)
@bp.input(Resolved, location="json")
@bp.output(Resolved)
@bp.doc(summary="Save which review items are resolved", responses={200: "Saved list", 404: "Not found"},
        description="Stored as editor.resolved (GET ?editor=true). Kept by regenerate; field ids are stable.")
def put_resolved(form_id, json_data):
    resolved = list(dict.fromkeys(json_data["resolved"]))
    if not current_app.config["STORE"].set_resolved(form_id, resolved, user()):
        abort(404, "Form not found")
    return {"resolved": resolved}


class Regenerate(Schema):
    applicant_self_only = Boolean(required=True, metadata={"description": "true: applicant acts only in person (no proxy, no "
                                  "„Podmiot wniosku” for a person; Standardy s.9). false: proxy allowed (default)."})


@bp.post("/forms/<form_id>/regenerate")
@bp.auth_required(auth)
@bp.input(Variant, location="query")
@bp.input(Regenerate, location="json")
@bp.doc(summary="Rebuild a stored form with editor overrides (no LLM)",
        responses={200: "Rebuilt form (or the envelope with ?report / ?editor)", 404: "Not found", 409: "Stored before FieldTree was kept"},
        description="Rebuilds the COI JSON from the stored FieldTree (`editor.tree`) with the given overrides and saves it, "
                    "replacing manual edits. `editor.applicant_self_only` = {value, source: dokument|domyślnie|edytor, quote}.")
def regenerate_form(form_id, query_data, json_data):
    store = current_app.config["STORE"]
    row = store.get_form(form_id) or abort(404, "Form not found")
    try:
        r = pipeline.regenerate(row, store, json_data["applicant_self_only"])
    except pipeline.NoStoredTree:
        abort(409, "This form was stored before its FieldTree was kept; convert the file again", extra_data={"code": "no_stored_tree"})
    store.replace_form(form_id, r.form, r.report, r.editor, user())
    return _body(form_id, r.form, r.report, r.editor, query_data)


@bp.post("/forms/validate")
@bp.auth_required(auth, optional=True)
@bp.input(Form, location="json")
@bp.doc(summary="Validate a COI form JSON", description="Returns {valid, errors[{path, message, rule}]}: the task's JSON Schema, rules R1-R6 of \"Reguły techniczne\", unique techName, choice fields, JSONata references.")
def validate_form(json_data):
    user(public=True)
    errors = violations(json_data)
    return {"valid": not errors, "errors": errors}


@bp.get("/info")
@bp.doc(summary="Version, limits and model tiers (no token needed)")
def info():
    c = current_app.config
    cfg = c["COI"]
    return {
        "version": c["VERSION"],
        "limits": {"max_file_mb": cfg.max_file_mb, "max_filename_len": c["MAX_FILENAME_LEN"],
                   "extensions": sorted(ALLOWED), "forbidden_filename_chars": FORBIDDEN},
        "llm": {"tiers": json.loads(cfg.ladder_path.read_text())["tiers"]},
        "auth": {"alg": c["JWT_ALG"]},
        "generator": "templates-v1",
    }
