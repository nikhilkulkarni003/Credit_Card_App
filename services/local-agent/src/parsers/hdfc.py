"""
Reference bank parser: HDFC Bank credit card e-statement.

Calibrated against a REAL HDFC "Business MoneyBack" e-statement (2026-08-20,
via the local agent's `debug-extract` command — raw statement content was
never sent off-machine; only the structural layout was used to write these
patterns). Key quirks of PyMuPDF's text extraction for this statement:

  - The rupee symbol (₹) decodes as the literal letter "C" (font-encoding
    artifact), so amounts appear as "C21,129.24", "C2,69,000", etc.
  - Summary fields are laid out as LABEL, then VALUE on the *next line* —
    not "Label: value" on one line as originally assumed.
  - The "Previous Statement Dues / Payments Received / Purchases / Finance
    Charges" block is a label GROUP followed by a value GROUP (4 labels,
    then their 4 values), not per-line pairs.
  - Transaction rows span multiple lines: a "DD/MM/YYYY| HH:MM" line, then a
    (possibly wrapped) description, then a "+ C amount" (credit) or
    "C amount" (debit) line.

This is still only calibrated against ONE statement from ONE card product.
If extraction/reconciliation looks wrong on a different HDFC card variant or
statement month, re-run `debug-extract` on that statement and adjust the
patterns below — do not assume this covers every HDFC layout.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from src.models.statement import ExtractedCharge, ExtractedStatement, ExtractedTransaction
from src.parsers.base import StatementParser

# The rupee glyph extracts as "C" in this statement's font encoding. Allow an
# optional space after it and either 2-decimal or bare (credit-limit-style) amounts.
_AMOUNT_RE = r"C\s?([\d,]+(?:\.\d{1,2})?)"

_CARD_NO_RE = re.compile(r"\b(\d{6})X{4,8}(\d{4})\b")
_MONTH_DATE_RE = r"\d{1,2}\s+[A-Za-z]{3},?\s+\d{4}"
_BILLING_PERIOD_RE = re.compile(rf"({_MONTH_DATE_RE})\s*-\s*({_MONTH_DATE_RE})")

_TOTAL_DUE_RE = re.compile(rf"TOTAL AMOUNT DUE\s*\n\s*{_AMOUNT_RE}", re.IGNORECASE)
_MIN_DUE_RE = re.compile(rf"MINIMUM DUE\s*\n\s*{_AMOUNT_RE}", re.IGNORECASE)
_DUE_DATE_RE = re.compile(rf"DUE DATE\s*\n\s*(Nil|{_MONTH_DATE_RE})", re.IGNORECASE)

# "PREVIOUS STATEMENT DUES / PAYMENTS/CREDITS RECEIVED / PURCHASES/DEBIT
# (Current Billing Cycle) / FINANCE CHARGES" label block, followed by their
# 4 values in the same order.
_DUES_BLOCK_ANCHOR_RE = re.compile(
    r"PREVIOUS STATEMENT DUES.*?FINANCE CHARGES", re.IGNORECASE | re.DOTALL
)

# Optional standalone charge lines (not observed on the calibration statement,
# since it had no GST/late/annual fee that cycle — kept as best-effort so a
# statement that DOES carry these isn't silently dropped; verify against a
# real example with non-zero values before trusting these blindly).
_CHARGE_PATTERNS: dict[str, str] = {
    "GST": rf"\b(?:IGST|Total GST|GST)\b\s*[:\-]?\s*{_AMOUNT_RE}",
    "Late Payment Fee": rf"Late\s+Payment\s+(?:Fee|Charges?)\s*[:\-]?\s*{_AMOUNT_RE}",
    "Annual Fee": rf"(?:Annual|Membership)\s+Fee\s*[:\-]?\s*{_AMOUNT_RE}",
}

# Transaction row: "DD/MM/YYYY| HH:MM", then a (possibly multi-line, wrapped)
# description, then an amount line optionally prefixed with "+" for a credit.
_TXN_RE = re.compile(
    r"(\d{2}/\d{2}/\d{4})\|\s*\d{2}:\d{2}\s*\n(.*?)\n\s*(\+)?\s*" + _AMOUNT_RE,
    re.DOTALL,
)

# Description-cleanup: drop "(Ref# ...)" blocks and long mixed letter+digit
# reference tokens (e.g. "DP216194TUHZ5LCU71L") that carry no merchant signal.
_REF_BLOCK_RE = re.compile(r"\(Ref#.*?\)", re.DOTALL)
_REF_TOKEN_RE = re.compile(r"\b(?=[A-Za-z0-9]{8,}\b)(?=[A-Za-z0-9]*\d)(?=[A-Za-z0-9]*[A-Za-z])[A-Za-z0-9]{8,}\b")


def _parse_amount(raw: str) -> Decimal:
    try:
        return Decimal(raw.replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(f"Could not parse amount from {raw!r}") from exc


def _parse_slash_date(raw: str) -> date:
    return datetime.strptime(raw, "%d/%m/%Y").date()


def _parse_month_date(raw: str) -> date | None:
    if raw.strip().lower() == "nil":
        return None
    cleaned = raw.replace(",", "")
    return datetime.strptime(cleaned, "%d %b %Y").date()


def _extract_dues_block(text: str) -> list[Decimal] | None:
    """Returns [previous_dues, payments_received, purchases, finance_charges] or None."""
    anchor = _DUES_BLOCK_ANCHOR_RE.search(text)
    if not anchor:
        return None
    tail = text[anchor.end() : anchor.end() + 400]
    amounts = re.findall(_AMOUNT_RE, tail)
    if len(amounts) < 4:
        return None
    return [_parse_amount(a) for a in amounts[:4]]


class HdfcStatementParser(StatementParser):
    bank_code = "HDFC"

    def identify(self, pdf_text_sample: str, sender_email: str, subject: str) -> bool:
        sender_hit = "hdfcbank" in sender_email.lower()
        subject_hit = bool(re.search(r"hdfc.*(statement|credit card)", subject, re.IGNORECASE))
        content_hit = "hdfc bank" in pdf_text_sample.lower() and "credit card" in pdf_text_sample.lower()
        return sender_hit or subject_hit or content_hit

    def normalize_merchant(self, raw_description: str) -> str:
        text = _REF_BLOCK_RE.sub("", raw_description)
        # Run the base cleanup (trailing "*SUFFIX", long digit-only tokens,
        # title-casing) BEFORE stripping mixed alnum reference tokens —
        # otherwise removing "ORDER998877" first leaves a dangling "*" that
        # the base's "\*[A-Z0-9]+$" pattern no longer matches.
        text = super().normalize_merchant(text)
        text = _REF_TOKEN_RE.sub("", text)
        return re.sub(r"\s{2,}", " ", text).strip()

    def extract_statement_metadata(self, pdf_text: str) -> ExtractedStatement:
        card_match = _CARD_NO_RE.search(pdf_text)
        card_last_four = card_match.group(2) if card_match else "0000"

        period_match = _BILLING_PERIOD_RE.search(pdf_text)
        period_start = _parse_month_date(period_match.group(1)) if period_match else None
        period_end = _parse_month_date(period_match.group(2)) if period_match else None

        total_due_match = _TOTAL_DUE_RE.search(pdf_text)
        min_due_match = _MIN_DUE_RE.search(pdf_text)
        due_date_match = _DUE_DATE_RE.search(pdf_text)

        total_amount_due = _parse_amount(total_due_match.group(1)) if total_due_match else None
        minimum_amount_due = _parse_amount(min_due_match.group(1)) if min_due_match else None
        due_date = _parse_month_date(due_date_match.group(1)) if due_date_match else None

        dues = _extract_dues_block(pdf_text)
        previous_balance = payments_received = purchases = interest = None
        if dues:
            previous_balance, payments_received, purchases, interest = dues

        charges = self.extract_charges(pdf_text)
        charges_by_label = {c.label: c.amount for c in charges}

        found_fields = [
            total_amount_due,
            minimum_amount_due,
            previous_balance,
            payments_received,
            purchases,
            period_end,
            card_match,
        ]
        confidence = "high" if sum(f is not None for f in found_fields) >= 6 else "medium" if any(found_fields) else "low"

        return ExtractedStatement(
            bank_code=self.bank_code,
            card_last_four=card_last_four,
            statement_date=period_end,  # this statement has no separately-labeled date distinct from billing-period end
            statement_period_start=period_start,
            statement_period_end=period_end,
            due_date=due_date,
            total_amount_due=total_amount_due,
            minimum_amount_due=minimum_amount_due,
            previous_balance=previous_balance,
            payments_received=payments_received,
            purchases=purchases,
            interest=interest if interest else charges_by_label.get("Interest"),
            gst=charges_by_label.get("GST"),
            late_payment_fee=charges_by_label.get("Late Payment Fee"),
            annual_fee=charges_by_label.get("Annual Fee"),
            closing_balance=total_amount_due,  # HDFC doesn't print a separate "closing balance" label
            transactions=self.extract_transactions(pdf_text),
            charges=charges,
            extraction_confidence=confidence,
        )

    def extract_transactions(self, pdf_text: str) -> list[ExtractedTransaction]:
        transactions: list[ExtractedTransaction] = []
        for match in _TXN_RE.finditer(pdf_text):
            date_str, description, sign, amount_str = match.groups()
            # Strip the standalone "l" reward-icon artifact line — PyMuPDF's
            # column-extraction order for the REWARDS column isn't stable
            # (it can land before or after the amount line), so it sometimes
            # gets swept into the description capture group.
            description = re.sub(r"^\s*l\s*$", "", description, flags=re.MULTILINE | re.IGNORECASE).strip()
            amount = _parse_amount(amount_str)
            is_credit = sign == "+"
            transactions.append(
                ExtractedTransaction(
                    transaction_date=_parse_slash_date(date_str),
                    merchant_name=self.normalize_merchant(description),
                    original_description=" ".join(description.split()),
                    amount=-amount if is_credit else amount,
                    transaction_type="payment" if is_credit else "purchase",
                )
            )
        return transactions

    def extract_charges(self, pdf_text: str) -> list[ExtractedCharge]:
        charges: list[ExtractedCharge] = []
        dues = _extract_dues_block(pdf_text)
        if dues and dues[3]:
            charges.append(ExtractedCharge(label="Interest", amount=dues[3]))
        for label, pattern in _CHARGE_PATTERNS.items():
            match = re.search(pattern, pdf_text, re.IGNORECASE)
            if match:
                charges.append(ExtractedCharge(label=label, amount=_parse_amount(match.group(1))))
        return charges
