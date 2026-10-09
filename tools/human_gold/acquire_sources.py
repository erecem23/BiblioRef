"""Fail-closed public source acquisition for the human-gold benchmark.

Only repository metadata, URL/file naming, HTTP response bytes and PDF
renderability are inspected. PDF text is never read and BiblioRef is never
imported.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import unquote, urlsplit

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FRAGMENT_TOKEN = re.compile(
    r"(?:^|[_\-\s.])(abstract|abstrak|resumen|summary|ringkasan|cover|capa|portada|"
    r"chapter|chap|capitulo|capítulo|bab\d*|part\d*|pendahuluan|introduction|intro|"
    r"introducao|introdução|frontmatter|prelim(?:inary|inaries)?|annex|anexo|appendix|"
    r"priloge|contents?|indice|índice|index)(?:[_\-\s.]|$)",
    re.IGNORECASE,
)
_FULL_RELATIONS = {"fulltext", "full_text", "complete", "complete_thesis", "thesis", "dissertation"}


class AcquisitionError(RuntimeError):
    pass


def _filename(url: str) -> str:
    return unquote(Path(urlsplit(url).path).name)


def _looks_fragment_url(url: str) -> bool:
    filename = _filename(url)
    return bool(filename and _FRAGMENT_TOKEN.search(filename))


def _pinned_snapshot(candidate: dict) -> bool:
    value = candidate.get("metadata_snapshot_sha256")
    return isinstance(value, str) and bool(_SHA256.fullmatch(value.casefold()))


def _declares_thesis(candidate: dict) -> bool:
    for value in (candidate.get("metadata_work_type"), candidate.get("work_type"), candidate.get("type")):
        if isinstance(value, str) and value.casefold().replace("_", " ") in {
            "dissertation", "doctoral thesis", "master thesis", "thesis",
        }:
            return True
    query = candidate.get("metadata_source_query")
    return isinstance(query, str) and "type:dissertation" in query.casefold()


def _declared_fulltext(candidate: dict) -> str | None:
    rows = candidate.get("declared_bitstreams")
    if not isinstance(rows, list):
        return None
    options = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        url = row.get("url")
        relation = row.get("relation")
        if (
            isinstance(url, str) and url
            and isinstance(relation, str)
            and relation.casefold().replace("-", "_") in _FULL_RELATIONS
            and row.get("public") is True
            and not _looks_fragment_url(url)
        ):
            options.append(url)
    return sorted(set(options))[0] if options else None


def acquisition_ruling(candidate: dict) -> dict:
    document_id = candidate.get("document_id") if isinstance(candidate, dict) else None
    base = {"document_id": document_id, "eligible": False}
    if not isinstance(candidate, dict):
        return {**base, "reason_code": "invalid_candidate"}
    if not _pinned_snapshot(candidate):
        return {**base, "reason_code": "unpinned_metadata_snapshot"}
    if not _declares_thesis(candidate):
        return {**base, "reason_code": "metadata_not_thesis"}
    url = candidate.get("bitstream_url")
    if not isinstance(url, str) or not url:
        return {**base, "reason_code": "missing_public_bitstream"}
    resolved = url
    resolution = "recorded_bitstream"
    if _looks_fragment_url(url):
        replacement = _declared_fulltext(candidate)
        if not replacement:
            return {**base, "reason_code": "metadata_partial_bitstream", "original_bitstream_url": url}
        resolved = replacement
        resolution = "declared_fulltext_bitstream"
    return {
        **base,
        "eligible": True,
        "reason_code": None,
        "resolved_bitstream_url": resolved,
        "resolution": resolution,
    }


def make_serialized_validator(inner):
    """Serialize a native PDF validator while leaving HTTP acquisition parallel."""
    lock = threading.Lock()

    def validate(path: Path) -> bool:
        with lock:
            return bool(inner(path))

    return validate


def _pdfium_render_validator(path: Path) -> bool:
    try:
        import pypdfium2 as pdfium
        document = pdfium.PdfDocument(str(path))
        try:
            if len(document) < 1:
                return False
            page = document[0]
            try:
                bitmap = page.render(scale=0.5)
                try:
                    bitmap.to_pil()
                finally:
                    try:
                        bitmap.close()
                    except Exception:
                        pass
            finally:
                try:
                    page.close()
                except Exception:
                    pass
        finally:
            document.close()
    except Exception:
        return False
    return True


_default_pdf_validator = make_serialized_validator(_pdfium_render_validator)


def _response_status(response) -> int:
    status = getattr(response, "status", None)
    if status is None:
        status = getattr(response, "code", None)
    return int(status) if isinstance(status, int) else 200


def _content_type(response) -> str:
    headers = getattr(response, "headers", {})
    try:
        value = headers.get("Content-Type", "")
    except Exception:
        value = ""
    return str(value).split(";", 1)[0].strip().casefold()


def _read_bounded(response, max_bytes: int) -> bytes:
    if max_bytes <= 0:
        raise AcquisitionError("max_bytes must be positive")
    chunks = []
    total = 0
    while True:
        chunk = response.read(min(1024 * 1024, max_bytes + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > max_bytes:
            raise AcquisitionError("download_too_large")
    return b"".join(chunks)


def _round_observation(*, attempt: int, url: str, status_code: int | None = None,
                       content_type: str | None = None, body: bytes | None = None,
                       outcome: str = "downloaded", error: str | None = None) -> dict:
    row = {"attempt": attempt, "url": url, "outcome": outcome}
    if status_code is not None:
        row["status_code"] = status_code
    if content_type is not None:
        row["content_type"] = content_type
    if body is not None:
        row["bytes"] = len(body)
        row["sha256"] = hashlib.sha256(body).hexdigest()
    if error:
        row["error"] = error
    return row


def _download_once(url: str, *, opener, timeout: float, max_bytes: int, attempt: int):
    try:
        response = opener(url, timeout=timeout)
        with response:
            status = _response_status(response)
            content_type = _content_type(response)
            if status in {401, 403}:
                return _round_observation(attempt=attempt, url=url, status_code=status, content_type=content_type, outcome="access_denied"), None, "access_denied"
            if 500 <= status <= 599:
                body = None
                try:
                    body = _read_bounded(response, min(max_bytes, 64 * 1024))
                except Exception:
                    pass
                return _round_observation(attempt=attempt, url=url, status_code=status, content_type=content_type, body=body, outcome="http_server_error"), None, "http_server_error"
            if status >= 400:
                return _round_observation(attempt=attempt, url=url, status_code=status, content_type=content_type, outcome="http_error"), None, "http_error"
            try:
                body = _read_bounded(response, max_bytes)
            except AcquisitionError as exc:
                return _round_observation(attempt=attempt, url=url, status_code=status, content_type=content_type, outcome="download_too_large"), None, str(exc)
            observation = _round_observation(attempt=attempt, url=url, status_code=status, content_type=content_type, body=body)
            if not body.startswith(b"%PDF-"):
                observation["outcome"] = "non_pdf_response"
                return observation, None, "non_pdf_response"
            if content_type == "text/html" or body[:256].lstrip().lower().startswith((b"<html", b"<!doctype html")):
                observation["outcome"] = "non_pdf_response"
                return observation, None, "non_pdf_response"
            return observation, body, None
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        reason = "access_denied" if status in {401, 403} else "http_server_error" if 500 <= status <= 599 else "http_error"
        return _round_observation(attempt=attempt, url=url, status_code=status, outcome=reason, error=str(exc)), None, reason
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return _round_observation(attempt=attempt, url=url, outcome="transport_failure", error=str(exc)), None, "transport_failure"


def acquire_candidate(candidate: dict, cache_dir: Path, *, opener=urllib.request.urlopen,
                      pdf_validator=None, retries: int = 3, timeout: float = 30.0,
                      max_bytes: int = 250 * 1024 * 1024) -> dict:
    ruling = acquisition_ruling(candidate)
    result = {**candidate, "pre_output_eligibility": ruling, "rounds": [], "accepted": False}
    if not ruling["eligible"]:
        result["reason_code"] = ruling["reason_code"]
        return result
    if isinstance(retries, bool) or not isinstance(retries, int) or retries < 1:
        raise ValueError("retries must be a positive integer")
    url = ruling["resolved_bitstream_url"]
    downloads: list[bytes] = []
    attempt = 0
    while len(downloads) < 2:
        attempt += 1
        observation, body, reason = _download_once(url, opener=opener, timeout=timeout, max_bytes=max_bytes, attempt=attempt)
        result["rounds"].append(observation)
        if body is not None:
            downloads.append(body)
            continue
        if reason in {"http_server_error", "transport_failure"} and attempt < retries:
            continue
        result["reason_code"] = reason or "acquisition_failure"
        return result
    if downloads[0] != downloads[1]:
        result["reason_code"] = "unstable_repeated_download"
        return result
    body = downloads[0]
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    document_id = candidate.get("document_id")
    if not isinstance(document_id, str) or not document_id:
        raise ValueError("candidate requires document_id")
    final_path = cache_dir / f"{document_id}.pdf"
    fd, temp_name = tempfile.mkstemp(prefix=f".{document_id}.", suffix=".pdf.tmp", dir=cache_dir)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        temp_path = Path(temp_name)
        validator = pdf_validator or _default_pdf_validator
        if not validator(temp_path):
            result["reason_code"] = "unreadable_pdf"
            return result
        os.replace(temp_path, final_path)
    finally:
        try:
            Path(temp_name).unlink(missing_ok=True)
        except Exception:
            pass
    result.update({
        "accepted": True,
        "acquisition_accepted": True,
        "reason_code": None,
        "resolved_bitstream_url": url,
        "sha256": hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
        "cache_path": str(final_path),
    })
    return result


def _load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Acquire source PDFs without running BiblioRef.")
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--pdf-cache", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--max-bytes", type=int, default=250 * 1024 * 1024)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args(argv)
    rows = [acquire_candidate(row, args.pdf_cache, max_bytes=args.max_bytes, retries=args.retries) for row in _load_jsonl(args.candidates)]
    _write_jsonl(args.ledger, rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
