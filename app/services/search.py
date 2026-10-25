from sqlalchemy import text
from sqlalchemy.orm import Session
from app.models import Job, User
from app.services.llm import embed
from app.services.jobs_provider import fetch_jobs, normalize_job
import pypandoc

def provider_options(user: User, limit: int) -> list[dict]:
    # Provider's documented option values can vary. Verify them against your installed package.
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
            # Upsert per user+URL.
            existing = db.query(Job).filter_by(user_id=user.id, job_url=item["job_url"]).first()
            searchable = "\n".join([item["position"], item["company"], item["location"], item["description"]])
            try:
                vector = await embed(searchable)
            except Exception:
                # Don't drop a job just because embeddings are temporarily unavailable.
                vector = None
            if existing:
                for key, value in item.items():
                    setattr(existing, key, value)
                existing.embedding = vector
                existing.is_active = True
            else:
                db.add(Job(user_id=user.id, **item, embedding=vector))
            count += 1
        db.commit()
    return count

async def rank_jobs(db: Session, user: User, limit: int = 25) -> list[dict]:
    parsed_resume = pypandoc.convert_text(user.resume_latex, 'plain', format='latex')
    query_text = f"{user.target_roles}\nPreferred locations: {user.locations}\nJob type: {user.job_type}\nExperience: {user.experience_level}\nResume: {parsed_resume}\nAdditional context: {user.additional_context[:1500]}"
    try:
        query_vector = await embed(query_text)
    except Exception:
        query_vector = None

    # Keyword relevance + cosine similarity. pgvector cosine distance is lower for closer vectors.
    # Salary is intentionally not a hard filter because postings frequently omit it.
    if query_vector:
        rows = db.execute(text("""
            SELECT j.id,
                   ts_rank_cd(to_tsvector('english',
                     coalesce(j.position,'') || ' ' || coalesce(j.company,'') || ' ' ||
                     coalesce(j.location,'') || ' ' || coalesce(j.description,'')),
                     plainto_tsquery('english', :q)) AS keyword_score,
                   CASE WHEN j.embedding IS NULL THEN 0
                     ELSE 1 - (j.embedding <=> CAST(:vec AS vector)) END AS vector_score
            FROM jobs j
            WHERE j.user_id = :uid AND j.is_active = true
            ORDER BY (0.45 * ts_rank_cd(to_tsvector('english',
                       coalesce(j.position,'') || ' ' || coalesce(j.company,'') || ' ' ||
                       coalesce(j.location,'') || ' ' || coalesce(j.description,'')),
                       plainto_tsquery('english', :q))
                    + 0.55 * CASE WHEN j.embedding IS NULL THEN 0
                       ELSE 1 - (j.embedding <=> CAST(:vec AS vector)) END) DESC
            LIMIT :lim
        """), {"q": query_text, "vec": "[" + ",".join(map(str, query_vector)) + "]", "uid": user.id, "lim": limit}).mappings().all()
        scores = {r["id"]: round(float(0.45 * (r["keyword_score"] or 0) + 0.55 * (r["vector_score"] or 0)), 5) for r in rows}
        ids = [r["id"] for r in rows]
        jobs = db.query(Job).filter(Job.id.in_(ids)).all() if ids else []
        by_id = {j.id: j for j in jobs}
        return [{**{k: getattr(by_id[i], k) for k in ["id","position","company","location","posted_date","salary_text","salary_min","salary_max","job_url","company_logo","ago_time","description"]}, "relevance_score": scores[i]} for i in ids if i in by_id]

    # Fallback keyword ranking if embedding service is down.
    jobs = db.query(Job).filter_by(user_id=user.id, is_active=True).order_by(Job.fetched_at.desc()).limit(limit).all()
    terms = set(query_text.lower().split())
    return [{**{k: getattr(j, k) for k in ["id","position","company","location","posted_date","salary_text","salary_min","salary_max","job_url","company_logo","ago_time","description"]},
             "relevance_score": round(sum(t in (j.position+" "+j.description+" "+j.company).lower() for t in terms) / max(len(terms),1), 5)} for j in jobs]
