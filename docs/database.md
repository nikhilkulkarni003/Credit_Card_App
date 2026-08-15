# Database

Schema lives in `supabase/migrations/`, applied in order:

1. `0001_initial_schema.sql` — tables, constraints, indexes, `updated_at` triggers.
2. `0002_row_level_security.sql` — RLS enabled + policies on every user-owned table.
3. `0003_default_categories_and_signup.sql` — auto-provisions a `profiles` row and the default category tree for every new `auth.users` signup; seeds shared `banks` reference data.

## Ownership model

- `banks` is shared reference data (bank name/code/parser key) — readable by any authenticated user, not writable via the client API.
- `cards`, `categories`, `merchant_rules` are directly owned via `user_id`.
- `statements`, `payments`, `processing_jobs` are owned indirectly via `card_id -> cards.user_id`.
- `transactions`, `processing_events` are owned indirectly via `statement_id -> statements.card_id -> cards.user_id`.

This chain is enforced in every RLS policy (see `0002_row_level_security.sql`), not just in application code.

## No sensitive card data

`cards.last_four_digits` is the only card-number fragment stored (checked to be exactly 4 digits). Full PAN and CVV are never captured anywhere in the schema.

## Applying migrations

```bash
supabase link --project-ref <your-project-ref>
supabase db push
```

(Requires the Supabase CLI and a Supabase project — see README for setup.)
