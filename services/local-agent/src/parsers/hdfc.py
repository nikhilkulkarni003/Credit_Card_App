"""
Reference bank parser: HDFC Bank credit card e-statement.

This is the FIRST and reference implementation of StatementParser (per the phased
build plan: get one bank working reliably before adding others).

IMPORTANT — calibration note: this parser was built from the general, publicly
documented structure of HDFC credit card e-statements (labelled summary block,
then a "Date / Transaction Description / Amount" table). It has NOT been
calibrated against a real HDFC PDF in this environment (none was provided, and
real statements must never be committed to the repo). Before relying on it:
run it against one real statement via the local agent, compare the extracted
totals to the printed summary, and adjust the regexes in `_LINE_PATTERNS` /
`_SUMMARY_PATTERNS` below if extraction or reconciliation fails. The
`validate()` reconciliation check (inherited from StatementParser) exists
specifically to catch exactly this kind of drift instead of silently trusting
a bad extraction.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from src.models.statement import ExtractedCharge, ExtractedStatement, ExtractedTransaction
from src.parsers.base import StatementParser

_AMOUNT_RE = r"[\d,]+\.\d{2}"

_SUMMARY_PATTERNS: dict[str, str] = {
    "total_amount_due": rf"Total\s+(?:Amount\s+)?Due\s*[:\-]?\s*(?:Rs\.?|₹)?\s*({_AMOUNT_RE})",
    "minimum_amount_due": rf"Minimum\s+(?:Amount\s+)?Due\s*[:\-]?\s*(?:Rs\.?|₹)?\s*({_AMOUNT_RE})",
    "previous_balance": rf"Previous\s+Balance\s*[:\-]?\s*(?:Rs\.?|₹)?\s*({_AMOUNT_RE})",
    "payments_received": rf"Payment(?:s)?(?:/Credits)?\s+(?:Received)?\s*[:\-]?\s*(?:Rs\.?|₹)?\s*({_AMOUNT_RE})",
    "purchases": rf"Purchase(?:s)?(?:/Debits)?\s*[:\-]?\s*(?:Rs\.?|₹)?\s*({_AMOUNT_RE})",
    "cash_advances": rf"Cash\s+Advance(?:s)?\s*[:\-]?\s*(?:Rs\.?|₹)?\s*({_AMOUNT_RE})",
    "closing_balance": rf"Closing\s+Balance\s*[:\-]?\s*(?:Rs\.?|₹)?\s*({_AMOUNT_RE})",
}

_CHARGE_PATTERNS: dict[str, str] = {
    "Interest": rf"Finance\s+Charge(?:s)?\s*[:\-]?\s*(?:Rs\.?|₹)?\s*({_AMOUNT_RE})",
    "GST": rf"(?:IGST|GST|CGST\s*\+\s*SGST)\s*[:\-]?\s*(?:Rs\.?|₹)?\s*({_AMOUNT_RE})",
    "Late Payment Fee": rf"Late\s+Payment\s+(?:Fee|Charges?)\s*[:\-]?\s*(?:Rs\.?|₹)?\s*({_AMOUNT_RE})",
    "Annual Fee": rf"(?:Annual|Membership)\s+Fee\s*[:\-]?\s*(?:Rs\.?|₹)?\s*({_AMOUNT_RE})",
}

_DUE_DATE_RE = r"(?:Payment\s+Due\s+Date|Due\s+Date)\s*[:\-]?\s*(\d{2}[/\-]\d{2}[/\-]\d{4})"
_STMT_DATE_RE = r"Statement\s+Date\s*[:\-]?\s*(\d{2}[/\-]\d{2}[/\-]\d{4})"
_CARD_RE = r"(?:Card\s+No\.?|Card\s+Number).*?(\d{4})\s*$"

# Transaction line: "DD/MM/YYYY  DESCRIPTION TEXT  1,234.56 [Cr]"
_TXN_LINE_RE = re.compile(
    rf"^(\d{{2}}/\d{{2}}/\d{{4}})\s+(.+?)\s+({_AMOUNT_RE})\s*(Cr)?\s*$"
)


def _parse_amount(raw: str) -> Decimal:
    try:
        return Decimal(raw.replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(f"Could not parse amount from {raw!r}") from exc


def _parse_date(raw: str) -> "datetime.date":
    normalized = raw.replace("-", "/")
    return datetime.strptime(normalized, "%d/%m/%Y").date()


class HdfcStatementParser(StatementParser):
    bank_code = "HDFC"

    def identify(self, pdf_text_sample: str, sender_email: str, subject: str) -> bool:
        sender_hit = "hdfcbank" in sender_email.lower()
        subject_hit = bool(re.search(r"hdfc.*(statement|credit card)", subject, re.IGNORECASE))
        content_hit = "hdfc bank" in pdf_text_sample.lower() and "statement" in pdf_text_sample.lower()
        return sender_hit or subject_hit or content_hit

    def extract_statement_metadata(self, pdf_text: str) -> ExtractedStatement:
        card_match = re.search(_CARD_RE, pdf_text, re.MULTILINE)
        card_last_four = card_match.group(1) if card_match else "0000"

        stmt_date_match = re.search(_STMT_DATE_RE, pdf_text)
        due_date_match = re.search(_DUE_DATE_RE, pdf_text)

        fields: dict[str, Decimal] = {}
        for field, pattern in _SUMMARY_PATTERNS.items():
            match = re.search(pattern, pdf_text, re.IGNORECASE)
            if match:
                fields[field] = _parse_amount(match.group(1))

        charges = self.extract_charges(pdf_text)
        charges_by_label = {c.label: c.amount for c in charges}

        return ExtractedStatement(
            bank_code=self.bank_code,
            card_last_four=card_last_four,
            statement_date=_parse_date(stmt_date_match.group(1)) if stmt_date_match else None,
            due_date=_parse_date(due_date_match.group(1)) if due_date_match else None,
            total_amount_due=fields.get("total_amount_due"),
            minimum_amount_due=fields.get("minimum_amount_due"),
            previous_balance=fields.get("previous_balance"),
            payments_received=fields.get("payments_received"),
            purchases=fields.get("purchases"),
            cash_advances=fields.get("cash_advances"),
            interest=charges_by_label.get("Interest"),
            gst=charges_by_label.get("GST"),
            late_payment_fee=charges_by_label.get("Late Payment Fee"),
            annual_fee=charges_by_label.get("Annual Fee"),
            closing_balance=fields.get("closing_balance"),
            transactions=self.extract_transactions(pdf_text),
            charges=charges,
            extraction_confidence="high" if len(fields) >= 5 else "medium" if fields else "low",
        )

    def extract_transactions(self, pdf_text: str) -> list[ExtractedTransaction]:
        transactions: list[ExtractedTransaction] = []
        for line in pdf_text.splitlines():
            match = _TXN_LINE_RE.match(line.strip())
            if not match:
                continue
            date_str, description, amount_str, cr_marker = match.groups()
            amount = _parse_amount(amount_str)
            is_credit = bool(cr_marker)
            txn_type = "payment" if is_credit else "purchase"
            transactions.append(
                ExtractedTransaction(
                    transaction_date=_parse_date(date_str),
                    merchant_name=self.normalize_merchant(description),
                    original_description=description.strip(),
                    amount=-amount if is_credit else amount,
                    transaction_type=txn_type,
                )
            )
        return transactions

    def extract_charges(self, pdf_text: str) -> list[ExtractedCharge]:
        charges: list[ExtractedCharge] = []
        for label, pattern in _CHARGE_PATTERNS.items():
            match = re.search(pattern, pdf_text, re.IGNORECASE)
            if match:
                charges.append(ExtractedCharge(label=label, amount=_parse_amount(match.group(1))))
        return charges
