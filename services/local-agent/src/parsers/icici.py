"""
ICICI Bank (Amazon Pay ICICI) credit card e-statement parser.

NOT YET CALIBRATED against a real statement — unlike hdfc.py, this has not
been run against real ICICI statement text yet. The regexes below are a
starting guess and will very likely need correction the same way hdfc.py did
(run `debug-extract` on a real ICICI message, inspect the local-only output
file, and fix these patterns to match). Until then, expect extraction_confidence
to come back "low" and most fields to be None rather than wrong — per the
"never silently guess financial data" rule, returning None is the correct
behavior for a pattern that doesn't actually match, not a bug to work around.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from src.models.statement import ExtractedCharge, ExtractedStatement, ExtractedTransaction
from src.parsers.base import StatementParser

_AMOUNT_RE = r"(?:Rs\.?|₹|INR)\s?([\d,]+(?:\.\d{1,2})?)"

_TOTAL_DUE_RE = re.compile(rf"Total\s+Amount\s+Due\s*[:\-]?\s*{_AMOUNT_RE}", re.IGNORECASE)
_MIN_DUE_RE = re.compile(rf"Minimum\s+Amount\s+Due\s*[:\-]?\s*{_AMOUNT_RE}", re.IGNORECASE)
_DUE_DATE_RE = re.compile(r"Due\s+Date\s*[:\-]?\s*(\d{1,2}[/\-]\w+[/\-]\d{2,4})", re.IGNORECASE)
_CARD_NO_RE = re.compile(r"\b(\d{4})X{4,8}(\d{4})\b")

_TXN_RE = re.compile(
    rf"(\d{{2}}/\d{{2}}/\d{{4}})\s+(.+?)\s+{_AMOUNT_RE}\s*(CR)?\s*$",
    re.MULTILINE,
)


def _parse_amount(raw: str) -> Decimal:
    try:
        return Decimal(raw.replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(f"Could not parse amount from {raw!r}") from exc


def _parse_slash_date(raw: str) -> date:
    return datetime.strptime(raw, "%d/%m/%Y").date()


class IciciStatementParser(StatementParser):
    bank_code = "ICICI"

    def identify(self, pdf_text_sample: str, sender_email: str, subject: str) -> bool:
        sender_hit = "icici" in sender_email.lower()
        subject_hit = bool(re.search(r"icici.*(statement|credit card)", subject, re.IGNORECASE))
        content_hit = "icici bank" in pdf_text_sample.lower() and "credit card" in pdf_text_sample.lower()
        return sender_hit or subject_hit or content_hit

    def extract_statement_metadata(self, pdf_text: str) -> ExtractedStatement:
        card_match = _CARD_NO_RE.search(pdf_text)
        card_last_four = card_match.group(2) if card_match else "0000"

        total_due_match = _TOTAL_DUE_RE.search(pdf_text)
        min_due_match = _MIN_DUE_RE.search(pdf_text)
        due_date_match = _DUE_DATE_RE.search(pdf_text)

        total_amount_due = _parse_amount(total_due_match.group(1)) if total_due_match else None
        minimum_amount_due = _parse_amount(min_due_match.group(1)) if min_due_match else None

        found_fields = [total_amount_due, minimum_amount_due, card_match, due_date_match]
        confidence = "medium" if sum(f is not None for f in found_fields) >= 2 else "low"

        return ExtractedStatement(
            bank_code=self.bank_code,
            card_last_four=card_last_four,
            total_amount_due=total_amount_due,
            minimum_amount_due=minimum_amount_due,
            transactions=self.extract_transactions(pdf_text),
            charges=self.extract_charges(pdf_text),
            extraction_confidence=confidence,
        )

    def extract_transactions(self, pdf_text: str) -> list[ExtractedTransaction]:
        transactions: list[ExtractedTransaction] = []
        for match in _TXN_RE.finditer(pdf_text):
            date_str, description, amount_str, cr_marker = match.groups()
            amount = _parse_amount(amount_str)
            is_credit = bool(cr_marker)
            transactions.append(
                ExtractedTransaction(
                    transaction_date=_parse_slash_date(date_str),
                    merchant_name=self.normalize_merchant(description),
                    original_description=description.strip(),
                    amount=-amount if is_credit else amount,
                    transaction_type="payment" if is_credit else "purchase",
                )
            )
        return transactions

    def extract_charges(self, pdf_text: str) -> list[ExtractedCharge]:
        # Not yet calibrated — no charge patterns confirmed against a real statement.
        return []
