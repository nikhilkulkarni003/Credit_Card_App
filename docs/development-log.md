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

**Remaining work (as of the end of this entry):** categorization AI fallback (Gemini) not wired up yet (deterministic rules + learned merchant rules only for now — by design, AI is optional); only 2 of the 18 real candidate statements had been processed at this point; no "New Statements Found" review UI yet (statements processed one at a time via CLI); no payment-marking UI; no expense analytics/reports page; only 1 of 7+ banks seen in the real inbox had a parser.

## 2026-08-20 (continued) — Phase 7: two more real bank parsers (ICICI, IndusInd)

**What was implemented:**
- **ICICI (Amazon Pay ICICI) parser** (`src/parsers/icici.py`), calibrated against a real statement via the same `debug-extract` workflow. Real-world quirk found: the rupee symbol extracts as a backtick `` ` `` (a different font artifact than HDFC's "C"), and — more importantly — the printed "Total Amount Due" / "Minimum Amount Due" values appear in an order that does **not** reliably match their label order (separated by an unrelated Earnings block). Resolved without guessing which value is which by using a real constraint instead: Minimum Amount Due is always ≤ Total Amount Due by RBI convention, so `max()`/`min()` of the two candidates is used rather than positional order. Reconciled correctly and synced on the **first live attempt** — 3/3 transactions, card last four `9004`.
- **IndusInd Bank parser** (`src/parsers/indusind.py`), calibrated against a real statement that happened to have **active EMI conversions** — the messiest layout of the three so far. Findings: the header block's printed VALUE order doesn't match its LABEL order either (positions for "Purchases & Other Charges" and "Cash Advance" are swapped); "Purchases & Other Charges" is not pure retail spend but already folds in that cycle's interest/GST/EMI installment charges, so `validate()` is overridden per-bank to avoid double-counting a separate charges total on top of it; "Total Amount Due" is not printed as a single unambiguous value at all, so it is computed from the reconciliation formula and documented as derived, not printed; and **Payment Due Date could not be confidently extracted from the text layer** — left as `None` rather than guessed, flagged for the user to check whether the real PDF renders it as an image.
- Both banks added to `banks` table (migrations `0005`, `0006`), `gmail/detector.py` sender-domain recognition, and the parser registry.

**Bugs found and fixed during live testing:**
1. IndusInd: the first live run against the real statement returned `None` for previous balance/purchases/total/closing balance, despite the exact same raw text having been used to calibrate the parser and pass all 7 unit tests moments earlier. Root cause: the header **values** print roughly 30–40 lines after the header **labels** (a large intervening block of payment-slip fields, Credit Summary labels, transaction-table column headers, and marketing messages) — but the synthetic test fixture had placed labels and values close together, so the fixture passed while not actually representing the real document's structure. This is a fixture/reality mismatch, not a logic bug — the extraction regex's 200-character search window was simply too small to span the real gap. Fixed by anchoring on `"Closing Balance(Points)"` (the last of the intervening labels, immediately before the real values start) instead of trying to span the whole gap from `"Previous Balance"`, and rebuilt the fixture with a realistic gap so this class of bug gets caught by tests next time rather than only in production.

**Outcome:** three banks (HDFC, ICICI, IndusInd) now have parsers calibrated against real statements, all reconciling correctly and synced into the live Supabase project, visible in the dashboard. `sync-statement` has now been run successfully against three different real card products from three different banks, including one with active EMI loans — the pipeline (download → decrypt → parse → reconcile → categorize → sync) has held up across meaningfully different statement layouts, not just one.

**Test suite:** 44/44 passing after this entry (vault: 8, HDFC: 5, ICICI: 7, IndusInd: 7, categorization engine: 7, Gmail detector: 7, Gmail client: 3, ICICI/IndusInd identify smoke tests included above).

**Remaining work:** Gemini AI categorization fallback still not wired up; SBI Elite / IDFC FIRST / Suryoday / BOBCARD still have no parsers (4 of the original 18 discovered statements' banks); no "New Statements Found" review UI (still CLI, one statement at a time); no payment-marking UI; no expense analytics/reports page; IndusInd's Payment Due Date gap is unresolved (needs the user to check the actual PDF for an image-rendered due date).
