# Aalas — Job Hunter Backend (FastAPI)

Backend scaffold for a job discovery tool with PostgreSQL/pgvector hybrid ranking and Ollama-powered resume/cover-letter generation.

## Important integration notes

- `linkedin-jobs-api` is an unofficial third-party scraper-style package, **not an official LinkedIn API**. The code keeps it behind `app/services/jobs_provider.py`. Its example in your prompt is JavaScript (`require(...)`), not a Python API; the Python package may not expose the same interface. Verify its actual Python interface before expecting live fetches. If it only exists as a Node package, run it as a separate Node microservice or replace the adapter with a permitted job-data provider.
- The example response you supplied does not contain a full job description. Tailoring is much better when the provider supplies the description. This scaffold stores an empty description when none is available and tells the model not to invent facts.
- Check LinkedIn and provider terms, rate limits, privacy obligations, and any applicable API terms before deploying scraping-based ingestion.
- `gemma4:e4b` is used for both document-generation calls. Embeddings use a separate Ollama model (`nomic-embed-text`) because a chat model is not automatically an embedding model. Its vector size must match `EMBEDDING_DIM` in `app/models.py`; if it differs, update that constant and recreate the `jobs` table.
- For local testing, generated PDFs are returned as URLs. LaTeX compilation is not a security boundary; run compilation in an isolated container with resource limits before accepting arbitrary user-provided LaTeX in production.

## Start PostgreSQL with persistent storage

The compose file mounts `pgdata` as a named volume, so data survives container restarts/recreation unless you explicitly remove the volume.

```bash
docker compose up -d db
```

Equivalent command based on your request:

```bash
docker run -d --name hybrid-search \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=password \
  -v hybrid_pgdata:/home/postgres/pgdata/data \
  timescale/timescaledb-ha:pg17 \
  -c shared_preload_libraries=timescaledb,pg_textsearch
```

If you already created the database without a volume, create a new container with the volume configured. `docker compose down -v` deletes persisted DB data; avoid it if you want to keep data.

## Run locally (recommended for first Swagger tests)

Requires Python 3.12, PostgreSQL with `vector` and `pg_textsearch` extensions, Ollama, and a LaTeX engine (`tectonic` or `pdflatex`).

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
ollama pull gemma4:e4b
ollama pull nomic-embed-text
uvicorn app.main:app --reload
```

Open Swagger at http://127.0.0.1:8000/docs. For initial API testing, set `SCHEDULER_ENABLED=false`; trigger search manually.

## Run the API in Docker

```bash
docker compose build api
docker compose up -d
```

The API container expects Ollama on the host at port 11434. On Linux, `host.docker.internal` is mapped using `host-gateway`.

## API flow

1. `POST /api/users` — create the profile as JSON. Do **not** include `resume_latex` in the JSON body.
2. `POST /api/users/{user_id}/resume` — upload the resume as a `.tex` file using `multipart/form-data`. In Swagger, select the file in the `file` field. This stores its UTF-8 LaTeX source in the user's profile and replaces any previously uploaded resume.
3. `PATCH /api/users/{user_id}` — update profile preferences or additional context. To replace the resume, use the upload endpoint again.
4. `POST /api/users/{user_id}/search` — fetch and index jobs, then rank by hybrid keyword/vector relevance. Body: `{"refresh": true, "limit": 25}`.
5. `GET /api/users/{user_id}/jobs` — return cached jobs ranked against the latest profile.
6. `GET /api/jobs/{job_id}` — inspect a job.
7. `POST /api/documents/tailor-resume` — body `{"user_id": 1, "job_id": 1}`. Returns LaTeX and PDF URL.
8. `GET /api/documents/{filename}/pdf` — download the PDF.
9. `POST /api/documents/cover-letter` — body `{"user_id": 1, "job_id": 1}`. Returns letter text and download URL.
10. `GET /api/documents/{filename}/download` — download cover-letter text.

### Uploading a resume in Swagger

Create the profile first, for example:

```json
{
  "name": "Test User",
  "email": "test@example.com",
  "target_roles": "Software Engineer, Backend Engineer",
  "locations": "Bengaluru, Hyderabad",
  "job_type": "full time",
  "salary_min": 1200000,
  "salary_currency": "INR",
  "experience_level": "entry level",
  "additional_context": "Project: Built a REST API using FastAPI and PostgreSQL."
}
```

Then call `POST /api/users/{user_id}/resume`, enter the user ID in the path, and choose the `.tex` file in the `file` input. The endpoint accepts files up to 1 MB, requires UTF-8 text, and rejects non-`.tex` filenames. Profile responses report `resume_uploaded: true/false` instead of echoing the entire LaTeX source.

## Hybrid ranking

The query combines PostgreSQL full-text keyword rank (45%) and pgvector cosine similarity (55%). Tune weights after evaluating results. Missing salary is not treated as zero and does not remove a job from search. The response exposes `"Not specified"` for salary when the provider omits it.

## Design choices and next steps

- Per-user unique `(user_id, job_url)` prevents duplicate listings across refreshes.
- Search refresh currently fetches every target role serially to avoid hammering a provider. Add provider-aware rate limiting/backoff and pagination after confirming provider support.
- Scheduler is configured for midnight and noon in `Asia/Kolkata`, but disabled by default in `.env.example` and Docker Compose so tests don't trigger provider calls unexpectedly. Set `SCHEDULER_ENABLED=true` to enable.
- This scaffold does not yet implement authentication, user data deletion/export, provider retry queues, or a production migration framework. Add authentication and encrypt/restrict resume data before public deployment.
- In a multi-user production system, run scheduled refreshes in a dedicated worker rather than starting a scheduler in every API replica.