# Development Log

## 2026-08-15 — Phase 0: Architecture & Environment

**Environment inspected:**
- Directory was empty, no existing project, no git repo.
- Node v24.18.0, npm 11.16.0 — present.
- Python 3.13.14 — present (accessible via `py -3` / full path; bare `python` alias is inconsistent on this machine, so scripts/docs use `py -3`).
- Git 2.55.0 — present.
- pnpm/yarn — not installed. **Decision:** use npm as the package manager (avoids an extra install; can switch later without much friction).
- Supabase CLI, Vercel CLI, Tesseract — not installed. Will be needed later (Phase 1 for Supabase CLI, Phase 7+ for OCR fallback). Not blocking for Phase 0/1 scaffolding.

**What was implemented:**
- Initialized git repository.
- Created monorepo structure: `apps/web`, `services/local-agent` (with `gmail/vault/pdf/parsers/categorization/ocr/sync/models` subpackages), `supabase/migrations`, `supabase/seed`, `docs`, `scripts`, `tests/fixtures`, `data/statements`.
- Wrote `.gitignore` covering: env files, all local vault/credential files, `*.pdf` (except test fixtures), the entire `data/` directory, logs, Python/Node build artifacts, Supabase local state.

**Security decisions:**
- `data/statements/` (where downloaded original PDFs live) is git-ignored entirely.
- Any file matching `*.pdf` is ignored by default; only files explicitly placed under `tests/fixtures/` are allowed, and those must be synthetic, never real statements.
- No `.env` file exists yet; only `.env.example` (names only, no values) will be committed.

**Remaining work:** Phase 1 (Next.js + Supabase foundation), Phase 2 (local agent + password vault — critical path), then Gmail/PDF/categorization phases per the phased plan in the project's master prompt.

**Note on scope:** This is a large, multi-phase build (full-stack web app, Python local agent, encrypted local vault, Gmail OAuth, bank-specific PDF parsing, AI-assisted categorization, Supabase schema with RLS). Phases 3+ (live Gmail OAuth, live Supabase project, live Gemini calls) require the user to provision their own credentials (Google Cloud OAuth client, Supabase project, Gemini API key) — the code will be built as real, working integrations, but cannot be exercised end-to-end without those credentials being supplied by the user outside of any cloud service that must never see statement passwords.
