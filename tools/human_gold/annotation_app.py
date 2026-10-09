"""Visual-first local editor for human gold bibliography annotations.

This module deliberately renders cached PDFs itself and has no dependency on
the BiblioRef extractor.  It is a small local FastAPI application, not a
prediction UI: every zone, reference boundary, anchor, and flag is entered by
the annotator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import tempfile
import threading
import zlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response

from .schema import deterministic_sample_ids


_DOCUMENT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")


def _load_manifest(path: Path) -> dict[str, dict[str, Any]]:
    """Load the Task 1 JSONL manifest without importing its implementation."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot read manifest: {path}") from exc
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    rows = parsed if isinstance(parsed, list) else [json.loads(line) for line in text.splitlines() if line.strip()]
    if not isinstance(rows, list):
        raise ValueError("manifest must be a JSON array or JSONL")
    documents: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("manifest row is not an object")
        document_id = row.get("document_id")
        digest = row.get("sha256")
        if not isinstance(document_id, str) or not _DOCUMENT_ID.fullmatch(document_id):
            raise ValueError(f"invalid manifest document_id: {document_id!r}")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError(f"manifest requires SHA-256: {document_id}")
        try:
            int(digest, 16)
        except ValueError as exc:
            raise ValueError(f"manifest requires SHA-256: {document_id}") from exc
        if document_id in documents:
            raise ValueError(f"duplicate manifest document_id: {document_id}")
        documents[document_id] = row
    if not documents:
        raise ValueError("manifest is empty")
    return documents


