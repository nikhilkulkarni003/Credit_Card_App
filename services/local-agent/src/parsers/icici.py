"""
ICICI Bank (Amazon Pay ICICI) credit card e-statement parser.

Calibrated against a REAL Amazon Pay ICICI e-statement (2026-08-20, via
`debug-extract` — only the structural layout was used, statement content
never left the local machine). Key quirks of this statement's text extraction:

  - The rupee symbol extracts as a literal backtick "`" (a different font
    artifact than HDFC's "C").
  - "Total Amount due" / "Minimum Amount due" LABELS appear together near the
    top of the STATEMENT SUMMARY box, but their two VALUES print much further
    down, separated by an unrelated EARNINGS block — and in this statement
    the value order came out *reversed* relative to the label order (i.e. you
    cannot assume "first value after the labels = Total Amount Due"). Rather
    than guess which is which, we use the one fact that's always true by RBI
    convention: Minimum Amount Due <= Total Amount Due. So we take the LARGER
    of the two candidate amounts as the total and the SMALLER as the minimum.
    This is a real constraint, not an assumption about magnitude of a
    specific statement — but if a future statement ever prints MAD == TAD
    (fully unpaid single small purchase) this degrades gracefully to the
    correct answer anyway.
  - "Previous Balance / Purchases / Cash Advances / Payments" is a clean,
    reliably-ordered label-block-then-value-block (CREDIT SUMMARY section) —
    used directly, and also cross-checked against the max/min-derived total via
    the standard StatementParser.validate() reconciliation.
  - Transactions are single-line descriptions (unlike HDFC's wrapped ones):
    DATE, then a serial number line, description line, optional 2-letter
    country-code line ("IN"), reward-points line, then the amount — with no
    currency symbol printed in the transaction table itself.

As with hdfc.py: this is calibrated against ONE statement. Re-run
`debug-extract` and adjust if a different ICICI card product or a statement
with non-zero fees/interest reveals a layout this doesn't handle.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from src.models.statement import ExtractedCharge, ExtractedStatement, ExtractedTransaction
from src.parsers.base import StatementParser

_AMOUNT_RE = r"`\s?([\d,]+\.\d{1,2})"
_CARD_NO_RE = re.compile(r"\b(\d{4})X{4,8}(\d{4})\b")

_MONTH_DATE_RE = r"[A-Za-z]+\s+\d{1,2},\s*\d{4}"
_STATEMENT_PERIOD_RE = re.compile(
    rf"Statement period\s*:\s*({_MONTH_DATE_RE})\s*to\s*({_MONTH_DATE_RE})", re.IGNORECASE
)
_SPENDS_OVERVIEW_DATES_RE = re.compile(
    rf"SPENDS OVERVIEW\s*\n\s*({_MONTH_DATE_RE})\s*\n\s*({_MONTH_DATE_RE})", re.IGNORECASE
)

_DUE_AMOUNTS_ANCHOR_RE = re.compile(r"Total Amount due.*?Minimum Amount due", re.IGNORECASE | re.DOTALL)
_CREDIT_SUMMARY_ANCHOR_RE = re.compile(
    r"Previous Balance.*?Payments\s*/\s*Credits", re.IGNORECASE | re.DOTALL
)

# Single-line transaction row: date, serial number, description, optional
# 2-letter country code, reward points, amount (no currency symbol here).
_TXN_RE = re.compile(
    r"(\d{2}/\d{2}/\d{4})\s*\n\d+\s*\n(.+?)\s*\n(?:[A-Z]{2}\s*\n)?\d+\s*\n([\d,]+\.\d{2})\b"
)


def _parse_amount(raw: str) -> Decimal:
    try:
        return Decimal(raw.replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(f"Could not parse amount from {raw!r}") from exc


def _parse_slash_date(raw: str) -> date:
    return datetime.strptime(raw, "%d/%m/%Y").date()


def _parse_month_date(raw: str) -> date:
    cleaned = re.sub(r",", "", raw).strip()
    return datetime.strptime(cleaned, "%B %d %Y").date()


def _extract_due_amounts(text: str) -> tuple[Decimal | None, Decimal | None]:
    anchor = _DUE_AMOUNTS_ANCHOR_RE.search(text)
    if not anchor:
        return None, None
    tail = text[anchor.end() : anchor.end() + 600]
    amounts = [_parse_amount(a) for a in re.findall(_AMOUNT_RE, tail)[:2]]
    if len(amounts) < 2:
        return None, None
    return max(amounts), min(amounts)  # (total_amount_due, minimum_amount_due)


def _extract_credit_summary(text: str) -> list[Decimal] | None:
    """Returns [previous_balance, purchases, cash_advances, payments_received] or None."""
    anchor = _CREDIT_SUMMARY_ANCHOR_RE.search(text)
    if not anchor:
        return None
    tail = text[anchor.end() : anchor.end() + 300]
    amounts = re.findall(_AMOUNT_RE, tail)
    if len(amounts) < 4:
        return None
    return [_parse_amount(a) for a in amounts[:4]]


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

        period_match = _STATEMENT_PERIOD_RE.search(pdf_text)
        period_start = _parse_month_date(period_match.group(1)) if period_match else None
        period_end = _parse_month_date(period_match.group(2)) if period_match else None

        total_amount_due, minimum_amount_due = _extract_due_amounts(pdf_text)

        summary = _extract_credit_summary(pdf_text)
        previous_balance = purchases = cash_advances = payments_received = None
        if summary:
            previous_balance, purchases, cash_advances, payments_received = summary

        due_date = None
        spends_dates_match = _SPENDS_OVERVIEW_DATES_RE.search(pdf_text)
        if spends_dates_match:
            parsed_dates = sorted(_parse_month_date(g) for g in spends_dates_match.groups())
            due_date = parsed_dates[-1]  # payment due date is always after the statement date

        found_fields = [total_amount_due, minimum_amount_due, previous_balance, purchases, period_end, card_match]
        confidence = "high" if sum(f is not None for f in found_fields) >= 5 else "medium" if any(found_fields) else "low"

        return ExtractedStatement(
            bank_code=self.bank_code,
            card_last_four=card_last_four,
            statement_date=period_end,
            statement_period_start=period_start,
            statement_period_end=period_end,
            due_date=due_date,
            total_amount_due=total_amount_due,
            minimum_amount_due=minimum_amount_due,
            previous_balance=previous_balance,
            payments_received=payments_received,
            purchases=purchases,
            cash_advances=cash_advances,
            closing_balance=total_amount_due,  # ICICI doesn't print a separate "closing balance" label
            transactions=self.extract_transactions(pdf_text),
            charges=self.extract_charges(pdf_text),
            extraction_confidence=confidence,
        )

    def extract_transactions(self, pdf_text: str) -> list[ExtractedTransaction]:
        transactions: list[ExtractedTransaction] = []
        for match in _TXN_RE.finditer(pdf_text):
            date_str, description, amount_str = match.groups()
            transactions.append(
                ExtractedTransaction(
                    transaction_date=_parse_slash_date(date_str),
                    merchant_name=self.normalize_merchant(description),
                    original_description=description.strip(),
                    amount=_parse_amount(amount_str),
                    transaction_type="purchase",
                )
            )
        return transactions

    def extract_charges(self, pdf_text: str) -> list[ExtractedCharge]:
        # Not observed on the calibration statement (no interest/GST/fees that
        # cycle) — no confirmed pattern to extract yet rather than a guess.
        return []
