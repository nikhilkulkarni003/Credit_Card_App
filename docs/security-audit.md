# Security Audit — 2026-08-15 (Phase 0/1/2 checkpoint)

This is a point-in-time audit at the end of the initial build session. Re-run this checklist
at the end of every phase, especially before Phase 3 (Gmail OAuth) and Phase 8 (final hardening).

## Repo-wide secret scan

- Searched for `password=`, `secret=`, `api_key=`, `token=` patterns followed by long
  literal values across the repo: **no matches**.
- No `.env` or `.env.local` files exist in the repo (only `.env.example` files, which
  contain variable names only, no values).
- `git status` confirms no real credential files are staged or tracked.

## `.gitignore` coverage

Verified `.gitignore` excludes: `.env*` (except `.env.example`), `*.pem`/`*.key`,
`credentials.json`/`token.json`/`client_secret*.json`, the local vault directories,
`services/local-agent/local_agent.sqlite*`, all `*.pdf` except `tests/fixtures/**`, the
entire `data/` directory, logs, and standard Node/Python build artifacts.

## Password vault (`services/local-agent/src/vault`)

- Storage backend is `keyring` (OS credential store — Windows Credential Manager/DPAPI on
  this machine), not a custom encryption scheme.
- `test_password_never_appears_in_log_output` (in `tests/test_vault.py`) asserts a real
  secret value never appears in any captured log record across set/get/delete — **passing**.
- No model in `services/local-agent/src/models` has a password field, so the sync layer
  cannot structurally serialize a password into a Supabase payload.
- `test_password()` never calls `set_password()` internally — verified by test.

## Database / RLS

- RLS is enabled on all 10 user-relevant tables in `0002_row_level_security.sql`.
- Every policy chains back to `auth.uid()`, either directly (`user_id` column) or via a
  join through `cards.user_id` / `statements.card_id -> cards.user_id`.
- `banks` is the only table without user-scoped RLS by design (shared reference data,
  read-only to any authenticated user, no client write policy exists at all).
- The Supabase **service-role key** appears only in `services/local-agent/.env.example`
  (names only) and `apps/web/.env.example`'s server-only section with an explicit warning
  not to use it client-side; it does not appear in any `apps/web/src` file, so it cannot
  currently leak into the browser bundle.

## Web app

- `apps/web/src/lib/supabase/client.ts` (browser) only ever uses the anon key.
- No `SUPABASE_SERVICE_ROLE_KEY` reference exists anywhere under `apps/web/src`.
- `npx tsc --noEmit`, `npx eslint .`, and `npx next build` all pass with zero errors.

## Local agent

- `pytest` suite: 20/20 passing (vault: 8, HDFC parser: 5, categorization engine: 7).
- No network calls are made in any test (all Gmail/Supabase/AI dependencies are injected
  as fakes/protocols, per `MerchantRuleStore` / `AiCategorizer` in `categorization/engine.py`).

## Known gaps at this checkpoint (tracked, not yet built)

- Gmail OAuth flow itself is not yet implemented (Phase 3) — nothing to audit yet, but the
  `.env.example` already documents that the client secret is local-only.
- The local-agent -> Supabase sync job is not yet implemented — the "no password field on
  sync models" guarantee above is a design property, not yet exercised against a live sync.
- No local HTTP bridge between the web app and local agent exists yet (Phase 3+); when
  built, it must bind to `127.0.0.1` only and require a per-session token (see
  docs/security.md, "Local agent network exposure").
- No pre-commit secret-scanning hook is wired up yet (manual grep only, as above).

## Verdict

No secrets, credentials, or password values found anywhere in the tracked repo contents at
this checkpoint. Continue re-running this scan before every subsequent phase, particularly
once Gmail OAuth and the sync job add new places a mistake could occur.
