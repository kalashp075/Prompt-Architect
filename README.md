# Prompt Architect

Prompt Architect turns an unstructured idea into a clear, target-specific
prompt. The current implementation requires an authenticated user to start a
session, and everything beyond the initial idea box happens only after login.

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
string. Production startup requires this variable; SQLite is intended only
for local development.

Set `GEMINI_MODEL` to an available Flash-tier model from Google AI Studio.
The model is read only from the environment; restart Django after changing
`.env`.

Run migrations and start Django:

```bash
python manage.py migrate
python manage.py runserver
```

The API health check is available at `http://localhost:8000/api/health/`.

Production deployments must provide `DATABASE_URL`, a 32+ character
`DJANGO_SECRET_KEY`, `SUPABASE_JWT_ISSUER`, a JWKS/URL setting, and
`SECURE_PROXY_SSL_HEADER=https`. Prompt creation, clarification, and final
generation require an authenticated Supabase session.

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
- Email authentication uses Supabase Auth; Django does not send or store email
  credentials. In Supabase Dashboard, open `Authentication > Providers >
  Email`, enable the Email provider and **Confirm email**, and set the Site URL
  plus redirect URL to your frontend origins (for local development:
  `http://localhost:5173` and `http://localhost:5173/auth/callback`).
- Supabase sends the confirmation link and controls its token expiry, one-time
  use, abuse protection, and provider-side email rate limits. The UI adds a
  60-second resend cooldown. Configure custom SMTP under
  `Authentication > Settings > SMTP` before production; the built-in sender is
  intended for testing and has strict limits. Do not put a Gmail app password
  or SMTP secret in this repository or in frontend variables.
- Signup accepts common consumer providers (Gmail, Outlook/Hotmail, Yahoo,
  iCloud, Proton Mail, AOL, and Zoho). This is an application policy, not a
  security boundary; update the allowlist in `frontend/src/App.jsx` if the
  product should support additional providers.
- The frontend production bundle may emit a non-blocking Vite chunk-size
  warning because Supabase Auth is included in the browser bundle. Vendor
  chunks are split during the production build.

  ## Supabase database hardening

  After running Django migrations against the target Supabase project, run
  [`backend/supabase/rls.sql`](./backend/supabase/rls.sql) in the Supabase SQL
  Editor. This enables Row Level Security and revokes browser-facing
  `anon`/`authenticated` access to the Django-owned application tables. Django
  connects through the private database connection and performs the ownership
  checks in the API, so do not add public policies for these tables.

  The script is intentionally limited to the application tables:

  - `accounts_user`
  - `prompt_sessions_promptsession`
  - `prompt_sessions_specification`
  - `prompt_sessions_generatedprompt`

  Do not run it against Supabase-managed `auth.*` tables.

  ## Production checklist

  Before deploying:

  1. Set `DJANGO_DEBUG=false`, a long random `DJANGO_SECRET_KEY`, a production
     `DATABASE_URL`, exact `ALLOWED_HOSTS`, exact `CORS_ALLOWED_ORIGINS`, and
     `SUPABASE_JWT_ISSUER`.
  2. Set `DJANGO_SECURE_SSL_REDIRECT=true` and terminate TLS at the platform or
     a trusted reverse proxy. If the proxy forwards `X-Forwarded-Proto`, set
     `SECURE_PROXY_SSL_HEADER` in the deployment environment as required by
     that platform.
  3. Run `python manage.py check --deploy` and
     `python manage.py migrate` during the release process. Serve Django with a
     production WSGI/ASGI server, not `runserver`.
  4. Configure Supabase backups and verify Row Level Security policies for any
     tables exposed through Supabase APIs. Django ownership checks remain
     required even when RLS is enabled.
  5. Keep Gemini credentials server-side. Set an available Flash-tier
     `GEMINI_MODEL`, review the configured request limits, and monitor latency,
     errors, token usage, and provider quota.
  6. Run dependency checks before release:

     ```bash
     npm audit --audit-level=high
     pip-audit -r backend/requirements.txt
     ```

  7. Publish a privacy notice that explains session retention and that prompt
     content is sent to Google Gemini. Do not collect confidential or regulated
     data until retention, deletion, and incident-response procedures are in
     place.

  Prompt sessions are tied to the authenticated user account, so the user must
  sign in before the app creates or resumes a prompt.

## Functional hardening included

The current pass includes distinct LLM loading labels, disabled async actions,
inline validation, retryable rate-limit/LLM errors, network and auth error
handling, a sessions empty state, clipboard confirmation, Markdown download,
and a phone-width responsive baseline.
