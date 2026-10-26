# Aalas Frontend

A React + Vite frontend for the Aalas FastAPI job-hunting backend. It provides profile registration, LaTeX resume upload, job searching and ranked listings, job details, tailored resume generation/PDF download, generated LaTeX download, cover-letter generation, and cover-letter download.

## Requirements

- Node.js 20+ recommended
- The Aalas FastAPI backend running on `http://127.0.0.1:8000`
- The backend database, Ollama model, and LaTeX compiler configured as described in the backend README

## Start the frontend

```bash
cp .env.example .env
npm install
npm run dev
```

Open http://localhost:3000. The Vite dev server uses port 3000 because the current backend CORS configuration allows `http://localhost:3000` and `http://127.0.0.1:3000`.

Set `VITE_API_BASE_URL` in `.env` if the backend is not at `http://127.0.0.1:8000`. Vite variables are read at build time; restart Vite after changing `.env`.

## Build for production

```bash
npm run build
npm run preview
```

The production bundle is created in `dist/`. Configure your production server or reverse proxy to route API requests to the FastAPI backend, and update the backend CORS origins for the frontend deployment domain.

## User flow

1. Register a profile with name, email, job-role preferences, locations, job type, experience level, salary preference, and optional additional context.
2. Optionally upload a `.tex` resume during registration, or upload/replace it on **My profile**. The current backend accepts UTF-8 `.tex` files up to 1 MB.
3. Click **Find new jobs** to call `POST /api/users/{user_id}/search`, then browse ranked jobs and filter results locally.
4. Select a job to view details and open the original listing.
5. Choose **Tailor resume** or **Cover letter**. Tailored resume generation displays a PDF preview when the returned PDF can be fetched, and offers PDF and `.tex` downloads. Cover letters display a preview and offer a `.txt` download.
6. The browser remembers the active profile ID in localStorage. It does not store the resume source in the browser. Use the profile ID to restore a session if needed.

## API endpoints used

- `POST /api/users`
- `GET /api/users/{user_id}`
- `PATCH /api/users/{user_id}`
- `POST /api/users/{user_id}/resume` (multipart form field `file`)
- `POST /api/users/{user_id}/search`
- `GET /api/users/{user_id}/jobs`
- `POST /api/documents/tailor-resume`
- `POST /api/documents/cover-letter`
- `GET /api/documents/{filename}/pdf`
- `GET /api/documents/{filename}/download`

The frontend also links to FastAPI Swagger at `/docs`.

## Notes and current backend limitations

- The current backend has profile creation and profile read/update routes but no authentication or password-based login. Registration in this UI creates a backend profile; restoring by ID is not authentication. Do not deploy with real user resumes without adding authentication, authorization, and appropriate privacy protections.
- The frontend expects the latest backend response shape where `UserOut` contains `resume_uploaded` and job documents use `pdf_url` and `download_url` values under `/api`.
- The UI does not claim that a job is a percentage match; the score displayed on job cards is the backend's raw RRF score.
- Cover letters download as plain text because the current backend creates `.txt` files. Change the backend if you want PDF cover letters.
- Salary is displayed as unspecified when the listing omits it; no zero-salary assumption is made.