def _ratio(value: Any, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise ValueError(f"invalid {label}")


def _integer(value: Any, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"invalid {label}")


def _validate_annotation(annotation: Any, partition: str = "primary") -> dict[str, Any]:
    """Validate the editable draft shape used by the Task 1 gold schema."""
    if not isinstance(annotation, dict):
        raise ValueError("annotation must be an object")
    required = {
        "document_id": str,
        "document_sha256": str,
        "annotator_id": str,
        "annotation_complete": bool,
        "document_has_target_bibliography": bool,
        "zones": list,
        "full_text_sample_ids": list,
    }
    for field, expected in required.items():
        if field not in annotation or not isinstance(annotation[field], expected):
            raise ValueError(f"missing or invalid field: {field}")
    if not annotation["document_id"] or not annotation["annotator_id"]:
        raise ValueError("document_id and annotator_id must be non-empty")
    digest = annotation["document_sha256"]
    if len(digest) != 64:
        raise ValueError("invalid document_sha256")
    try:
        int(digest, 16)
    except ValueError as exc:
        raise ValueError("invalid document_sha256") from exc
    samples = annotation["full_text_sample_ids"]
    if not all(isinstance(sample, str) and sample for sample in samples):
        raise ValueError("invalid full-text sample ID")

    zone_ids: set[str] = set()
    ref_ids: set[str] = set()
    for zone in annotation["zones"]:
        if not isinstance(zone, dict):
            raise ValueError("zone is not an object")
        for field, expected in (("gold_zone_id", str), ("role", str), ("heading_text", str),
                                ("heading_present", bool), ("references", list)):
            if field not in zone or not isinstance(zone[field], expected):
                raise ValueError(f"missing or invalid zone field: {field}")
        for field in ("start_page", "end_page"):
            _integer(zone.get(field), field)
        for field in ("start_y_ratio", "end_y_ratio"):
            _ratio(zone.get(field), field)
        if zone["start_page"] < 1 or zone["end_page"] < zone["start_page"]:
            raise ValueError("invalid zone page range")
        if zone["start_page"] == zone["end_page"] and zone["end_y_ratio"] < zone["start_y_ratio"]:
            raise ValueError("invalid zone y range")
        if not zone["gold_zone_id"] or zone["gold_zone_id"] in zone_ids:
            raise ValueError(f"duplicate or invalid gold_zone_id: {zone.get('gold_zone_id', '')}")
        zone_ids.add(zone["gold_zone_id"])
        ordinals: list[int] = []
        for ref in zone["references"]:
            if not isinstance(ref, dict):
                raise ValueError("reference is not an object")
            for field, expected in (("gold_ref_id", str), ("ordinal", int), ("start_page", int),
                                    ("start_y_ratio", (int, float)), ("start_anchor", str), ("flags", list)):
                if field not in ref or not isinstance(ref[field], expected):
                    raise ValueError(f"missing or invalid reference field: {field}")
            _integer(ref["ordinal"], "ordinal")
            _integer(ref["start_page"], "reference start_page")
            _ratio(ref["start_y_ratio"], "reference start_y_ratio")
            if ref["ordinal"] < 1:
                raise ValueError("invalid ordinal")
            if not ref["gold_ref_id"] or ref["gold_ref_id"] in ref_ids:
                raise ValueError(f"duplicate or invalid gold_ref_id: {ref.get('gold_ref_id', '')}")
            if not isinstance(ref["start_anchor"], str):
                raise ValueError("invalid start_anchor")
            if "visible_text_gold" in ref and not isinstance(ref["visible_text_gold"], str):
                raise ValueError("invalid visible_text_gold")
            if ref["start_page"] < zone["start_page"] or ref["start_page"] > zone["end_page"]:
                raise ValueError("reference start outside zone pages")
            ref_ids.add(ref["gold_ref_id"])
            ordinals.append(ref["ordinal"])
        if ordinals != list(range(1, len(ordinals) + 1)):
            raise ValueError(f"ordinal sequence invalid in zone: {zone['gold_zone_id']}")
    references = [reference for zone in annotation["zones"] for reference in zone["references"]]
    if annotation["annotation_complete"]:
        if not annotation["document_has_target_bibliography"]:
            if annotation["zones"] or samples:
                raise ValueError("no-target annotation must not contain zones or samples")
        else:
            expected = deterministic_sample_ids(annotation["document_id"], partition, references)
            if samples != expected or len(samples) != len(set(samples)):
                raise ValueError("invalid deterministic full-text sample IDs")
            by_id = {reference["gold_ref_id"]: reference for reference in references}
            if any(not isinstance(by_id[sample].get("visible_text_gold"), str) or not by_id[sample]["visible_text_gold"].strip() for sample in samples):
                raise ValueError("missing visible_text_gold for sampled reference")
    return annotation


class AnnotationStore:
    """One locked draft/history pair, using uniquely named replacement files."""

    def __init__(self, output: Path) -> None:
        self.output = output
        self.output.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def draft_path(self, document_id: str) -> Path:
        return self.output / f"{document_id}.json"

    def load(self, document_id: str) -> dict[str, Any] | None:
        path = self.draft_path(document_id)
        with self._lock:
            if not path.exists():
                return None
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError("saved draft is unreadable") from exc
        return data if isinstance(data, dict) else None

    def save(self, annotation: dict[str, Any]) -> None:
        payload = json.dumps(annotation, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        document_id = annotation["document_id"]
        history_row = {
            "timestamp": datetime.now(UTC).isoformat(),
            "document_id": document_id,
            "document_sha256": annotation["document_sha256"],
            "annotator_id": annotation["annotator_id"],
            "annotation_sha256": digest,
        }
        with self._lock:
            temporary_name: str | None = None
            try:
                fd, temporary_name = tempfile.mkstemp(
                    prefix=f".{document_id}.", suffix=".annotation.tmp", dir=self.output
                )
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary_name, self.draft_path(document_id))
                temporary_name = None
                with (self.output / ".history.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(history_row, sort_keys=True, separators=(",", ":")) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
            finally:
                if temporary_name:
                    try:
                        os.unlink(temporary_name)
                    except FileNotFoundError:
                        pass


class AnnotationService:
    def __init__(self, manifest: Path, pdf_cache: Path, output: Path, annotator_id: str) -> None:
        if not annotator_id:
            raise ValueError("annotator ID must be non-empty")
        self.documents = _load_manifest(Path(manifest))
        self.pdf_cache = Path(pdf_cache)
        self.store = AnnotationStore(Path(output))
        self.annotator_id = annotator_id

    def document(self, document_id: str) -> dict[str, Any]:
        try:
            return self.documents[document_id]
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="unknown document") from exc

    def pdf_path(self, document_id: str) -> Path:
        row = self.document(document_id)
        configured = row.get("pdf_filename", row.get("cache_filename", row.get("pdf_path")))
        candidates = [str(configured)] if isinstance(configured, str) and configured else []
        candidates.append(f"{document_id}.pdf")
        cache_root = self.pdf_cache.resolve()
        for candidate in candidates:
            path = (cache_root / candidate).resolve()
            if path.parent == cache_root and path.is_file():
                return path
        raise HTTPException(status_code=404, detail="cached PDF not found")

    def verified_pdf(self, document_id: str) -> Path:
        row = self.document(document_id)
        path = self.pdf_path(document_id)
        try:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            raise HTTPException(status_code=404, detail="cached PDF not readable") from exc
        if actual.lower() != row["sha256"].lower():
            raise HTTPException(status_code=409, detail="cached PDF SHA-256 does not match manifest")
        return path

    def validate_for_document(self, document_id: str, annotation: Any) -> dict[str, Any]:
        row = self.document(document_id)
        self.verified_pdf(document_id)
        try:
            checked = _validate_annotation(annotation, str(row.get("partition", "primary")))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if checked["document_id"] != document_id:
            raise HTTPException(status_code=422, detail="annotation document_id does not match route")
        if checked["document_sha256"].lower() != row["sha256"].lower():
            raise HTTPException(status_code=422, detail="annotation document_sha256 does not match manifest")
        if checked["annotator_id"] != self.annotator_id:
            raise HTTPException(status_code=422, detail="annotation annotator_id does not match CLI annotator")
        return checked


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def _bitmap_png(bitmap: Any) -> bytes:
    """Encode PDFium's RGB bitmap as PNG using only the stdlib."""
    if bitmap.mode != "RGB" or bitmap.n_channels != 3:
        raise ValueError(f"unexpected PDFium bitmap mode: {bitmap.mode}")
    row_bytes = bitmap.width * 3
    raw = bytes(bitmap.buffer)
    scanlines = []
    for row in range(bitmap.height):
        start = row * bitmap.stride
        scanlines.append(b"\x00" + raw[start:start + row_bytes])
    ihdr = struct.pack(">IIBBBBB", bitmap.width, bitmap.height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(b"".join(scanlines), level=6))
        + _png_chunk(b"IEND", b"")
    )


