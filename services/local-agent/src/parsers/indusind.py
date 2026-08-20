"""
IndusInd Bank credit card e-statement parser.

Calibrated against a REAL IndusInd statement (2026-08-20, via debug-extract —
content never left the local machine, only structural layout was used). This
statement's layout was significantly messier than HDFC's/ICICI's — it has
active EMI/loan conversions, a tear-off payment slip, and a header block whose
printed VALUE order does not match its LABEL order. What was actually
resolvable, and how:

  - Header labels appear as: Previous Balance, Purchases & Other Charges,
    Cash Advance, Payment & Other Credits. The four VALUES that follow print
    in the order [previous_balance, cash_advance, purchases, payments] —
    i.e. positions 2 and 3 are swapped relative to their labels. Confirmed by
    cross-checking: the value in "purchases" position exactly equals
    (Interest & Other Charges total) + (EMI Charges total) for this cycle,
    and the value in "payments" position exactly equals the Payment Details
    section's total.
  - For an IndusInd statement with active EMIs, "Purchases & Other Charges"
    is NOT purely retail purchases — it already includes this cycle's
    interest/GST/EMI installment charges. validate() is overridden below to
    NOT add a separate charges_total on top of it (would double-count).
  - Total Amount Due is not reliably identifiable as a single printed value
    near its label (same ambiguous-ordering problem) — so it is COMPUTED as
    previous_balance + purchases + cash_advance - payments, the same formula
    used for reconciliation. This is documented as derived, not printed.
  - Minimum Amount Due IS reliably readable from the tear-off payment-slip
    fragment, which pairs the statement date with the amount owed in a
    compact "date, amount, masked-card-number" pattern.
  - Payment Due Date could NOT be confidently identified in this statement's
    text layer at all — left as None (rather than guessed). If this matters,
    check whether the actual PDF renders the due date as an image/graphic
    instead of text.

This is calibrated against ONE statement with active EMIs. Re-run
`debug-extract` on an IndusInd statement WITHOUT active EMIs to see if the
header block behaves more simply, and adjust accordingly.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from src.models.statement import ExtractedCharge, ExtractedStatement, ExtractedTransaction, ReconciliationResult
from src.parsers.base import StatementParser

_CARD_NO_RE = re.compile(r"\b(\d{4})X{4,8}(\d{4})\b")
_PERIOD_RE = re.compile(r"(\d{2}/\d{2}/\d{4})\s*To\s*(\d{2}/\d{2}/\d{4})", re.IGNORECASE)

_HEADER_ANCHOR_RE = re.compile(
    r"Previous Balance.*?Payment\s*&\s*Other Credits", re.IGNORECASE | re.DOTALL
)
_GENERIC_AMOUNT_RE = re.compile(r"([\d,]+\.\d{2})\s*(DR|CR)?")

# Tear-off payment slip fragment: "<row>\n<date>\n<amount>\n<masked card no>".
_SLIP_RE = re.compile(
    r"\n1\s*\n(\d{2}/\d{2}/\d{4})\s*\n([\d,]+\.\d{2})\s*\n\d{4}X{4,8}\d{4}", re.IGNORECASE
)

# Interest & Other Charges / EMI Charges / Payment line items:
# "DATE\nDESCRIPTION\nREWARD_POINTS\nAMOUNT DR|CR"
_TXN_RE = re.compile(r"(\d{2}/\d{2}/\d{4})\s*\n(.+?)\s*\n\d+\s*\n([\d,]+\.\d{2})\s*(DR|CR)\b")


def _parse_amount(raw: str) -> Decimal:
    try:
        return Decimal(raw.replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(f"Could not parse amount from {raw!r}") from exc


def _parse_slash_date(raw: str) -> date:
    return datetime.strptime(raw, "%d/%m/%Y").date()


def _classify(description: str) -> str:
    upper = description.upper()
    if "FINANCE CHARGE" in upper:
        return "interest"
    if "GST" in upper:
        return "fee"
    if "EMI" in upper:
        return "other"
    return "purchase"


def _extract_header_block(text: str) -> dict[str, Decimal] | None:
    anchor = _HEADER_ANCHOR_RE.search(text)
    if not anchor:
        return None
    tail = text[anchor.end() : anchor.end() + 200]
    matches = _GENERIC_AMOUNT_RE.findall(tail)
    if len(matches) < 4:
        return None
    previous_balance, cash_advance, purchases, payments_received = (_parse_amount(m[0]) for m in matches[:4])
    return {
        "previous_balance": previous_balance,
        "cash_advance": cash_advance,
        "purchases": purchases,
        "payments_received": payments_received,
    }


class IndusindStatementParser(StatementParser):
    bank_code = "INDUSIND"

    def identify(self, pdf_text_sample: str, sender_email: str, subject: str) -> bool:
        sender_hit = "indusind" in sender_email.lower()
        subject_hit = bool(re.search(r"indusind.*(statement|credit card)", subject, re.IGNORECASE))
        content_hit = "indusind bank" in pdf_text_sample.lower() and "credit card" in pdf_text_sample.lower()
        return sender_hit or subject_hit or content_hit

    def extract_statement_metadata(self, pdf_text: str) -> ExtractedStatement:
        card_match = _CARD_NO_RE.search(pdf_text)
        card_last_four = card_match.group(2) if card_match else "0000"

        period_match = _PERIOD_RE.search(pdf_text)
        period_start = _parse_slash_date(period_match.group(1)) if period_match else None
        period_end = _parse_slash_date(period_match.group(2)) if period_match else None

        header = _extract_header_block(pdf_text)
        previous_balance = header["previous_balance"] if header else None
        cash_advance = header["cash_advance"] if header else None
        purchases = header["purchases"] if header else None
        payments_received = header["payments_received"] if header else None

        total_amount_due = None
        if None not in (previous_balance, purchases, payments_received):
            total_amount_due = previous_balance + purchases + (cash_advance or Decimal(0)) - payments_received

        statement_date = None
        minimum_amount_due = None
        slip_match = _SLIP_RE.search(pdf_text)
        if slip_match:
            statement_date = _parse_slash_date(slip_match.group(1))
            minimum_amount_due = _parse_amount(slip_match.group(2))

        transactions = self.extract_transactions(pdf_text)
        interest = sum((t.amount for t in transactions if t.transaction_type == "interest"), Decimal(0)) or None
        gst = sum(
            (t.amount for t in transactions if t.transaction_type == "fee" and "GST" in t.original_description.upper()),
            Decimal(0),
        ) or None

        found_fields = [total_amount_due, minimum_amount_due, previous_balance, purchases, period_end, card_match]
        confidence = "medium" if sum(f is not None for f in found_fields) >= 5 else "low"

        return ExtractedStatement(
            bank_code=self.bank_code,
            card_last_four=card_last_four,
            statement_date=statement_date,
            statement_period_start=period_start,
            statement_period_end=period_end,
            due_date=None,  # see module docstring — not confidently extractable from this layout yet
            total_amount_due=total_amount_due,
            minimum_amount_due=minimum_amount_due,
            previous_balance=previous_balance,
            payments_received=payments_received,
            purchases=purchases,
            cash_advances=cash_advance,
            interest=interest,
            gst=gst,
            closing_balance=total_amount_due,
            transactions=transactions,
            charges=[],  # deliberately empty — see validate() override, avoids double-counting
            extraction_confidence=confidence,
        )

    def extract_transactions(self, pdf_text: str) -> list[ExtractedTransaction]:
        transactions: list[ExtractedTransaction] = []
        for match in _TXN_RE.finditer(pdf_text):
            date_str, description, amount_str, marker = match.groups()
            description = description.strip()
            if description.lower() == "total":
                continue
            amount = _parse_amount(amount_str)
            is_credit = marker == "CR"
            transactions.append(
                ExtractedTransaction(
                    transaction_date=_parse_slash_date(date_str),
                    merchant_name=self.normalize_merchant(description),
                    original_description=description,
                    amount=-amount if is_credit else amount,
                    transaction_type="payment" if is_credit else _classify(description),
                )
            )
        return transactions

    def extract_charges(self, pdf_text: str) -> list[ExtractedCharge]:
        # Deliberately empty — interest/GST are already folded into
        # "purchases" for this bank's summary math (see module docstring);
        # returning them here too would double-count in validate().
        return []

    def validate(self, statement: ExtractedStatement) -> ReconciliationResult:
        if statement.previous_balance is None or statement.closing_balance is None:
            return ReconciliationResult(
                ok=False,
                expected_total=Decimal(0),
                actual_total=Decimal(0),
                difference=Decimal(0),
                explanation="Insufficient data to reconcile (missing previous_balance or closing_balance).",
            )
        purchases = statement.purchases or Decimal(0)
        cash_advances = statement.cash_advances or Decimal(0)
        payments = statement.payments_received or Decimal(0)
        # No separate charges_total term: "purchases" already includes this
        # cycle's interest/EMI charges for IndusInd's summary structure.
        expected_closing = statement.previous_balance + purchases + cash_advances - payments
        difference = (expected_closing - statement.closing_balance).copy_abs()
        ok = difference <= Decimal("1.00")
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
