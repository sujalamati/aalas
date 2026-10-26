from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Job, User
from app.services.llm import embed
from app.services.jobs_provider import fetch_jobs, normalize_job

logger = logging.getLogger(__name__)

# pg_textsearch's <@> operator returns NEGATIVE BM25 scores; more negative is better.
BM25_INDEX_NAME = "jobs_search_text_bm25_idx"
RRF_K = 60
DEFAULT_CANDIDATE_MULTIPLIER = 10
MIN_CANDIDATES = 100
JOB_FIELDS = [
    "id", "position", "company", "location", "posted_date", "salary_text",
    "salary_min", "salary_max", "job_url", "company_logo", "ago_time", "description",
]


def provider_options(user: User, limit: int) -> list[dict]:
    # Provider filter values may differ by provider/version; keep this mapping in one place.
    return [{
        "keyword": role.strip(),
        "location": user.locations.split(",")[0].strip(),
        "dateSincePosted": "past Week",
        "jobType": user.job_type,
        "remoteFilter": "",
        "salary": str(user.salary_min) if user.salary_min is not None else "",
        "experienceLevel": user.experience_level,
        "limit": str(limit),
        "page": "0",
        "has_verification": False,
        "under_10_applicants": False,
    } for role in user.target_roles.split(",") if role.strip()]


async def fetch_and_store(db: Session, user: User, limit: int = 25) -> int:
    options_list = provider_options(user, limit)
    count = 0
    for options in options_list:
        raw_jobs = await fetch_jobs(options)
        for raw in raw_jobs:
            item = normalize_job(raw)
            if not item["job_url"]:
                continue

            existing = db.query(Job).filter_by(user_id=user.id, job_url=item["job_url"]).first()
            # If a detail-page request fails, preserve the previously fetched full description.
            if existing and not item["description"] and existing.description:
                item["description"] = existing.description

            searchable = "\n".join([
                item["position"], item["company"], item["location"], item["description"]
            ])
            try:
                vector = await embed(searchable)
            except Exception:
                logger.exception("Could not embed job url=%s", item["job_url"])
                vector = None

            if existing:
                for key, value in item.items():
                    setattr(existing, key, value)
                # Don't wipe an older valid vector if the embedding service is temporarily down.
                if vector is not None:
                    existing.embedding = vector
                existing.is_active = True
            else:
                db.add(Job(user_id=user.id, **item, embedding=vector))
            count += 1
        db.commit()
    return count


def _resume_as_plain_text(latex: str) -> str:
    """Use Pandoc if installed; fall back to raw LaTeX so search still works during setup."""
    if not latex:
        return ""
    try:
        import pypandoc
        return pypandoc.convert_text(latex, "plain", format="latex")
    except Exception:
        logger.warning("Could not convert LaTeX resume to plain text; using source as fallback.", exc_info=True)
        return latex


def _make_query_text(user: User) -> tuple[str, str]:
    """Build bounded keyword and semantic queries from the user's actual profile."""
    parsed_resume = _resume_as_plain_text(user.resume_latex)
    # Keep the lexical query relatively concise: very long resume text can dilute useful terms.
    keyword_query = "\n".join([
        user.target_roles or "",
        f"Preferred locations: {user.locations or ''}",
        f"Job type: {user.job_type or ''}",
        f"Experience: {user.experience_level or ''}",
        f"Resume skills and experience: {parsed_resume}",
        f"Additional context: {(user.additional_context or '')}",
    ]).strip()

    semantic_query = "\n".join([
        user.target_roles or "",
        f"Preferred locations: {user.locations or ''}",
        f"Job type: {user.job_type or ''}",
        f"Experience: {user.experience_level or ''}",
        f"Resume: {parsed_resume}",
        f"Additional context: {(user.additional_context or '')}",
    ]).strip()
    return keyword_query, semantic_query


def _bm25_candidates_sql() -> str:
    """Keyword-only query used when embeddings are not available."""
    return f"""
        WITH user_jobs AS MATERIALIZED (
            SELECT j.id,
                   (COALESCE(j.position, '') || ' ' || COALESCE(j.company, '') || ' ' ||
                    COALESCE(j.location, '') || ' ' || COALESCE(j.description, '')) AS search_text
            FROM jobs AS j
            WHERE j.user_id = :uid AND j.is_active = TRUE
        ), keyword_scored AS MATERIALIZED (
            SELECT uj.id,
                   uj.search_text <@> to_bm25query(:q, '{BM25_INDEX_NAME}') AS bm25_score
            FROM user_jobs AS uj
        ), keyword AS (
            SELECT id,
                   ROW_NUMBER() OVER (ORDER BY bm25_score ASC, id ASC) AS keyword_rank
            FROM (
                SELECT id, bm25_score
                FROM keyword_scored
                WHERE bm25_score < 0
                ORDER BY bm25_score ASC, id ASC
                LIMIT :candidate_limit
            ) AS top_keyword
        )
        SELECT id,
               1.0 / (:rrf_k + keyword_rank) AS rrf_score
        FROM keyword
        ORDER BY rrf_score DESC, id ASC
        LIMIT :lim
    """


