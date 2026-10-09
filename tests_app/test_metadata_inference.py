from biblioref.metadata.inference import (
    apply_inferences, confirm_inference, field_origin, inference_of, propose_inferences, public_inference, undo_inference,
)

UNC, UNLP = "Universidad Nacional de Córdoba", "Universidad Nacional de La Plata"
PSI = "Doctorado en Psicología"


def _doc(i, **meta):
    return {"id": f"d{i}", "thesis_id": f"T{i:04d}", "path": "", "metadata": meta}


def _project():
    peers = [_doc(i, university=UNC, program=PSI, faculty="Facultad de Psicología", degree_level="doctorado") for i in range(1, 4)]
    return peers + [
        _doc(8, university=UNC, program=PSI, degree_level="doctorado"),                      # faculty from peers
        _doc(11, university=UNC, faculty="Facultad de Psicología", degree_level="doctorado"),  # program from level + faculty
        _doc(10, program=PSI, degree_level="doctorado"),                                      # university: not inferable
        _doc(20, university=UNLP, program=PSI, degree_level="doctorado"),                     # no UNLP peers: no faculty
        _doc(30, faculty="Facultad de Humanidades y Ciencias de la Educación", degree_level="doctorado"),
    ]


def test_rules_fill_only_what_the_evidence_supports():
    docs = _project()
    found = {(p["thesis_id"], p["field"]): p for p in propose_inferences(docs)}
    assert set(found) == {("T0008", "faculty"), ("T0011", "program")}
    assert found[("T0008", "faculty")]["value"] == "Facultad de Psicología"
    assert "3 de 3 tesis" in found[("T0008", "faculty")]["evidence"]
    assert found[("T0011", "program")]["value"] == PSI
    # Proposing never touches the theses.
    assert "faculty" not in docs[3]["metadata"]


def test_peers_must_agree_and_never_count_inferred_values():
    docs = _project()
    docs[0]["metadata"]["faculty"] = "Facultad de Filosofía y Humanidades"
    assert not [p for p in propose_inferences(docs) if p["field"] == "faculty"]

    docs = _project()
    docs[0]["metadata_inference"] = {"faculty": {"value": "Facultad de Psicología", "rule": "faculty_from_peers"}}
    assert not [p for p in propose_inferences(docs) if p["field"] == "faculty"]


def test_repository_university_then_chains_into_faculty_and_program(tmp_path):
    pdf = tmp_path / "t.pdf"
    pdf.write_bytes(b"x")
    docs = _project() + [{"id": "d27", "thesis_id": "T0027", "path": str(pdf), "metadata": {"degree_level": "doctorado", "program": PSI}}]
    texts = {str(pdf): "licencia ... https://rdu.unc.edu.ar"}
    found = {(p["thesis_id"], p["field"]): p for p in propose_inferences(docs, read_text=lambda path: texts.get(path, ""))}
    assert found[("T0027", "university")]["value"] == UNC
    assert found[("T0027", "faculty")]["value"] == "Facultad de Psicología"


def test_apply_confirm_undo_and_origin():
    docs = _project()
    by_id = {d["id"]: d for d in docs}
    proposals = propose_inferences(docs, rules=["program_from_level_faculty"])
    by_id["d11"]["metadata_detection"] = {"suggestions": {"university": UNC}}
    assert apply_inferences(by_id, proposals) == 1
    t11 = by_id["d11"]
    assert t11["metadata"]["program"] == PSI and inference_of(t11, "program")
    assert public_inference(t11)["program"]["rule_title"] == "Programa desde nivel y facultad"
    assert field_origin(t11, "program") == "inferido" and field_origin(t11, "university") == "PDF"

    # A person edits the cell: it is no longer an inference.
    t11["metadata"]["program"] = "Doctorado en Psicología Social"
    assert inference_of(t11, "program") is None and field_origin(t11, "program") == "manual"
    t11["metadata"]["program"] = PSI

    assert confirm_inference(t11, "program") and not inference_of(t11, "program")
    assert t11["metadata"]["program"] == PSI and field_origin(t11, "program") == "manual"

    apply_inferences(by_id, propose_inferences(docs, rules=["faculty_from_peers"]))
    assert undo_inference(by_id["d8"], "faculty") and "faculty" not in by_id["d8"]["metadata"]
    # Never overwrites a value that is already there.
    assert apply_inferences(by_id, [{"document_id": "d1", "field": "faculty", "value": "X", "rule": "faculty_from_peers", "evidence": ""}]) == 0
