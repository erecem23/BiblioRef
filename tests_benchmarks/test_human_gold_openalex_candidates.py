import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tools.human_gold.openalex_candidates import (
    apply_rejections,
    transform_openalex_snapshot,
)


def _work(work_id, host="repo.example.ca", license_value=None):
    return {
        "id": f"https://openalex.org/{work_id}",
        "title": f"Title {work_id}",
        "publication_year": 2024,
        "language": "en",
        "open_access": {"oa_status": "green"},
        "primary_location": {
            "pdf_url": f"https://{host}/{work_id}.pdf",
            "landing_page_url": f"https://{host}/items/{work_id}",
            "license": license_value,
        },
    }


def _config():
    return {
        "schema_version": "openalex_candidate_transform_v1",
        "document_id_prefix": "hg_openalex_",
        "metadata_source": "OpenAlex Works API metadata snapshot",
        "cache_policy": "local cache only pending redistribution review",
        "country_by_tld": {"ca": "CA"},
    }


def test_transform_is_deterministic_and_does_not_treat_oa_status_as_license():
    snapshot = {"results": [
        _work("W2", license_value="cc-by"),
        _work("W1"),
        _work("W3", host="generic.example.org"),
    ]}

    rows = transform_openalex_snapshot(snapshot, _config())

    assert [row["document_id"] for row in rows] == ["hg_openalex_w1", "hg_openalex_w2"]
    assert rows[0]["license_or_access_note"] == (
        "OpenAlex OA status=green; location license unavailable; "
        "local cache only pending redistribution review"
    )
    assert rows[1]["license_or_access_note"] == (
        "OpenAlex OA status=green; location license=cc-by; "
        "local cache only pending redistribution review"
    )


def test_structured_rejections_remove_only_listed_document_ids():
    rows = transform_openalex_snapshot(
        {"results": [_work("W1"), _work("W2")]}, _config()
    )
    rejections = [{
        "document_id": "hg_openalex_w1",
        "reason_code": "non_pdf_response",
        "evidence": {"detected_type": "HTML"},
    }]

    assert apply_rejections(rows, rejections) == [rows[1]]


def test_cli_writes_canonical_full_and_eligible_pools(tmp_path):
    from tools.human_gold.openalex_candidates import main

    snapshot = tmp_path / "snapshot.json"
    config = tmp_path / "transform.json"
    rejections = tmp_path / "rejections.jsonl"
    candidates = tmp_path / "candidates.jsonl"
    eligible = tmp_path / "eligible.jsonl"
    snapshot.write_text(json.dumps({"results": [_work("W2"), _work("W1")]}))
    config.write_text(json.dumps(_config()))
    rejections.write_text(json.dumps({
        "document_id": "hg_openalex_w2",
        "reason_code": "http_error",
        "evidence": {"http_status": 404},
    }) + "\n")

    assert main([
        "--snapshot", str(snapshot),
        "--transform-config", str(config),
        "--rejections", str(rejections),
        "--candidates-output", str(candidates),
        "--eligible-output", str(eligible),
    ]) == 0
    assert [json.loads(line)["document_id"] for line in candidates.read_text().splitlines()] == [
        "hg_openalex_w1", "hg_openalex_w2"
    ]
    assert [json.loads(line)["document_id"] for line in eligible.read_text().splitlines()] == [
        "hg_openalex_w1"
    ]


def _bash_works() -> bool:
    # On Windows without WSL, "bash" resolves to a stub that cannot start.
    if shutil.which("bash") is None:
        return False
    probe = subprocess.run(["bash", "-c", "true"], check=False, capture_output=True)
    return probe.returncode == 0


@pytest.mark.skipif(not _bash_works(), reason="replay_selection.sh needs a working bash")
def test_checked_in_pilot_selection_replays_byte_for_byte(tmp_path):
    script = Path("benchmarks/human_gold_v0_1/pilot/replay_selection.sh")

    completed = subprocess.run(
        ["bash", str(script), str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "pilot selection replay: PASS" in completed.stdout
