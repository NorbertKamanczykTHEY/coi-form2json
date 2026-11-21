"""Empty attachment-list lines on the real ParsedDocument of #5 (offline: Kreuzberg only, no LLM): skipped (EVAL-3 G3)."""
from pathlib import Path

import pytest

from coi.extraction.anchors import blocks_of, expand
from coi.extraction.gate import gate
from coi.extraction.postprocess import normalize
from coi.extraction.tree import FieldTree
from coi.parsing import parse

FORM5 = Path(__file__).resolve().parents[4] / "materials"


@pytest.mark.parametrize("ext", ["docx", "DOC", "PDF", "ODS"])
def test_empty_attachment_lines_of_form5_are_skipped(ext):
    path = next(FORM5.glob(f"5. */Wniosek o stwierdzenie nadpłaty podatku.{ext}"))
    blocks = blocks_of(parse(path.read_bytes(), path.name))
    head = next(a for a, t in blocks.items() if t.strip().lower().startswith("w załączeniu"))
    order = list(blocks)
    item = order[order.index(head) + 1]  # "1) korekta deklaracji"
    slots = order[order.index(head) + 2:order.index(head) + 4]  # "2) …", "3) …" (dots, underscores or nothing)
    tree = FieldTree.model_validate({  # what the model returns: the named upload, the empty lines dropped
        "title": "Wniosek", "applicant_kinds": ["person"], "dropped": [{"reason": "empty_slot", "src": [f"{slots[0]}-{slots[-1]}"]}],
        "pages": [{"title": "Załączniki", "sections": [{"title": "Załączniki", "fields": [
            {"key": "k", "label": "Korekta deklaracji", "source_label": "korekta deklaracji", "type": "FILE_UPLOADER", "src": [item]}]}]}]})
    out, _ = normalize(tree, blocks)
    ups = out.pages[0].sections[0].fields
    assert [(f.label, f.optional_evidence is None) for f in ups] == [("Korekta deklaracji", True)]
    assert set(slots) <= {a for d in out.dropped if d.reason == "empty_slot" for a in expand(d.src, blocks)}
    assert not gate(out, blocks)["lost_attachments"]  # "2)" is not a named attachment
