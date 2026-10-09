from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tools.human_gold.acquire_sources import (
    acquisition_ruling,
    acquire_candidate,
)


class FakeResponse:
    def __init__(self, body: bytes, *, status: int = 200, content_type: str = "application/pdf"):
        self._body = body
        self.status = status
        self.headers = {"Content-Type": content_type, "Content-Length": str(len(body))}
        self._offset = 0

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self._body) - self._offset
        chunk = self._body[self._offset:self._offset + size]
        self._offset += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def thesis(**overrides):
    row = {
        "document_id": "d1",
        "repository": "repo.example",
        "country": "AR",
        "language": "es",
        "publication_year": 2020,
        "title": "A thesis",
        "source_item_url": "https://repo.example/item/1",
        "bitstream_url": "https://repo.example/bitstreams/full/download",
        "stable_source_id": "oai:repo:1",
        "metadata_work_type": "dissertation",
        "metadata_snapshot_sha256": "a" * 64,
    }
    row.update(overrides)
    return row


def test_fragment_filename_fails_closed_without_declared_fulltext_relation():
    ruling = acquisition_ruling(thesis(bitstream_url="https://repo.example/files/COVER.pdf"))
    assert ruling["eligible"] is False
    assert ruling["reason_code"] == "metadata_partial_bitstream"


def test_multilingual_obvious_fragment_filename_fails_closed():
    ruling = acquisition_ruling(thesis(bitstream_url="https://repo.example/73661/53/PENDAHULUAN.pdf"))
    assert ruling["eligible"] is False
    assert ruling["reason_code"] == "metadata_partial_bitstream"


def test_fragment_can_use_only_declared_public_fulltext_bitstream():
    ruling = acquisition_ruling(thesis(
        bitstream_url="https://repo.example/files/ABSTRACT.pdf",
        declared_bitstreams=[
            {"url": "https://repo.example/files/thesis.pdf", "relation": "fulltext", "public": True},
            {"url": "https://repo.example/files/chapter1.pdf", "relation": "chapter", "public": True},
        ],
    ))
    assert ruling["eligible"] is True
    assert ruling["resolved_bitstream_url"] == "https://repo.example/files/thesis.pdf"
    assert ruling["resolution"] == "declared_fulltext_bitstream"


def test_missing_pinned_metadata_snapshot_fails_closed():
    ruling = acquisition_ruling(thesis(metadata_snapshot_sha256=None))
    assert ruling["eligible"] is False
    assert ruling["reason_code"] == "unpinned_metadata_snapshot"


def test_openalex_identity_without_explicit_dissertation_metadata_fails_closed():
    row = thesis(
        metadata_work_type=None,
        metadata_source_query=None,
        openalex_id="https://openalex.org/W1",
        metadata_source="OpenAlex Works API metadata snapshot",
    )
    ruling = acquisition_ruling(row)
    assert ruling["eligible"] is False
    assert ruling["reason_code"] == "metadata_not_thesis"


def test_access_denied_is_candidate_level_rejection(tmp_path):
    def opener(*args, **kwargs):
        return FakeResponse(b"forbidden", status=403, content_type="text/plain")

    result = acquire_candidate(thesis(), tmp_path, opener=opener, pdf_validator=lambda _: True)
    assert result["accepted"] is False
    assert result["reason_code"] == "access_denied"
    assert result["rounds"][0]["status_code"] == 403


def test_non_pdf_response_is_rejected_before_pdfium(tmp_path):
    called = False

    def validator(_):
        nonlocal called
        called = True
        return True

    result = acquire_candidate(
        thesis(),
        tmp_path,
        opener=lambda *a, **k: FakeResponse(b"<html>not pdf</html>", content_type="text/html"),
        pdf_validator=validator,
    )
    assert result["accepted"] is False
    assert result["reason_code"] == "non_pdf_response"
    assert called is False


def test_two_identical_pdf_downloads_are_required_and_retained(tmp_path):
    pdf = b"%PDF-1.7\nsynthetic-pdf-for-test\n%%EOF\n"
    calls = []

    def opener(*args, **kwargs):
        calls.append(1)
        return FakeResponse(pdf)

    result = acquire_candidate(thesis(), tmp_path, opener=opener, pdf_validator=lambda p: p.read_bytes() == pdf)
    assert result["accepted"] is True
    assert len(calls) == 2
    assert len(result["rounds"]) == 2
    assert result["rounds"][0]["sha256"] == result["rounds"][1]["sha256"] == hashlib.sha256(pdf).hexdigest()
    assert result["sha256"] == hashlib.sha256(pdf).hexdigest()
    assert result["bytes"] == len(pdf)
    assert Path(result["cache_path"]).read_bytes() == pdf


def test_different_repeated_downloads_are_rejected(tmp_path):
    bodies = iter([
        b"%PDF-1.7\nfirst\n%%EOF\n",
        b"%PDF-1.7\nsecond\n%%EOF\n",
    ])

    result = acquire_candidate(
        thesis(), tmp_path,
        opener=lambda *a, **k: FakeResponse(next(bodies)),
        pdf_validator=lambda _: True,
    )
    assert result["accepted"] is False
    assert result["reason_code"] == "unstable_repeated_download"
    assert len(result["rounds"]) == 2


def test_download_is_bounded(tmp_path):
    oversized = b"%PDF-1.7\n" + b"x" * 200
    result = acquire_candidate(
        thesis(), tmp_path,
        opener=lambda *a, **k: FakeResponse(oversized),
        pdf_validator=lambda _: True,
        max_bytes=64,
    )
    assert result["accepted"] is False
    assert result["reason_code"] == "download_too_large"


def test_unreadable_pdf_is_rejected_after_two_matching_downloads(tmp_path):
    pdf = b"%PDF-1.7\ninvalid\n%%EOF\n"
    result = acquire_candidate(
        thesis(), tmp_path,
        opener=lambda *a, **k: FakeResponse(pdf),
        pdf_validator=lambda _: False,
    )
    assert result["accepted"] is False
    assert result["reason_code"] == "unreadable_pdf"


def test_http_server_error_after_retries_is_recorded(tmp_path):
    calls = []

    def opener(*args, **kwargs):
        calls.append(1)
        return FakeResponse(b"server error", status=503, content_type="text/plain")

    result = acquire_candidate(thesis(), tmp_path, opener=opener, pdf_validator=lambda _: True, retries=3)
    assert result["accepted"] is False
    assert result["reason_code"] == "http_server_error"
    assert len(calls) == 3
    assert len(result["rounds"]) == 3


def test_transport_failure_is_recorded_after_retries(tmp_path):
    calls = []

    def opener(*args, **kwargs):
        calls.append(1)
        raise OSError("network down")

    result = acquire_candidate(thesis(), tmp_path, opener=opener, pdf_validator=lambda _: True, retries=2)
    assert result["accepted"] is False
    assert result["reason_code"] == "transport_failure"
    assert len(calls) == 2
    assert all(row["outcome"] == "transport_failure" for row in result["rounds"])
