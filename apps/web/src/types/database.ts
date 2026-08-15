// Hand-written types matching supabase/migrations/0001_initial_schema.sql.
// Once a real Supabase project exists, regenerate with:
//   npx supabase gen types typescript --project-id <ref> > src/types/database.ts

export type Category = {
  id: string;
  user_id: string;
  name: string;
  parent_id: string | null;
  icon: string | null;
  active: boolean;
  system_default: boolean;
  created_at: string;
  updated_at: string;
};

export type Bank = {
  id: string;
  name: string;
  code: string;
  statement_format: string | null;
  active: boolean;
  created_at: string;
};

export type Card = {
  id: string;
  user_id: string;
  bank_id: string;
  card_name: string;
  last_four_digits: string;
  card_type: "credit" | "charge";
  credit_limit: number | null;
  statement_day: number | null;
  default_due_day: number | null;
  active: boolean;
  created_at: string;
  updated_at: string;
};

export type Statement = {
  id: string;
  card_id: string;
  gmail_message_id: string | null;
  gmail_thread_id: string | null;
  filename: string | null;
  file_hash: string | null;
  statement_date: string | null;
  statement_period_start: string | null;
  statement_period_end: string | null;
  due_date: string | null;
  total_amount_due: number | null;
  minimum_amount_due: number | null;
  previous_balance: number | null;
  payments_received: number | null;
  purchases: number | null;
  cash_advances: number | null;
  interest: number | null;
  gst: number | null;
  late_payment_fee: number | null;
  annual_fee: number | null;
  other_charges: number | null;
  closing_balance: number | null;
  currency: string;
  extraction_confidence: "high" | "medium" | "low" | null;
  reconciliation_status: "pending" | "reconciled" | "mismatch" | "skipped";
  reconciliation_note: string | null;
  processing_status:
    | "discovered"
    | "queued"
    | "processing"
    | "needs_review"
    | "processed"
    | "failed"
    | "ignored";
  processing_error: string | null;
  processed_at: string | null;
  payment_status: "pending" | "partially_paid" | "paid" | "overdue";
  created_at: string;
  updated_at: string;
};

export type Transaction = {
  id: string;
  statement_id: string;
  transaction_date: string;
  posting_date: string | null;
  merchant_name: string;
  original_description: string;
  amount: number;
  currency: string;
  transaction_type: "purchase" | "payment" | "cash_advance" | "fee" | "interest" | "refund" | "other";
  category_id: string | null;
  categorization_source: "merchant_rule" | "deterministic_rule" | "ai" | "manual" | "uncategorized" | null;
  categorization_confidence: number | null;
  categorization_reason: string | null;
  manually_reviewed: boolean;
  extraction_source: string;
  created_at: string;
  updated_at: string;
};

export type Payment = {
  id: string;
  card_id: string;
  statement_id: string | null;
  payment_date: string;
  amount: number;
  payment_method: string | null;
  reference: string | null;
  notes: string | null;
  created_at: string;
};

export type MerchantRule = {
  id: string;
  user_id: string;
  merchant_pattern: string;
  normalized_merchant: string;
  category_id: string;
  priority: number;
  active: boolean;
  created_at: string;
  updated_at: string;
};

type TableDef<Row> = { Row: Row; Insert: Partial<Row>; Update: Partial<Row>; Relationships: [] };

export type Database = {
  public: {
    Tables: {
      categories: TableDef<Category>;
      banks: TableDef<Bank>;
      cards: TableDef<Card>;
      statements: TableDef<Statement>;
      transactions: TableDef<Transaction>;
      payments: TableDef<Payment>;
      merchant_rules: TableDef<MerchantRule>;
    };
    Views: Record<string, never>;
    Functions: Record<string, never>;
    Enums: Record<string, never>;
    CompositeTypes: Record<string, never>;
  };
};
