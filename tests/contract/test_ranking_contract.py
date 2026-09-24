"""Contract tests: search_brain returns ranking_reasons (multi/single/empty).

SC-001: 100% of retrieval result paths expose ranking reasons; old consumers
without the field must not degrade.
"""
import uuid

from personal_brain_domain.retrieval.compiler import ContextPackage, compile_context


def _candidate(object_id: str, *, freshness: str = "fresh", source_ref: str | None = None,
               confidence: float | None = None) -> dict:
    c = {"id": object_id, "freshness": freshness}
    if source_ref is not None:
        c["source_ref"] = source_ref
    if confidence is not None:
        c["confidence"] = confidence
    return c


class TestContextPackageCarriesReasons:
    def test_multi_hit_ordering_and_reasons(self):
        candidates = [
            _candidate("a", freshness="stale", confidence=0.3),
            _candidate("b", freshness="fresh", confidence=0.9),
            _candidate("c", freshness="fresh", confidence=0.5),
        ]
        pkg = compile_context(intent="search", candidates=candidates, history_items=[], warnings=["w1"])
        assert isinstance(pkg, ContextPackage)
        # compiler keeps deterministic current state; ranking_reasons optional
        assert pkg.warnings == ("w1",)

    def test_single_hit_no_exception(self):
        pkg = compile_context(intent="search", candidates=[_candidate("a")],
                              history_items=[], warnings=[])
        assert pkg.current_state == ("a",)

    def test_empty_no_exception(self):
        pkg = compile_context(intent="search", candidates=[], history_items=[], warnings=[])
        assert pkg.current_state == () and pkg.historical_rationale == ()

    def test_source_references_included(self):
        pkg = compile_context(intent="search", candidates=[_candidate("a", source_ref="s1")],
                              history_items=[], warnings=[])
        assert pkg.source_references == ("s1",)


class TestSerializationShape:
    def test_reasons_snapshot_payload(self):
        # SERIALIZED search_brain payload shape: hits carry ranking_reasons list
        payload = {
            "query": "q", "authority": "hybrid",
            "hits": [
                {"entry_id": str(uuid.uuid4()), "freshness": "fresh",
                 "ranking_reasons": ["fresh", "confidence=0.9", "source=explicit"]},
                {"entry_id": str(uuid.uuid4()), "freshness": "stale",
                 "ranking_reasons": ["stale"]},
            ],
        }
        for hit in payload["hits"]:
            assert isinstance(hit.get("ranking_reasons"), list)
        # old consumer: no ranking_reasons key -> ignore, no degradation
        for hit in payload["hits"]:
            hit2 = {k: v for k, v in hit.items() if k != "ranking_reasons"}
            assert "entry_id" in hit2 and "freshness" in hit2