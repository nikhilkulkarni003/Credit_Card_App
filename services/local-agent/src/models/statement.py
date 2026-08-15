"""
Structured data models for parsed statements.

IMPORTANT: none of these models has a password/secret field. This is deliberate —
it makes it structurally impossible for the sync layer to accidentally serialize
a statement password into a Supabase payload, because the field does not exist.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["high", "medium", "low"]
TransactionType = Literal["purchase", "payment", "cash_advance", "fee", "interest", "refund", "other"]


class ExtractedTransaction(BaseModel):
    transaction_date: date
    posting_date: date | None = None
    merchant_name: str  # normalized
    original_description: str  # raw, verbatim from the PDF
    amount: Decimal
    currency: str = "INR"
    transaction_type: TransactionType


class ExtractedCharge(BaseModel):
    """A single named fee/charge line (interest, GST, late fee, annual fee, etc.)."""

    label: str
    amount: Decimal


class ReconciliationResult(BaseModel):
    ok: bool
    expected_total: Decimal
    actual_total: Decimal
    difference: Decimal
    explanation: str  # human-readable, e.g. "Extracted transactions total ... but statement purchase total is ..."


class ExtractedStatement(BaseModel):
    bank_code: str
    card_last_four: str = Field(pattern=r"^\d{4}$")
    statement_date: date | None = None
    statement_period_start: date | None = None
    statement_period_end: date | None = None
    due_date: date | None = None

    total_amount_due: Decimal | None = None
    minimum_amount_due: Decimal | None = None
    previous_balance: Decimal | None = None
    payments_received: Decimal | None = None
    purchases: Decimal | None = None
    cash_advances: Decimal | None = None
    interest: Decimal | None = None
    gst: Decimal | None = None
    late_payment_fee: Decimal | None = None
    annual_fee: Decimal | None = None
    other_charges: Decimal | None = None
    closing_balance: Decimal | None = None
    currency: str = "INR"

    transactions: list[ExtractedTransaction] = Field(default_factory=list)
    charges: list[ExtractedCharge] = Field(default_factory=list)

    extraction_confidence: Confidence = "medium"
    reconciliation: ReconciliationResult | None = None
