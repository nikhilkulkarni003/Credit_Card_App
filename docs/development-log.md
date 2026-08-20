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

## 2026-08-20 — Phases 1–5: live credentials wired up, full pipeline validated end-to-end

**What was implemented:**
- Live Supabase project (`gylwwppdtekdvbfsmeqy`) connected; all 4 migrations applied via `supabase db push`, including a hot-fix (`0004_fix_signup_trigger_search_path.sql`) for a real bug hit on first sign-in (see below).
- Web app running against the live project; magic-link sign-in, card creation, dashboard KPIs all confirmed working against real RLS-protected data.
- Gmail OAuth fully wired (`src/gmail/auth.py`, `client.py`, `detector.py`) and connected to the user's real Gmail account (`nikhilkulkarni003@gmail.com`, read-only scope). A real inbox scan found 50 candidate emails, 18 correctly identified as statement emails across 7+ banks (HDFC, ICICI, SBI, IDFC FIRST, IndusInd, Suryoday, BOBCARD) — the detector heuristic works well on real data.
- **HDFC parser recalibrated against a real statement.** The original parser (written from general knowledge, never seen a real HDFC layout) scored 0/8 fields on the first live run. Used a new `debug-extract` CLI command to dump decrypted statement text to a local, git-ignored file — the raw statement content was never sent anywhere, including to the AI assistant building this — only the structural layout (label/value positioning, the rupee-symbol-as-"C" font quirk, multi-line transaction rows) was used to recalibrate. Second run: all fields extracted correctly, reconciliation passed within tolerance, against the user's real July 2026 statement.
- Built the Supabase sync layer (`src/sync/`) and wired the categorization engine to real `merchant_rules`/`categories` tables (`src/categorization/supabase_rule_store.py`). `sync-statement` CLI command runs the full pipeline (download → decrypt → parse → reconcile → categorize → write to Supabase) and is idempotent (re-running skips already-synced statements via the `card_id`+`gmail_message_id` unique constraint).
- **Confirmed end-to-end, with real data, in the actual dashboard**: real HDFC statement + 2 real transactions visible in the web UI, reconciliation shows OK.

**Bugs found and fixed during live testing (all real, none hypothetical):**
1. Signup trigger (`handle_new_user`) failed with "Database error saving new user" on the very first real sign-in — `SECURITY DEFINER` functions invoked by the Auth server run with a minimal `search_path`, so unqualified table references didn't resolve. Fixed by fully-qualifying with `public.` and pinning `search_path` explicitly.
2. `src/vault/__init__.py` didn't export `PasswordScope`, breaking `cli.py`'s import — one-line fix.
3. Gmail attachment detection was silently broken: `format="metadata"` never returns the MIME parts tree at all (only headers), so `has_pdf_attachment` was unconditionally `False`. Also, real Gmail messages nest attachments several levels deep in the MIME tree, not just at the top level. Fixed by switching to `format="full"` plus a recursive part-walker (`_walk_parts`), with tests covering the nested case.
4. HDFC parser regexes were wrong across the board against real data (see above) — rewrote from the real layout, including a merchant-normalization ordering bug (stripping a long reference token before the base class's trailing-`*SUFFIX` regex ran left a dangling `*`) and a stray REWARDS-column artifact ("l") landing inconsistently before or after the amount line depending on PDF extraction order.

**Security verification during this session:**
- Statement password: entered only via `getpass` (hidden input, never a CLI argument), stored via `keyring` immediately, and confirmed never appearing in any terminal output across `set-password`/`process-statement`/`sync-statement`.
- Gmail OAuth client secret and Supabase service-role key: both provided by the user in chat (their own choice, for their own local-only config), written directly into the git-ignored `services/local-agent/.env`, never logged, never included in any Supabase payload.
- `debug-extract` was used specifically so real statement *content* (balances, transaction details) never had to be shared in chat to fix the parser — only the anonymized structural layout was shared by the user, by choice, to calibrate regexes.
- Verified `git status`/`git add -A` diffs before every commit in this session — no `.env`, no PDFs, no credentials ever staged.

**Remaining work:** categorization AI fallback (Gemini) not wired up yet (deterministic rules + learned merchant rules only for now — by design, AI is optional); only 2 of the 18 real candidate statements have been processed (the rest need either more bank parsers or manual processing via the same HDFC flow for other HDFC statements); no "New Statements Found" review UI yet (statements are currently processed one at a time via CLI); no payment-marking UI; no expense analytics/reports page; only 1 of 7+ banks seen in the real inbox has a parser.
