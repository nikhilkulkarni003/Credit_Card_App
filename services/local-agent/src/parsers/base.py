"""
StatementParser interface — every bank-specific parser implements this.

Do NOT add bank-specific branching to application/sync code. Instead add a new
module here implementing StatementParser, and register it in registry.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.models.statement import ExtractedCharge, ExtractedStatement, ExtractedTransaction, ReconciliationResult


class StatementParseError(Exception):
    """Raised when a PDF cannot be parsed by a given bank parser. Message must be safe (no secrets)."""


class IncorrectPasswordError(StatementParseError):
    """Raised specifically when PDF decryption fails due to a wrong password."""


class StatementParser(ABC):
    """One implementation per bank. bank_code must match `banks.code` in the DB."""

    bank_code: str

    @abstractmethod
    def identify(self, pdf_text_sample: str, sender_email: str, subject: str) -> bool:
        """Return True if this parser can handle the given email/PDF."""

    @abstractmethod
    def extract_statement_metadata(self, pdf_text: str) -> ExtractedStatement:
        """Extract statement-level fields (dates, totals, fees) from full PDF text."""

    @abstractmethod
    def extract_transactions(self, pdf_text: str) -> list[ExtractedTransaction]:
        """Extract the individual transaction line items."""

    @abstractmethod
    def extract_charges(self, pdf_text: str) -> list[ExtractedCharge]:
        """Extract named fee/charge line items (interest, GST, late fee, etc.)."""

    def normalize_merchant(self, raw_description: str) -> str:
        """
        Default merchant normalization: strip common noise tokens. Bank parsers may
        override this for bank-specific description formats, but should call
        super().normalize_merchant() first where practical to keep behavior consistent.
        """
        import re

        text = raw_description.strip()
        text = re.sub(r"\*[A-Z0-9]+$", "", text)  # trailing "*ORDER12345" style suffixes
        text = re.sub(r"\s{2,}", " ", text)
        text = re.sub(r"\b\d{6,}\b", "", text)  # long reference numbers
        return text.strip().title()

    def validate(self, statement: ExtractedStatement) -> ReconciliationResult:
        """
        Default reconciliation: opening balance + purchases + cash advances + fees
        - payments = closing balance. Bank parsers may override this formula if
        their statement layout differs, but must never silently skip validation.
        """
        from decimal import Decimal

        if statement.previous_balance is None or statement.closing_balance is None:
            return ReconciliationResult(
                ok=False,
                expected_total=Decimal(0),
                actual_total=Decimal(0),
                difference=Decimal(0),
                explanation="Insufficient data to reconcile (missing previous_balance or closing_balance).",
            )

        charges_total = sum((c.amount for c in statement.charges), Decimal(0))
        purchases = statement.purchases or Decimal(0)
        cash_advances = statement.cash_advances or Decimal(0)
        payments = statement.payments_received or Decimal(0)

        expected_closing = (
            statement.previous_balance + purchases + cash_advances + charges_total - payments
        )
        difference = (expected_closing - statement.closing_balance).copy_abs()
        ok = difference <= Decimal("1.00")  # allow a rupee of rounding slack

        explanation = (
            "Reconciled within tolerance."
            if ok
            else (
                f"Computed closing balance {expected_closing} does not match statement "
                f"closing balance {statement.closing_balance}. Difference: {difference}."
            )
        )

        return ReconciliationResult(
            ok=ok,
            expected_total=expected_closing,
            actual_total=statement.closing_balance,
            difference=difference,
            explanation=explanation,
        )
