# Prompt Architect pre-deployment checklist

This checklist is based on the current repository audit. Items marked **Done in
the repository** have been implemented in code. Items marked **Manual check**
require access to the deployment platform, Supabase project, or production
environment and must be verified before launch.

## Must complete before launch

### Production configuration and HTTPS — Manual check

- [ ] Set `DJANGO_DEBUG=false` in the production environment. Never use the
  development fallback secret in production.
- [ ] Set a randomly generated `DJANGO_SECRET_KEY` of at least 50 characters.
- [ ] Set production `ALLOWED_HOSTS` to the exact API hostnames; do not use `*`.
- [ ] Set `CORS_ALLOWED_ORIGINS` to the exact deployed frontend origin(s); do
  not use a wildcard.
- [ ] Set `DATABASE_URL` to the production PostgreSQL/Supabase connection
  string. Do not use SQLite.
- [ ] Set `SUPABASE_URL` or `SUPABASE_JWKS_URL` and
  `SUPABASE_JWT_ISSUER` to production values.
- [ ] Keep `SECURE_PROXY_SSL_HEADER` only behind a trusted TLS terminator.
  The proxy must strip a client-provided `X-Forwarded-Proto` and set it from
  the actual connection, for example:

  ```nginx
  proxy_set_header X-Forwarded-Proto $scheme;
  ```

- [ ] Keep HTTP-to-HTTPS redirection enabled and verify it externally:

  ```bash
  curl -I http://api.example.com/
  curl -I https://api.example.com/
  ```

  The HTTP response must redirect to HTTPS, and Django must not be directly
  reachable around the proxy.
- [ ] Verify these response headers on the deployed API and frontend:
  `Strict-Transport-Security`, `Content-Security-Policy`,
  `X-Frame-Options`, `X-Content-Type-Options`, and `Referrer-Policy`.
- [ ] Confirm every subdomain is HTTPS before relying on HSTS subdomain or
  preload behavior.
- [ ] Run the following with production-equivalent environment variables and
  resolve every warning:

  ```bash
  python manage.py check --deploy --fail-level WARNING
  ```

### Supabase and database — Manual check

- [ ] Apply and verify [`backend/supabase/rls.sql`](./backend/supabase/rls.sql)
  in the target Supabase project.
- [ ] Test anonymous and authenticated PostgREST access to application tables;
  public/anonymous clients must not be able to read or write Django-owned data.
- [ ] Confirm the Django database role has only the privileges it needs.
- [ ] Confirm database credentials are stored in the deployment secret manager,
  rotated, and never exposed to the browser.
- [ ] Confirm migrations run successfully against the production database
  before serving traffic.

### Secrets, AI usage, and abuse controls — Manual check / implementation

- [ ] Keep `GEMINI_API_KEY` and database credentials backend-only. Never put
  them in `VITE_*` variables or frontend bundles.
- [ ] Set a valid `GEMINI_MODEL` and production Gemini input/output limits.
- [ ] Add a durable per-user daily/monthly generation quota before enabling
  paid production usage.
- [ ] Add global provider spend limits, billing alerts, usage tracking, and a
  circuit breaker for unexpected Gemini cost or provider failure.
- [ ] Verify the existing Gemini request throttle is applied to every
  expensive generation path, not only session creation.
- [ ] Add abuse protection for signup, login, password/email confirmation, and
  repeated failed requests at the identity provider or edge layer.
- [ ] Do not log prompt contents, access tokens, API keys, or full provider
  error payloads in centralized logs.

### Privacy and data rights — Manual/legal check

- [ ] Replace the current MVP privacy summary with a legally reviewed policy
  that names the data controller, processing purposes, Gemini transfer,
  retention periods, subprocessors, user rights, and contact method.
- [ ] Decide whether Supabase authentication storage requires a consent banner
  in the target jurisdictions. If optional analytics or tracking is added,
  gate it behind consent and document the choices.
- [ ] Document that **Delete my application data** removes data from this
  application but does not by itself delete the Supabase Auth identity. Provide
  a verified process for complete account deletion, including Supabase Auth.
- [ ] Confirm export and deletion requests are covered by an operational
  response process and audit trail.

## Completed in the repository

- [x] Added accessible labels to the primary idea, clarification, custom
  requirements, email, and password controls.
- [x] Added an explicit in-app 404 state for unknown routes.
- [x] Added `frontend/public/favicon.svg`.
- [x] Added `frontend/public/robots.txt` and `frontend/public/sitemap.xml`.
- [x] Added title, description, Open Graph, Twitter card, canonical, theme
  color, and favicon metadata to `frontend/index.html`.
- [x] Added an authenticated JSON export endpoint at
  `/api/account/export/` and an **Export my data** account action.
- [x] Added an authenticated application-data deletion endpoint at
  `/api/account/data/` and a confirmed **Delete my application data** action.
  This deletes the Django-side account record and all owned prompt sessions;
  Supabase Auth deletion still requires the manual process above.
- [x] Improved the contrast of the small sidebar section labels.
- [x] Confirmed there is no file-upload surface, so upload validation is not
  currently applicable.
- [x] Confirmed the frontend source has no debug `console.log`, `debugger`,
  TODO/FIXME markers, or obvious test data.

## Dependency and release validation

- [ ] From `frontend/`, run:

  ```bash
  npm audit --omit=dev --audit-level=moderate
  npm audit fix
  npm run build
  ```

  Resolve or formally accept the reported transitive `source-map-js`
  vulnerability after confirming it is build-only and absent from the runtime
  bundle.
- [ ] Install the backend requirements in the release environment and run:

  ```bash
  python manage.py test
  python manage.py check --deploy --fail-level WARNING
  ```

- [ ] Test export and deletion with a real authenticated account, including
  sessions with and without specifications/generated prompts.
- [ ] Verify all destructive actions require authentication and explicit
  confirmation.
- [ ] Verify no prompt data appears in error pages, logs, analytics, or
  browser URLs.

## Browser and accessibility acceptance

- [ ] Test keyboard-only navigation, visible focus, Escape behavior, sidebar
  focus, and modal/popover interaction.
- [ ] Test screen-reader names and validation messages for every form control.
- [ ] Verify contrast for all text/background combinations against WCAG AA.
- [ ] Test at 320px and 375px widths on iOS Safari and Android Chrome.
- [ ] Check long textarea input, mobile keyboard behavior, copy/download
  actions, and horizontal overflow.
- [ ] Check the browser console and network panel on the production build.

## Deployment operations and recovery — Manual check

- [ ] Configure a repeatable deployment with locked dependency versions.
- [ ] Run migrations before releasing application traffic.
- [ ] Configure automated encrypted database backups and test a restore.
- [ ] Configure centralized error monitoring and alerts without collecting
  sensitive prompt content.
- [ ] Define secret rotation, key revocation, incident response, rollback, and
  recovery procedures.
- [ ] Configure health checks for `/api/health/` and verify the process manager
  restarts unhealthy workers.
- [ ] Verify the deployed frontend returns `200` for the SPA shell and that
  `/favicon.svg`, `/robots.txt`, and `/sitemap.xml` are publicly reachable.
- [ ] Replace placeholder canonical, Open Graph, Twitter, robots, and sitemap
  URLs with the real production domain.
