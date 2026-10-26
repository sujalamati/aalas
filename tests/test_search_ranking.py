from types import SimpleNamespace

from app.services.search import (
    BM25_INDEX_NAME,
    RRF_K,
    _bm25_candidates_sql,
    _hybrid_rrf_sql,
    _make_query_text,
)


def test_query_text_includes_profile_resume_and_additional_context(monkeypatch):
    monkeypatch.setattr("app.services.search._resume_as_plain_text", lambda value: "Python PostgreSQL vector search")
    user = SimpleNamespace(
        target_roles="Backend Engineer",
        locations="Bengaluru",
        job_type="full time",
        experience_level="entry level",
        resume_latex="ignored source",
        additional_context="Worked on a retrieval project",
    )
    keyword_query, semantic_query = _make_query_text(user)
    assert "Backend Engineer" in keyword_query
    assert "Python PostgreSQL vector search" in keyword_query
    assert "retrieval project" in semantic_query


def test_hybrid_query_uses_bm25_vector_and_rrf():
    sql = _hybrid_rrf_sql()
    assert BM25_INDEX_NAME in sql
    assert "to_bm25query" in sql
    assert "<=> CAST(:vec AS vector)" in sql
    assert "FULL OUTER JOIN semantic" in sql
    assert ":rrf_k" in sql


def test_bm25_fallback_when_embedding_service_is_unavailable():
    sql = _bm25_candidates_sql()
    assert "to_bm25query" in sql
    assert "bm25_score < 0" in sql
    assert RRF_K == 60
