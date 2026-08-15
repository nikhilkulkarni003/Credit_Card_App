# Credit Card CFO

A personal credit-card statement management app: connects to Gmail, downloads statement
PDFs, decrypts them **locally** with a password that never leaves your machine, extracts
transactions, categorizes them (rules first, AI only as a fallback), and gives you a
dashboard of dues, spending, and payment status.

See [docs/architecture.md](docs/architecture.md) and [docs/security.md](docs/security.md)
before touching anything password/credential related.

## Repository layout

```
apps/web              Next.js 16 app (Vercel) — dashboard, auth, analytics
services/local-agent   Python 3.11+ local agent — Gmail, password vault, PDF parsing, categorization
supabase/migrations    Postgres schema + RLS
docs/                  Architecture, security, database, and phase-by-phase dev log
tests/fixtures         Synthetic (fake) statement fixtures only — never real statements
```

## Prerequisites

- Node.js 20.9+ (works with the Node 24 installed in this environment)
- Python 3.11+ (use the **standard** CPython build, not a free-threaded `3.13t` build —
  several native-extension packages like `pymupdf`/`pydantic` don't yet ship wheels for it)
- A Supabase project (free tier is enough for V1)
- A Google Cloud project with the Gmail API enabled and an OAuth 2.0 **Desktop app** client
- (Optional) A Gemini API key, only if you want AI categorization fallback

## 1. Set up Supabase

1. Create a project at supabase.com.
2. Apply the migrations in order (via SQL editor or the CLI):
   - `supabase/migrations/0001_initial_schema.sql`
   - `supabase/migrations/0002_row_level_security.sql`
   - `supabase/migrations/0003_default_categories_and_signup.sql`
3. Copy `apps/web/.env.example` to `apps/web/.env.local` and fill in
   `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` from Project Settings > API.
4. Copy `services/local-agent/.env.example` to `services/local-agent/.env` and fill in
   `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` (the **service role** key — keep this out
   of the web app entirely).

## 2. Run the web app

```bash
cd apps/web
npm install
npm run dev
```

Visit http://localhost:3000, sign in with a magic link (Supabase Auth), and you'll land on
an empty dashboard — a fresh `profiles` row and the default category tree are created
automatically on first sign-in (see `supabase/migrations/0003_...sql`).

## 3. Set up the local agent

```bash
cd services/local-agent
py -3.13 -m venv .venv        # use the standard build, see note above
.venv\Scripts\pip install -e .[dev]
copy .env.example .env        # then fill in Supabase + Gmail OAuth values
.venv\Scripts\pytest tests/ -v
```

All 20 tests (vault security, HDFC reference parser, categorization engine) should pass
without any credentials configured — they use fakes/in-memory backends, not real Gmail or
Supabase.

### Connect Gmail

You'll need your own Google Cloud OAuth client (Desktop app type) — see
[docs/gmail-integration.md](docs/gmail-integration.md) (to be filled in during Phase 3) for
the exact console steps. Client ID/secret go in `services/local-agent/.env`; the resulting
OAuth tokens are stored via the OS credential store, never as a plaintext file.

### Add your first bank password

The password vault (`services/local-agent/src/vault`) is usable standalone right now:

```python
from src.vault import PasswordVault, PasswordScope
vault = PasswordVault()
vault.set_password(PasswordScope(bank_code="HDFC"), "your-statement-password")
```

This writes to Windows Credential Manager via `keyring` — never to a file, never to Supabase.
A CLI/UI wrapper for this is planned; see `docs/development-log.md` for status.

## Running tests

```bash
# Local agent (Python)
cd services/local-agent && .venv\Scripts\pytest tests/ -v

# Web app (TypeScript)
cd apps/web && npx tsc --noEmit && npx eslint .
```

## Current status

See [docs/development-log.md](docs/development-log.md) for exactly what's built, what's
stubbed, and what's next. In short: database schema + RLS, the Next.js dashboard shell
(auth, cards, categories, statements/transactions views), the password vault, the
categorization engine, and one reference bank parser (HDFC) are built and tested. Gmail
OAuth wiring, the local-agent sync-to-Supabase job, and the AI (Gemini) fallback client
are scaffolded in the architecture but need your own credentials to exercise end-to-end.