def _hybrid_rrf_sql() -> str:
    """RRF fusion of top BM25 and pgvector cosine-similarity candidate lists."""
    return f"""
        WITH user_jobs AS MATERIALIZED (
            -- Filter by user first so a global BM25 top-k cannot crowd out this user's rows.
            SELECT j.id,
                   (COALESCE(j.position, '') || ' ' || COALESCE(j.company, '') || ' ' ||
                    COALESCE(j.location, '') || ' ' || COALESCE(j.description, '')) AS search_text,
                   j.embedding
            FROM jobs AS j
            WHERE j.user_id = :uid AND j.is_active = TRUE
        ), keyword_scored AS MATERIALIZED (
            SELECT uj.id,
                   uj.search_text <@> to_bm25query(:q, '{BM25_INDEX_NAME}') AS bm25_score
            FROM user_jobs AS uj
        ), keyword AS (
            SELECT id,
                   ROW_NUMBER() OVER (ORDER BY bm25_score ASC, id ASC) AS keyword_rank
            FROM (
                SELECT id, bm25_score
                FROM keyword_scored
                WHERE bm25_score < 0
                ORDER BY bm25_score ASC, id ASC
                LIMIT :candidate_limit
            ) AS top_keyword
        ), semantic AS (
            SELECT id,
                   ROW_NUMBER() OVER (ORDER BY distance ASC, id ASC) AS semantic_rank
            FROM (
                SELECT uj.id,
                       uj.embedding <=> CAST(:vec AS vector) AS distance
                FROM user_jobs AS uj
                WHERE uj.embedding IS NOT NULL
                ORDER BY distance ASC, uj.id ASC
                LIMIT :candidate_limit
            ) AS top_semantic
        ), fused AS (
            SELECT COALESCE(k.id, s.id) AS id,
                   COALESCE(1.0 / (:rrf_k + k.keyword_rank), 0.0) +
                   COALESCE(1.0 / (:rrf_k + s.semantic_rank), 0.0) AS rrf_score
            FROM keyword AS k
            FULL OUTER JOIN semantic AS s ON s.id = k.id
        )
        SELECT id, rrf_score
        FROM fused
        ORDER BY rrf_score DESC, id ASC
        LIMIT :lim
    """


async def rank_jobs(db: Session, user: User, limit: int = 25) -> list[dict[str, Any]]:
    """Rank saved jobs with BM25 keyword retrieval + vector retrieval, fused by RRF.

    The BM25 index is created during application startup in app.db.init_db().
    RRF avoids adding raw BM25 scores and cosine similarities, which use different scales.
    Salary is not a hard filter: missing salary remains "Not specified" rather than zero.
    """
    keyword_query, semantic_query = _make_query_text(user)
    try:
        query_vector = await embed(semantic_query)
    except Exception:
        logger.exception("Embedding query failed; falling back to BM25-only ranking for user_id=%s", user.id)
        query_vector = None

    candidate_limit = max(MIN_CANDIDATES, limit * DEFAULT_CANDIDATE_MULTIPLIER)
    params: dict[str, Any] = {
        "uid": user.id,
        "q": keyword_query,
        "candidate_limit": candidate_limit,
        "rrf_k": RRF_K,
        "lim": limit,
    }

    if query_vector:
        params["vec"] = "[" + ",".join(map(str, query_vector)) + "]"
        sql = _hybrid_rrf_sql()
    else:
        sql = _bm25_candidates_sql()

    rows = db.execute(text(sql), params).mappings().all()
    if not rows:
        # If BM25 has no lexical matches and embeddings are unavailable, return recent jobs
        # rather than presenting an empty page. Their scores are explicitly zero.
        if query_vector is None:
            jobs = (
                db.query(Job)
                .filter_by(user_id=user.id, is_active=True)
                .order_by(Job.fetched_at.desc())
                .limit(limit)
                .all()
            )
            return [{**{key: getattr(job, key) for key in JOB_FIELDS}, "relevance_score": 0.0} for job in jobs]
        return []

    scores = {row["id"]: round(float(row["rrf_score"]), 8) for row in rows}
    ids = list(scores.keys())  # Preserve ranking order from the SQL result.
    jobs = db.query(Job).filter(Job.id.in_(ids)).all() if ids else []
    by_id = {job.id: job for job in jobs}
    return [
        {**{key: getattr(by_id[job_id], key) for key in JOB_FIELDS}, "relevance_score": scores[job_id]}
        for job_id in ids
        if job_id in by_id
    ]
