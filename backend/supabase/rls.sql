-- Run this in the Supabase SQL editor for the target project.
-- These tables are created by Django in the public schema and must not be exposed
-- through the public PostgREST anon/authenticated roles.

ALTER TABLE public.accounts_user ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prompt_sessions_promptsession ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prompt_sessions_specification ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prompt_sessions_generatedprompt ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.accounts_user FROM anon, authenticated;
REVOKE ALL ON TABLE public.prompt_sessions_promptsession FROM anon, authenticated;
REVOKE ALL ON TABLE public.prompt_sessions_specification FROM anon, authenticated;
REVOKE ALL ON TABLE public.prompt_sessions_generatedprompt FROM anon, authenticated;

-- Django connects directly to Postgres using its own database role. Keep the
-- application database credentials private and do not grant anon/authenticated
-- access to these tables.

-- If needed later, add explicit policies for a service role or trusted backend only.
