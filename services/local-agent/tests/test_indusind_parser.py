from decimal import Decimal
from pathlib import Path

from src.parsers.indusind import IndusindStatementParser

FIXTURE = (
    Path(__file__).resolve().parents[2].parent / "tests" / "fixtures" / "indusind_synthetic_statement.txt"
)


def load_fixture_text() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_identify_matches_on_sender():
    parser = IndusindStatementParser()
    assert parser.identify("", sender_email="creditcard.estatements@indusind.com", subject="Your Statement") is True


def test_identify_matches_on_subject():
    parser = IndusindStatementParser()
    assert parser.identify("", sender_email="noreply@example.com", subject="IndusInd Bank Credit Card statement") is True


def test_identify_rejects_unrelated():
    parser = IndusindStatementParser()
    assert parser.identify("", sender_email="noreply@amazon.in", subject="Your order shipped") is False


def test_extract_statement_metadata():
    parser = IndusindStatementParser()
    statement = parser.extract_statement_metadata(load_fixture_text())

    assert statement.card_last_four == "1234"
    assert statement.previous_balance == Decimal("5000.00")
    assert statement.cash_advances == Decimal("0.00")
    assert statement.purchases == Decimal("618.00")  # interest(100) + gst(18) + emi(500)
    assert statement.payments_received == Decimal("1000.00")
    assert statement.total_amount_due == Decimal("4618.00")  # computed, not printed — see module docstring
    assert statement.minimum_amount_due == Decimal("700.00")  # from the tear-off slip
    assert statement.due_date is None  # not confidently extractable — must not be guessed
    assert str(statement.statement_date) == "2026-08-05"
    assert str(statement.statement_period_start) == "2026-05-16"
    assert str(statement.statement_period_end) == "2026-06-15"
    assert statement.interest == Decimal("100.00")
    assert statement.gst == Decimal("18.00")


def test_extract_transactions_classifies_by_description():
    parser = IndusindStatementParser()
    transactions = parser.extract_transactions(load_fixture_text())

    assert len(transactions) == 4  # "Total" summary lines must be excluded
    payment = next(t for t in transactions if t.transaction_type == "payment")
    assert payment.amount == Decimal("-1000.00")

    finance_charge = next(t for t in transactions if t.transaction_type == "interest")
    assert finance_charge.amount == Decimal("100.00")

    gst = next(t for t in transactions if t.transaction_type == "fee")
    assert gst.amount == Decimal("18.00")

    emi = next(t for t in transactions if t.transaction_type == "other")
    assert emi.amount == Decimal("500.00")


def test_reconciliation_passes_when_purchases_already_includes_charges():
    # This bank's validate() override must NOT add a separate charges_total
    # on top of purchases (purchases already includes interest/GST/EMI here) —
    # otherwise this would double-count and incorrectly fail reconciliation.
    parser = IndusindStatementParser()
    statement = parser.extract_statement_metadata(load_fixture_text())
    result = parser.validate(statement)

    assert result.ok is True, result.explanation


def test_reconciliation_flags_mismatch():
    parser = IndusindStatementParser()
    statement = parser.extract_statement_metadata(load_fixture_text())
    statement.closing_balance = Decimal("99999.00")

    result = parser.validate(statement)

    assert result.ok is False
