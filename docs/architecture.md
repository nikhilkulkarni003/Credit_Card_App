# Architecture

## Components

1. **`apps/web`** — Next.js (App Router, TypeScript) web application. Deployed to Vercel. Talks to Supabase (Postgres + Auth) for all application data. Never handles statement passwords.
2. **`services/local-agent`** — Python 3.13 application that runs on the user's own machine. Owns everything sensitive:
   - Gmail OAuth + API access
   - The encrypted statement-password vault
   - PDF download, decryption, parsing, OCR
   - Deterministic + learned categorization, with AI fallback
   - Syncing *sanitized* structured data (statements, transactions — never passwords, never raw PDF bytes by default) up to Supabase
3. **`supabase`** — Postgres schema, migrations, RLS policies, seed data (default categories). Also provides Supabase Auth for the web app.
4. **Vercel** — hosts `apps/web` only.

## Data flow

```
Gmail (OAuth) -> local-agent (download PDF)
              -> local-agent (vault: fetch bank/card password, local only)
              -> local-agent (decrypt + parse PDF locally)
              -> local-agent (categorize: rules -> learned merchant rules -> AI fallback)
              -> local-agent (sync sanitized JSON, NO passwords, NO raw PDF) -> Supabase
Supabase -> apps/web (dashboard, statements, transactions, analytics)
```

## Local/cloud boundary (hard rule)

Statement passwords, OAuth token files, and raw PDF bytes never cross the boundary into Supabase, Vercel, or any AI API. Only structured, sanitized JSON (amounts, dates, merchant strings, categories, safe metadata) is synced to the cloud. See [security.md](security.md) for the full threat model.

## Why a local agent instead of a serverless function

Password-protected PDFs require holding a secret (the statement password) at decrypt time. Doing this in a cloud function would mean either storing the password in the cloud (prohibited) or passing it through a request on every run (still a cloud exposure). Running decrypt+parse entirely on the user's machine means the password is only ever read from local OS-protected storage and used in local process memory.

## Extensibility toward multi-user SaaS

Every user-owned table in the schema (`cards`, `statements`, `transactions`, `categories`, `merchant_rules`, `payments`) is scoped by `user_id` (directly or via a parent FK) and protected by RLS from day one, even though V1 has one user. `banks` (bank/card metadata) is shared/global, not user-owned. This means introducing a `tenant_id`/organization layer later does not require restructuring ownership — it is already row-scoped per user.

## Bank parser architecture

`services/local-agent/src/parsers/base.py` defines a `StatementParser` interface (`identify`, `extract_statement_metadata`, `extract_transactions`, `extract_charges`, `validate`, `normalize_merchant`). Each bank gets its own module implementing this interface, registered in a parser registry (`parsers/registry.py`) keyed by bank code. Adding a bank means adding one new module + one registry entry — no changes to core application logic.
