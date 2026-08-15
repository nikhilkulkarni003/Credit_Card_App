-- Row Level Security — every user-owned table is locked to auth.uid().
-- banks is shared reference data: readable by any authenticated user, writable by no one via the API.

alter table profiles enable row level security;
alter table banks enable row level security;
alter table cards enable row level security;
alter table categories enable row level security;
alter table statements enable row level security;
alter table transactions enable row level security;
alter table merchant_rules enable row level security;
alter table payments enable row level security;
alter table processing_jobs enable row level security;
alter table processing_events enable row level security;

-- profiles
create policy "profiles_select_own" on profiles for select using (user_id = auth.uid());
create policy "profiles_insert_own" on profiles for insert with check (user_id = auth.uid());
create policy "profiles_update_own" on profiles for update using (user_id = auth.uid()) with check (user_id = auth.uid());

-- banks: read-only shared reference data for any authenticated user
create policy "banks_select_authenticated" on banks for select using (auth.role() = 'authenticated');

-- cards
create policy "cards_select_own" on cards for select using (user_id = auth.uid());
create policy "cards_insert_own" on cards for insert with check (user_id = auth.uid());
create policy "cards_update_own" on cards for update using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "cards_delete_own" on cards for delete using (user_id = auth.uid());

-- categories
create policy "categories_select_own" on categories for select using (user_id = auth.uid());
create policy "categories_insert_own" on categories for insert with check (user_id = auth.uid());
create policy "categories_update_own" on categories for update using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "categories_delete_own" on categories for delete using (user_id = auth.uid());

-- statements (owned via cards.user_id)
create policy "statements_select_own" on statements for select
  using (exists (select 1 from cards c where c.id = statements.card_id and c.user_id = auth.uid()));
create policy "statements_insert_own" on statements for insert
  with check (exists (select 1 from cards c where c.id = statements.card_id and c.user_id = auth.uid()));
create policy "statements_update_own" on statements for update
  using (exists (select 1 from cards c where c.id = statements.card_id and c.user_id = auth.uid()))
  with check (exists (select 1 from cards c where c.id = statements.card_id and c.user_id = auth.uid()));
create policy "statements_delete_own" on statements for delete
  using (exists (select 1 from cards c where c.id = statements.card_id and c.user_id = auth.uid()));

-- transactions (owned via statements -> cards.user_id)
create policy "transactions_select_own" on transactions for select
  using (exists (
    select 1 from statements s join cards c on c.id = s.card_id
    where s.id = transactions.statement_id and c.user_id = auth.uid()
  ));
create policy "transactions_insert_own" on transactions for insert
  with check (exists (
    select 1 from statements s join cards c on c.id = s.card_id
    where s.id = transactions.statement_id and c.user_id = auth.uid()
  ));
create policy "transactions_update_own" on transactions for update
  using (exists (
    select 1 from statements s join cards c on c.id = s.card_id
    where s.id = transactions.statement_id and c.user_id = auth.uid()
  ))
  with check (exists (
    select 1 from statements s join cards c on c.id = s.card_id
    where s.id = transactions.statement_id and c.user_id = auth.uid()
  ));
create policy "transactions_delete_own" on transactions for delete
  using (exists (
    select 1 from statements s join cards c on c.id = s.card_id
    where s.id = transactions.statement_id and c.user_id = auth.uid()
  ));

-- merchant_rules
create policy "merchant_rules_select_own" on merchant_rules for select using (user_id = auth.uid());
create policy "merchant_rules_insert_own" on merchant_rules for insert with check (user_id = auth.uid());
create policy "merchant_rules_update_own" on merchant_rules for update using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "merchant_rules_delete_own" on merchant_rules for delete using (user_id = auth.uid());

-- payments (owned via cards.user_id)
create policy "payments_select_own" on payments for select
  using (exists (select 1 from cards c where c.id = payments.card_id and c.user_id = auth.uid()));
create policy "payments_insert_own" on payments for insert
  with check (exists (select 1 from cards c where c.id = payments.card_id and c.user_id = auth.uid()));
create policy "payments_update_own" on payments for update
  using (exists (select 1 from cards c where c.id = payments.card_id and c.user_id = auth.uid()))
  with check (exists (select 1 from cards c where c.id = payments.card_id and c.user_id = auth.uid()));
create policy "payments_delete_own" on payments for delete
  using (exists (select 1 from cards c where c.id = payments.card_id and c.user_id = auth.uid()));

-- processing_jobs (owned via statements -> cards.user_id)
create policy "processing_jobs_select_own" on processing_jobs for select
  using (exists (
    select 1 from statements s join cards c on c.id = s.card_id
    where s.id = processing_jobs.statement_id and c.user_id = auth.uid()
  ));
create policy "processing_jobs_insert_own" on processing_jobs for insert
  with check (exists (
    select 1 from statements s join cards c on c.id = s.card_id
    where s.id = processing_jobs.statement_id and c.user_id = auth.uid()
  ));
create policy "processing_jobs_update_own" on processing_jobs for update
  using (exists (
    select 1 from statements s join cards c on c.id = s.card_id
    where s.id = processing_jobs.statement_id and c.user_id = auth.uid()
  ));

-- processing_events (owned via statements -> cards.user_id, nullable statement_id treated as inaccessible)
create policy "processing_events_select_own" on processing_events for select
  using (exists (
    select 1 from statements s join cards c on c.id = s.card_id
    where s.id = processing_events.statement_id and c.user_id = auth.uid()
  ));
create policy "processing_events_insert_own" on processing_events for insert
  with check (exists (
    select 1 from statements s join cards c on c.id = s.card_id
    where s.id = processing_events.statement_id and c.user_id = auth.uid()
  ));

-- NOTE: all writes described above are reachable via the anon/authenticated key + RLS.
-- The Supabase service-role key (used only by the local agent's sync process) bypasses RLS
-- by design and must never be exposed to the browser/Next.js client bundle.
