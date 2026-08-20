"""
Sync layer: writes sanitized, structured data (statements, transactions) to
Supabase. Deliberately narrow — the ExtractedStatement/ExtractedTransaction
models have no password field, so there is nothing sensitive to accidentally
serialize here. Idempotent: relies on the DB's unique constraints
(card_id+gmail_message_id for statements) so re-processing the same email
never creates duplicates.
"""

from __future__ import annotations

from supabase import Client

from src.categorization.engine import CategorizationEngine
from src.models.statement import ExtractedStatement


class CardNotFound(Exception):
    pass


def get_single_user_id(client: Client) -> str:
    """V1 is single-user: use the one profile row. Raises if 0 or >1 profiles exist."""
    response = client.table("profiles").select("user_id").execute()
    if not response.data:
        raise RuntimeError("No profiles found — sign in to the web app at least once first.")
    if len(response.data) > 1:
        raise RuntimeError(
            "Multiple profiles found; this sync helper assumes single-user V1. "
            "Pass an explicit user_id instead of relying on auto-detection."
        )
    return response.data[0]["user_id"]


def get_card_id(client: Client, user_id: str, bank_code: str, last_four: str) -> str:
    response = (
        client.table("cards")
        .select("id, banks!inner(code)")
        .eq("user_id", user_id)
        .eq("last_four_digits", last_four)
        .eq("banks.code", bank_code.upper())
        .limit(1)
        .execute()
    )
    if not response.data:
        raise CardNotFound(
            f"No card found for bank={bank_code} last_four={last_four}. Add it in the dashboard first."
        )
    return response.data[0]["id"]


def upsert_statement(
    client: Client, card_id: str, gmail_message_id: str, filename: str, statement: ExtractedStatement
) -> tuple[str, bool]:
    """Returns (statement_id, was_newly_created)."""
    existing = (
        client.table("statements")
        .select("id")
        .eq("card_id", card_id)
        .eq("gmail_message_id", gmail_message_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        return existing.data[0]["id"], False

    reconciliation_status = "pending"
    reconciliation_note = None
    if statement.reconciliation is not None:
        reconciliation_status = "reconciled" if statement.reconciliation.ok else "mismatch"
        reconciliation_note = statement.reconciliation.explanation

    payload = {
        "card_id": card_id,
        "gmail_message_id": gmail_message_id,
        "filename": filename,
        "statement_date": _iso(statement.statement_date),
        "statement_period_start": _iso(statement.statement_period_start),
        "statement_period_end": _iso(statement.statement_period_end),
        "due_date": _iso(statement.due_date),
        "total_amount_due": _dec(statement.total_amount_due),
        "minimum_amount_due": _dec(statement.minimum_amount_due),
        "previous_balance": _dec(statement.previous_balance),
        "payments_received": _dec(statement.payments_received),
        "purchases": _dec(statement.purchases),
        "cash_advances": _dec(statement.cash_advances),
        "interest": _dec(statement.interest),
        "gst": _dec(statement.gst),
        "late_payment_fee": _dec(statement.late_payment_fee),
        "annual_fee": _dec(statement.annual_fee),
        "other_charges": _dec(statement.other_charges),
        "closing_balance": _dec(statement.closing_balance),
        "currency": statement.currency,
        "extraction_confidence": statement.extraction_confidence,
        "reconciliation_status": reconciliation_status,
        "reconciliation_note": reconciliation_note,
        "processing_status": "processed",
        "processed_at": "now()",
    }
    result = client.table("statements").insert(payload).execute()
    return result.data[0]["id"], True


def sync_transactions(
    client: Client,
    user_id: str,
    statement_id: str,
    statement: ExtractedStatement,
    engine: CategorizationEngine,
) -> int:
    """Categorizes and inserts every transaction. Returns count inserted."""
    rows = []
    for txn in statement.transactions:
        result = engine.categorize(user_id, txn.merchant_name, txn.original_description, str(txn.amount))
        category_id = None
        if result.category_name:
            cat_response = (
                client.table("categories")
                .select("id")
                .eq("user_id", user_id)
                .eq("name", result.category_name)
                .limit(1)
                .execute()
            )
            if cat_response.data:
                category_id = cat_response.data[0]["id"]

        rows.append(
            {
                "statement_id": statement_id,
                "transaction_date": _iso(txn.transaction_date),
                "posting_date": _iso(txn.posting_date),
                "merchant_name": txn.merchant_name,
                "original_description": txn.original_description,
                "amount": _dec(txn.amount),
                "currency": txn.currency,
                "transaction_type": txn.transaction_type,
                "category_id": category_id,
                "categorization_source": result.source,
                "categorization_confidence": result.confidence,
                "categorization_reason": result.reason,
                "manually_reviewed": False,
                "extraction_source": "pdf_parser",
            }
        )
    if rows:
        client.table("transactions").insert(rows).execute()
    return len(rows)


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None


def _dec(value) -> float | None:
    return float(value) if value is not None else None
