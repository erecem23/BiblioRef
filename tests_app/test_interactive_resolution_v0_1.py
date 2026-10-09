from biblioref.resolver.models import Candidate
import biblioref.resolver.interactive as interactive


class _Backend:
    def __init__(self, source):
        self.name = source
        self.source = source

    def search(self, query):
        return (
            Candidate(
                source=self.source,
                source_id=f"{self.source}-1",
                title="A shared title",
                authors=("Smith, J.",),
                year="2020",
                doi="10.1000/shared",
                retrieval_method="test",
            ),
        )


def test_interactive_runner_collects_candidates_consensus_and_decision(monkeypatch):
    monkeypatch.setattr(interactive, "CrossrefBackend", lambda **kwargs: _Backend("crossref"))
    monkeypatch.setattr(interactive, "OpenAlexBackend", lambda **kwargs: _Backend("openalex"))
    runner = interactive.InteractiveResolutionRunner()
    result = runner.run(
        raw_reference="Smith, J. (2020). A shared title.",
        parsed={"author": "Smith, J.", "year": "2020", "title": "A shared title"},
        layers=["crossref", "openalex", "consensus", "decision"],
    )
    payload = result.as_dict()
    assert payload["batch"]["candidate_count"] == 2
    assert payload["consensus"]["status"] == "external_consensus"
    assert payload["decision"]["status"] == "VERIFIED_EXTERNAL_CONSENSUS"
    assert payload["semantic"] is None
    assert payload["rag"] is None
    assert payload["adjudication"] is None
    assert payload["candidates"][0]["identity_key"] == "doi:10.1000/shared"
    assert payload["layer_errors"] == {}
    assert "local_model_runtime_is_disabled" in payload["notes"]


def test_decision_expands_consensus_prerequisite():
    runner = interactive.InteractiveResolutionRunner()
    assert runner._expand_layers(("decision",)) == ("consensus", "decision")


def test_local_layers_are_rejected_by_interactive_runtime():
    runner = interactive.InteractiveResolutionRunner()
    for layer in ("semantic", "rag", "llm"):
        try:
            runner.run(raw_reference="x", parsed={}, layers=[layer])
        except ValueError as exc:
            assert "unknown interactive layer" in str(exc)
        else:
            raise AssertionError(f"{layer} must be disabled in current runtime")


def test_unknown_layer_is_rejected():
    runner = interactive.InteractiveResolutionRunner()
    try:
        runner.run(raw_reference="x", parsed={}, layers=["made_up"])
    except ValueError as exc:
        assert "unknown interactive layer" in str(exc)
    else:
        raise AssertionError("unknown layer should fail")
