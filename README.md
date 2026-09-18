# Prompt Architect

Prompt Architect turns an unstructured idea into a clear, target-specific
prompt. The current implementation includes the anonymous core flow,
Supabase authentication and persistence, and functional UX hardening.

## Stack and architecture

- Frontend: React, Vite, Tailwind CSS, React Router, and React Query
- Backend: Django, Django REST Framework, and CORS headers
- Database and auth: Supabase Postgres and Supabase Auth
- LLM: Gemini through the server-side `google-genai` Python SDK

The frontend owns the wizard, authentication screens, session history,
status-driven resume, validation, and retryable server actions. Django REST
Framework exposes the health and session APIs. The `sessions` app owns the
prompt-session data model and workflow endpoints; the isolated `llm` app owns
Gemini templates, schemas, retries, and error translation. Supabase provides
Postgres and Auth. Django verifies Supabase access tokens with JWKS and stores
a local user mirror. Application schema changes are managed by Django
migrations.

## Local setup

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `DATABASE_URL` in `backend/.env` to your Supabase Postgres connection
string. For a local smoke test without Supabase, the project falls back to
SQLite; deployed environments should always provide `DATABASE_URL`.

Set `GEMINI_MODEL` to an available Flash-tier model from Google AI Studio.
The model is read only from the environment; restart Django after changing
`.env`.

Run migrations and start Django:

```bash
python manage.py migrate
python manage.py runserver
```

The API health check is available at `http://localhost:8000/api/health/`.

### Frontend

In a second terminal:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Populate `frontend/.env` with the Supabase project URL and public anon key
from **Project Settings > API**, plus the backend URL:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_SUPABASE_URL=https://your-project-ref.supabase.co
VITE_SUPABASE_ANON_KEY=your-public-anon-key
```

Open the Vite URL shown in the terminal (normally `http://localhost:5173`).
Supabase Auth handles browser sessions, while Gemini and database credentials
remain on the backend.

### Backend Supabase Auth settings

Populate `backend/.env` with the project URL and JWKS issuer:

```env
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_JWKS_URL=https://your-project-ref.supabase.co/auth/v1/.well-known/jwks.json
SUPABASE_JWT_ISSUER=https://your-project-ref.supabase.co/auth/v1
```

The backend verifies access tokens using JWKS, creates a local `accounts.User`
mirror on the first authenticated request, and attaches saved sessions to
that user. Restart both development servers after changing environment files.

## Free-tier and local-development notes

- Gemini free-tier quota can produce 429 responses. The UI shows a dedicated
  rate-limit message and allows retrying the same action.
- Flash models can occasionally return temporary 503/busy responses.
- Hosted free-tier services may sleep or cold-start after inactivity, so the
  first request can take noticeably longer.
- Supabase email confirmation may be enabled by default for new projects.
  Confirm the signup email or disable confirmation temporarily for local QA.
- The frontend production bundle may emit a non-blocking Vite chunk-size
  warning because Supabase Auth is included in the browser bundle.

## Functional hardening included

The current pass includes distinct LLM loading labels, disabled async actions,
inline validation, retryable rate-limit/LLM errors, network and auth error
handling, a sessions empty state, clipboard confirmation, Markdown download,
and a phone-width responsive baseline.
