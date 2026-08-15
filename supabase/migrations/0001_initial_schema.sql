-- Credit Card CFO — initial schema
-- Design principles:
--   * Every user-owned table is scoped to auth.uid() (directly or via parent FK) for RLS.
--   * No table stores full card numbers, CVV, or statement passwords.
--   * UUID primary keys, created_at/updated_at timestamps, FKs + indexes on hot lookup columns.

create extension if not exists "pgcrypto";

-- ============================================================
-- profiles — one row per authenticated user
-- ============================================================
create table profiles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade unique,
  display_name text,
  ai_categorization_enabled boolean not null default true,
  ai_confidence_threshold numeric(5,2) not null default 80.00,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ============================================================
-- banks — shared reference data, NOT user-owned
-- ============================================================
create table banks (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  code text not null unique, -- e.g. 'HDFC', 'ICICI' — used by the parser registry
  statement_format text,     -- free-text notes on the statement layout/version
  active boolean not null default true,
  created_at timestamptz not null default now()
);

-- ============================================================
-- cards — user-owned
-- ============================================================
create table cards (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  bank_id uuid not null references banks(id) on delete restrict,
  card_name text not null,
  last_four_digits char(4) not null check (last_four_digits ~ '^[0-9]{4}$'),
  card_type text not null default 'credit' check (card_type in ('credit', 'charge')),
  credit_limit numeric(14,2),
  statement_day smallint check (statement_day between 1 and 31),
  default_due_day smallint check (default_due_day between 1 and 31),
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, bank_id, last_four_digits)
);
create index idx_cards_user_id on cards(user_id);

-- ============================================================
-- categories — user-owned (system defaults are seeded per-user on signup)
-- ============================================================
create table categories (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  parent_id uuid references categories(id) on delete set null,
  icon text,
  active boolean not null default true,
  system_default boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, parent_id, name)
);
create index idx_categories_user_id on categories(user_id);

-- ============================================================
-- statements — user-owned via card_id
-- ============================================================
create table statements (
  id uuid primary key default gen_random_uuid(),
  card_id uuid not null references cards(id) on delete cascade,
  gmail_message_id text,
  gmail_thread_id text,
  filename text,
  file_hash text, -- sha256 of the decrypted PDF, for duplicate detection
  statement_date date,
  statement_period_start date,
  statement_period_end date,
  due_date date,
  total_amount_due numeric(14,2),
  minimum_amount_due numeric(14,2),
  previous_balance numeric(14,2),
  payments_received numeric(14,2),
  purchases numeric(14,2),
  cash_advances numeric(14,2),
  interest numeric(14,2),
  gst numeric(14,2),
  late_payment_fee numeric(14,2),
  annual_fee numeric(14,2),
  other_charges numeric(14,2),
  closing_balance numeric(14,2),
  currency text not null default 'INR',
  extraction_confidence text check (extraction_confidence in ('high', 'medium', 'low')),
  reconciliation_status text not null default 'pending'
    check (reconciliation_status in ('pending', 'reconciled', 'mismatch', 'skipped')),
  reconciliation_note text,
  processing_status text not null default 'discovered'
    check (processing_status in ('discovered', 'queued', 'processing', 'needs_review', 'processed', 'failed', 'ignored')),
  processing_error text, -- safe, user-facing message only — never raw exceptions/secrets
  processed_at timestamptz,
  payment_status text not null default 'pending'
    check (payment_status in ('pending', 'partially_paid', 'paid', 'overdue')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (card_id, gmail_message_id)
);
create index idx_statements_card_id on statements(card_id);
create index idx_statements_due_date on statements(due_date);
create index idx_statements_statement_date on statements(statement_date);
create unique index idx_statements_file_hash on statements(card_id, file_hash) where file_hash is not null;

-- ============================================================
-- transactions — user-owned via statement_id -> card_id
-- ============================================================
create table transactions (
  id uuid primary key default gen_random_uuid(),
  statement_id uuid not null references statements(id) on delete cascade,
  transaction_date date not null,
  posting_date date,
  merchant_name text not null,       -- normalized
  original_description text not null, -- raw, as printed on statement
  amount numeric(14,2) not null,
  currency text not null default 'INR',
  transaction_type text not null check (transaction_type in ('purchase', 'payment', 'cash_advance', 'fee', 'interest', 'refund', 'other')),
  category_id uuid references categories(id) on delete set null,
  categorization_source text check (categorization_source in ('merchant_rule', 'deterministic_rule', 'ai', 'manual', 'uncategorized')),
  categorization_confidence numeric(5,2),
  categorization_reason text,
  manually_reviewed boolean not null default false,
  extraction_source text not null default 'pdf_parser',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index idx_transactions_statement_id on transactions(statement_id);
create index idx_transactions_category_id on transactions(category_id);
create index idx_transactions_transaction_date on transactions(transaction_date);
create index idx_transactions_merchant_name on transactions(merchant_name);

-- ============================================================
-- merchant_rules — user-owned, learned categorization
-- ============================================================
create table merchant_rules (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  merchant_pattern text not null,     -- raw pattern matched against original_description
  normalized_merchant text not null,  -- canonical display name, e.g. "Swiggy"
  category_id uuid not null references categories(id) on delete cascade,
  priority smallint not null default 100,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, merchant_pattern)
);
create index idx_merchant_rules_user_id on merchant_rules(user_id);

-- ============================================================
-- payments — user-owned via card_id
-- ============================================================
create table payments (
  id uuid primary key default gen_random_uuid(),
  card_id uuid not null references cards(id) on delete cascade,
  statement_id uuid references statements(id) on delete set null,
  payment_date date not null,
  amount numeric(14,2) not null check (amount > 0),
  payment_method text,
  reference text,
  notes text,
  created_at timestamptz not null default now()
);
create index idx_payments_card_id on payments(card_id);
create index idx_payments_statement_id on payments(statement_id);

-- ============================================================
-- processing_jobs — user-owned via statement_id -> card_id
-- ============================================================
create table processing_jobs (
  id uuid primary key default gen_random_uuid(),
  statement_id uuid not null references statements(id) on delete cascade,
  job_type text not null check (job_type in ('download', 'decrypt', 'parse', 'categorize', 'sync')),
  status text not null default 'pending' check (status in ('pending', 'running', 'succeeded', 'failed')),
  started_at timestamptz,
  completed_at timestamptz,
  error_code text,
  safe_error_message text, -- must never contain secrets/raw exception text
  created_at timestamptz not null default now()
);
create index idx_processing_jobs_statement_id on processing_jobs(statement_id);

-- ============================================================
-- processing_events — safe audit trail
-- ============================================================
create table processing_events (
  id uuid primary key default gen_random_uuid(),
  statement_id uuid references statements(id) on delete cascade,
  event_type text not null,
  message text not null, -- safe, human-readable; never secrets
  metadata jsonb,
  created_at timestamptz not null default now()
);
create index idx_processing_events_statement_id on processing_events(statement_id);

-- ============================================================
-- updated_at trigger helper
-- ============================================================
create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger trg_profiles_updated_at before update on profiles for each row execute function set_updated_at();
create trigger trg_cards_updated_at before update on cards for each row execute function set_updated_at();
create trigger trg_categories_updated_at before update on categories for each row execute function set_updated_at();
create trigger trg_statements_updated_at before update on statements for each row execute function set_updated_at();
create trigger trg_transactions_updated_at before update on transactions for each row execute function set_updated_at();
create trigger trg_merchant_rules_updated_at before update on merchant_rules for each row execute function set_updated_at();
