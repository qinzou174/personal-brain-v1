"""Unit tests: ranking reasons collect freshness/confidence/source signals.

ER-03/FR-057: ranking reasons must reflect input signals; single/empty results
must not raise.
"""
from personal_brain_domain.retrieval.ranking import rank_hits, rrf_fuse


def _hit(object_id: str, *, freshness: str = "fresh", confidence: float | None = None,
         source_trust: str | None = None, information_class: str | None = None) -> dict:
    hit = {"id": object_id, "freshness": freshness}
    if confidence is not None:
        hit["confidence"] = confidence
    if source_trust is not None:
        hit["source_trust"] = source_trust
    if information_class is not None:
        hit["information_class"] = information_class
    return hit


class TestRankReasons:
    def test_mixed_candidates_carry_signals(self):
        candidates = [
            _hit("a", freshness="fresh", confidence=0.9, source_trust="high", information_class="explicit"),
            _hit("b", freshness="stale", confidence=0.4, source_trust="low", information_class="inference"),
            _hit("c", freshness="fresh"),
        ]
        ranked = rank_hits(candidates=candidates, keyword_rank=["a", "b", "c"], semantic_rank=["a"])
        reasons_by_id = {r.object_id: r.reasons for r in ranked}
        assert any("fresh" in r for r in reasons_by_id["a"])
        assert any(s.startswith("confidence=") for s in reasons_by_id["a"])
        assert any(s == "source=explicit" for s in reasons_by_id["a"])
        assert any("stale" in r for r in reasons_by_id["b"])
        assert any(s.startswith("confidence=") for s in reasons_by_id["b"])

    def test_no_signal_keeps_default(self):
        ranked = rank_hits(candidates=[_hit("a"), _hit("b")],
                           keyword_rank=["a", "b"], semantic_rank=[])
        for r in ranked:
            assert r.reasons, "reasons must not be empty"

    def test_single_hit_without_signals_uses_single(self):
        ranked = rank_hits(candidates=[{"id": "a"}], keyword_rank=[], semantic_rank=[])
        assert ranked[0].reasons == ("single",)

    def test_single_hit_with_signals_carries_them(self):
        ranked = rank_hits(candidates=[_hit("a", freshness="fresh", confidence=0.9)],
                           keyword_rank=[], semantic_rank=[])
        assert any(s.startswith("freshness=") for s in ranked[0].reasons)
        assert any(s.startswith("confidence=") for s in ranked[0].reasons)

    def test_all_hard_filtered_returns_empty(self):
        deleted = {"id": "x", "lifecycle_state": "deleted"}
        secret = {"id": "y", "sensitivity": "secret"}
        ranked = rank_hits(candidates=[deleted, secret], keyword_rank=[], semantic_rank=[])
        assert ranked == []


class TestRrfFuse:
    def test_fuse_sums_reciprocal_ranks(self):
        fused = rrf_fuse(keyword_rank=["a", "b"], semantic_rank=["b", "a"])
        assert fused["a"] > 0.0 and fused["b"] > 0.0