def _page_png(service: AnnotationService, document_id: str, page_number: int) -> bytes:
    if page_number < 1:
        raise HTTPException(status_code=404, detail="page not found")
    pdf_path = service.verified_pdf(document_id)
    try:
        document = pdfium.PdfDocument(str(pdf_path))
        if page_number > len(document):
            raise HTTPException(status_code=404, detail="page not found")
        page = document[page_number - 1]
        bitmap = page.render(scale=2, rev_byteorder=True)
        try:
            return _bitmap_png(bitmap)
        finally:
            bitmap.close()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail="unable to render cached PDF") from exc
    finally:
        try:
            document.close()
        except (UnboundLocalError, AttributeError):
            pass


def _browser_page(documents: dict[str, dict[str, Any]], annotator_id: str) -> str:
    document_bootstrap = [
        {"document_id": document_id, "sha256": row["sha256"], "partition": row.get("partition", "primary")}
        for document_id, row in documents.items()
    ]
    bootstrap = json.dumps({"documents": document_bootstrap, "annotator": annotator_id}).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><title>Human gold annotation</title>
<style>body{{font:14px system-ui;margin:1rem;max-width:1100px}} #page-image{{max-width:100%;border:1px solid #aaa;cursor:crosshair}} fieldset{{margin:.7rem 0}} input{{margin:.15rem}} #status{{white-space:pre-wrap}}</style>
</head><body>
<h1>Human-gold bibliography annotation</h1>
<p>Click the page image after choosing a marking action. Coordinates are saved as page-image ratios.</p>
<p>Reference IDs are generated per zone (for example, z001-r0001) and remain globally unique.</p>
<label>Document <select id=\"document\"></select></label>
<button id=\"previous\">Previous page</button><span id=\"page-number\">1</span><button id=\"next\">Next page</button>
<fieldset><legend>Mark on next click</legend>
<button data-action=\"zone-start\">Zone start</button><button data-action=\"zone-end\">Zone end</button><button data-action=\"reference\">Reference start</button></fieldset>
<fieldset><legend>Active zone</legend>
<label>Reactivate saved zone <select id=\"zone-select\"></select></label>
<label><input id=\"heading_present\" type=\"checkbox\" checked> heading_present</label>
<label>heading_text <input id=\"heading_text\" value=\"References\"></label>
<button id=\"update-heading\">Apply heading to active zone</button></fieldset>
<fieldset><legend>Active reference</legend>
<label>Reactivate saved reference <select id=\"reference-select\"></select></label>
<label>start_anchor <input id=\"start_anchor\" placeholder=\"Type visible text manually\"></label>
<label>reference flags <input id=\"flags\" placeholder=\"comma-separated flags\"></label>
<button id=\"update-reference\">Apply reference edits</button></fieldset>
<fieldset><legend>Deterministic full-text transcription tasks</legend><div id=\"tasks\"></div>
</fieldset>
<fieldset><legend>Non-target lookalikes</legend><label>non_target_lookalike_notes <input id=\"non_target_lookalike_notes\" placeholder=\"Describe any non-target list or lookalike\"></label><button id=\"update-notes\">Apply notes</button></fieldset>
<label><input id=\"document_has_target_bibliography\" type=\"checkbox\" checked> document_has_target_bibliography</label>
<label><input id=\"annotation_complete\" type=\"checkbox\"> annotation_complete</label>
<button id=\"save\">Save draft</button><pre id=\"status\"></pre><img id=\"page-image\" alt=\"Rendered PDF page\">
<script>
const boot = {bootstrap};
let documentId = boot.documents[0].document_id, page = 1, action = null, activeZone = -1, activeRef = -1;
let annotation;
const byId = id => document.getElementById(id);
const stableZoneId = n => `z${{String(n).padStart(3, '0')}}`;
const stableRefId = (zone, n) => `${{zone.gold_zone_id}}-r${{String(n).padStart(4, '0')}}`;
function blank() {{ const item = boot.documents.find(row => row.document_id === documentId); return {{document_id:documentId, document_sha256:item.sha256, annotator_id:boot.annotator, annotation_complete:false, document_has_target_bibliography:true, zones:[], full_text_sample_ids:[]}}; }}
function allReferences() {{ return annotation.zones.flatMap(zone => zone.references); }}
function stableHash(value) {{ let hash = 2166136261; for (const char of value) {{ hash ^= char.charCodeAt(0); hash = Math.imul(hash, 16777619); }} return hash >>> 0; }}
function deterministicSamples() {{ const refs = allReferences(); if (!refs.length || !annotation.document_has_target_bibliography) return []; const current = boot.documents.find(row => row.document_id === documentId); const wanted = current.partition === 'stress' ? 5 : 10; if (refs.length <= wanted) return refs.map(ref => ref.gold_ref_id); const chosen = new Set([0, refs.length - 1, Math.round((refs.length - 1) * .25), Math.round((refs.length - 1) * .5), Math.round((refs.length - 1) * .75)]); const remaining = refs.map((ref, index) => [index, stableHash(`${{documentId}}+${{index + 1}}`)]).filter(item => !chosen.has(item[0])).sort((a, b) => a[1] - b[1] || a[0] - b[0]); for (const item of remaining) {{ if (chosen.size >= wanted) break; chosen.add(item[0]); }} return [...chosen].sort((a, b) => a - b).map(index => refs[index].gold_ref_id); }}
function renderTasks() {{ const tasks = byId('tasks'); tasks.replaceChildren(); for (const id of annotation.full_text_sample_ids) {{ const ref = allReferences().find(item => item.gold_ref_id === id); const label = document.createElement('label'); label.textContent = `Transcribe visible text for ${{id}} `; const text = document.createElement('textarea'); text.rows = 2; text.cols = 60; text.value = ref && ref.visible_text_gold || ''; text.oninput = () => {{ if (ref) ref.visible_text_gold = text.value; }}; label.append(text); tasks.append(label, document.createElement('br')); }} }}
function renderSelectors() {{ const zones = byId('zone-select'); const refs = byId('reference-select'); zones.replaceChildren(); if (!annotation.zones.length) {{ activeZone = -1; activeRef = -1; refs.replaceChildren(); return; }} if (activeZone < 0 || activeZone >= annotation.zones.length) activeZone = 0; annotation.zones.forEach((zone, index) => {{ const option = document.createElement('option'); option.value = String(index); option.textContent = zone.gold_zone_id; zones.append(option); }}); zones.value = String(activeZone); const zoneRefs = annotation.zones[activeZone].references; refs.replaceChildren(); if (!zoneRefs.length) {{ activeRef = -1; return; }} if (activeRef < 0 || activeRef >= zoneRefs.length) activeRef = 0; zoneRefs.forEach((ref, index) => {{ const option = document.createElement('option'); option.value = String(index); option.textContent = ref.gold_ref_id; refs.append(option); }}); refs.value = String(activeRef); }}
function setControls() {{ renderSelectors(); byId('heading_present').checked = activeZone >= 0 ? annotation.zones[activeZone].heading_present : true; byId('heading_text').value = activeZone >= 0 ? annotation.zones[activeZone].heading_text : ''; byId('start_anchor').value = activeRef >= 0 ? annotation.zones[activeZone].references[activeRef].start_anchor : ''; byId('flags').value = activeRef >= 0 ? annotation.zones[activeZone].references[activeRef].flags.join(',') : ''; byId('document_has_target_bibliography').checked = annotation.document_has_target_bibliography; byId('annotation_complete').checked = annotation.annotation_complete; byId('non_target_lookalike_notes').value = (annotation.non_target_lookalike_notes || []).join('\\n'); renderTasks(); }}
function image() {{ byId('page-image').src = `/api/document/${{encodeURIComponent(documentId)}}/page/${{page}}`; byId('page-number').textContent = page; }}
async function load() {{ annotation = blank(); try {{ const r = await fetch(`/api/document/${{encodeURIComponent(documentId)}}/annotation`); if (r.ok) annotation = await r.json(); }} catch (_) {{}} setControls(); image(); }}
function clickRatio(event) {{ const box = event.currentTarget.getBoundingClientRect(); return Math.max(0, Math.min(1, (event.clientY - box.top) / box.height)); }}
document.querySelectorAll('[data-action]').forEach(button => button.onclick = () => {{ action = button.dataset.action; byId('status').textContent = `Click image to mark ${{action}}`; }});
byId('page-image').onclick = event => {{ if (!action) return; const y = clickRatio(event); if (action === 'zone-start') {{ const zone = {{gold_zone_id:stableZoneId(annotation.zones.length + 1), role:'references', start_page:page, end_page:page, start_y_ratio:y, end_y_ratio:y, heading_present:true, heading_text:'References', references:[]}}; annotation.zones.push(zone); activeZone = annotation.zones.length - 1; activeRef = -1; }} else if (action === 'zone-end' && activeZone >= 0) {{ const zone = annotation.zones[activeZone]; zone.end_page = page; zone.end_y_ratio = y; }} else if (action === 'reference' && activeZone >= 0) {{ const zone = annotation.zones[activeZone]; const ref = {{gold_ref_id:stableRefId(zone, zone.references.length + 1), ordinal:zone.references.length + 1, start_page:page, start_y_ratio:y, start_anchor:'', flags:[]}}; zone.references.push(ref); activeRef = zone.references.length - 1; annotation.full_text_sample_ids = deterministicSamples(); }} action = null; setControls(); }};
byId('update-heading').onclick = () => {{ if (activeZone < 0) return; const zone = annotation.zones[activeZone]; zone.heading_present = byId('heading_present').checked; zone.heading_text = byId('heading_text').value; }};
byId('update-reference').onclick = () => {{ if (activeZone < 0 || activeRef < 0) return; const ref = annotation.zones[activeZone].references[activeRef]; ref.start_anchor = byId('start_anchor').value; ref.flags = byId('flags').value.split(',').map(x => x.trim()).filter(Boolean); }};
byId('zone-select').onchange = () => {{ activeZone = Number(byId('zone-select').value); activeRef = -1; setControls(); }};
byId('reference-select').onchange = () => {{ activeRef = Number(byId('reference-select').value); setControls(); }};
byId('update-notes').onclick = () => {{ annotation.non_target_lookalike_notes = byId('non_target_lookalike_notes').value.split('\\n').map(note => note.trim()).filter(Boolean); }};
byId('previous').onclick = () => {{ if (page > 1) {{ page--; image(); }} }}; byId('next').onclick = () => {{ page++; image(); }};
byId('save').onclick = async () => {{ annotation.document_has_target_bibliography = byId('document_has_target_bibliography').checked; annotation.full_text_sample_ids = annotation.document_has_target_bibliography ? deterministicSamples() : []; annotation.annotation_complete = byId('annotation_complete').checked; setControls(); const response = await fetch(`/api/document/${{encodeURIComponent(documentId)}}/annotation`, {{method:'POST', headers:{{'content-type':'application/json'}}, body:JSON.stringify(annotation)}}); byId('status').textContent = response.ok ? 'Saved.' : `Save failed: ${{await response.text()}}`; }};
const chooser = byId('document'); boot.documents.forEach(row => {{ const option = document.createElement('option'); option.value = option.textContent = row.document_id; chooser.append(option); }}); chooser.onchange = () => {{ documentId = chooser.value; page = 1; activeZone = activeRef = -1; load(); }}; load();
</script></body></html>"""


def create_app(manifest: Path, pdf_cache: Path, output: Path, annotator_id: str) -> FastAPI:
    """Create an app bound to one manifest, cache, output directory, and annotator."""
    service = AnnotationService(manifest, pdf_cache, output, annotator_id)
    app = FastAPI(title="Human-gold annotation")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _browser_page(service.documents, service.annotator_id)

    @app.get("/api/document/{document_id}/page/{page}")
    def render_page(document_id: str, page: int) -> Response:
        return Response(_page_png(service, document_id, page), media_type="image/png")

    @app.get("/api/document/{document_id}/annotation")
    def get_annotation(document_id: str) -> dict[str, Any]:
        service.verified_pdf(document_id)
        draft = service.store.load(document_id)
        if draft is None:
            raise HTTPException(status_code=404, detail="annotation draft not found")
        return draft

    @app.post("/api/document/{document_id}/annotation")
    def save_annotation(document_id: str, annotation: dict[str, Any]) -> dict[str, Any]:
        checked = service.validate_for_document(document_id, annotation)
        service.store.save(checked)
        return checked

    return app


build_app = create_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local visual human-gold annotation app.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--pdf-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--annotator", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    import uvicorn

    uvicorn.run(create_app(args.manifest, args.pdf_cache, args.output, args.annotator), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
