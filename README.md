# Aalas — Job Hunter Backend (FastAPI)

Backend scaffold for a job discovery tool with PostgreSQL/pgvector hybrid ranking and Ollama-powered resume/cover-letter generation.

## Important integration notes

- `app/services/jobs_provider.py` is a native Python port of the supplied JavaScript implementation. It uses `httpx` and BeautifulSoup; the unrelated `linkedin-jobs-api` Python package has been removed. It requests LinkedIn guest-job listing HTML, so the endpoint and HTML selectors can change and requests may be rate-limited. This is not an official LinkedIn API; verify applicable terms before deployment and keep request rates conservative.
- Search results do not contain the full description, so the provider makes a second request to each job URL and extracts `description` from the page’s schema.org `JobPosting` JSON-LD. It falls back to common visible-description selectors. A failed detail-page request does not discard the listing; its description remains empty.
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

## LinkedIn guest-job provider details

The provider is implemented in pure Python in `app/services/jobs_provider.py`:

- `httpx` requests the guest-job listing endpoint.
- `beautifulsoup4` parses the same selectors used by the supplied Cheerio implementation and extracts full descriptions from the individual job details pages (JSON-LD first, visible HTML selectors second).
- The adapter supports the original date, experience, job-type, remote, salary, sort, and page filters.
- Results are fetched in batches of 25, with a one-hour in-memory cache, bounded retries, exponential backoff, and a pause between successful batches.
- Job detail pages are fetched with bounded concurrency and an independent one-hour description cache to reduce duplicate requests. The supplied JavaScript dependency `random-useragent` is not needed. The Python version uses a stable User-Agent and does not rotate identities to get around rate limiting.

The listing endpoint contains only card fields. The provider therefore makes a second request to each `jobUrl` and extracts the full description from the page. LinkedIn can change guest endpoints, JSON-LD, or HTML selectors without notice; blocked/failed detail pages leave the description empty rather than breaking the entire search. Avoid high-frequency polling and comply with applicable terms. For durable/production use, consider a licensed job-data API.

## Hybrid ranking

Job relevance uses BM25 keyword retrieval and pgvector cosine-similarity retrieval, fused using Reciprocal Rank Fusion (RRF). Missing salary is not treated as zero and does not remove a job from search. The response exposes `"Not specified"` for salary when the provider omits it. See the BM25/RRF details below.

## Design choices and next steps

- Per-user unique `(user_id, job_url)` prevents duplicate listings across refreshes.
- Search refresh currently fetches every target role serially. The provider adapter uses 25-job batches, bounded retries with exponential backoff, a two-to-three-second pause between successful batches, and a one-hour in-memory cache. LinkedIn may rate-limit or alter this guest endpoint, so test conservatively.
- Scheduler is configured for midnight and noon in `Asia/Kolkata`, but disabled by default in `.env.example` and Docker Compose so tests don't trigger provider calls unexpectedly. Set `SCHEDULER_ENABLED=true` to enable.
- This scaffold does not yet implement authentication, user data deletion/export, provider retry queues, or a production migration framework. Add authentication and encrypt/restrict resume data before public deployment.
- In a multi-user production system, run scheduled refreshes in a dedicated worker rather than starting a scheduler in every API replica.


## Hybrid ranking: BM25 + vector search + Reciprocal Rank Fusion

The backend creates `jobs_search_text_bm25_idx` during startup. It indexes a concatenation of job title, company, location, and full description with `pg_textsearch` (`text_config='english'`). If the database already exists, restart the API once so `init_db()` creates the index. Confirm with:

```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'jobs' AND indexname = 'jobs_search_text_bm25_idx';
```

Search now fetches separate keyword and semantic candidate lists (up to `max(100, limit * 10)` each) and fuses their ranks using Reciprocal Rank Fusion:

`rrf_score = 1 / (60 + keyword_rank) + 1 / (60 + semantic_rank)`

A job appearing in only one candidate list receives the contribution from that list. `pg_textsearch` returns negative BM25 scores, so lower/more-negative scores are better and are sorted ascending before assigning ranks. RRF combines rank positions rather than adding uncalibrated BM25 and cosine-similarity scores. If embedding generation is unavailable, the endpoint falls back to BM25-only ranking. If no lexical matches exist and embeddings are unavailable, recent jobs are returned with score `0`.

The keyword query includes a bounded portion of the resume converted from LaTeX to plain text, role/location preferences, and additional context. `pypandoc-binary` is included so `pypandoc.convert_text(..., format='latex')` is available without a separate system Pandoc install. The BM25 expression index computes corpus statistics over the `jobs` table. The SQL materializes a user's active job subset before scoring to prevent other users' duplicate saved rows from crowding out that user's candidate list; for large production datasets, consider normalizing jobs into one global table with a separate user-job association table.
