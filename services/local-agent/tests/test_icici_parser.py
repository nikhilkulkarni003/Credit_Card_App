from decimal import Decimal
from pathlib import Path

from src.parsers.icici import IciciStatementParser

FIXTURE = (
    Path(__file__).resolve().parents[2].parent / "tests" / "fixtures" / "icici_synthetic_statement.txt"
)


def load_fixture_text() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_identify_matches_on_sender():
    parser = IciciStatementParser()
    assert parser.identify("", sender_email="credit_card@icici.bank.in", subject="Your Statement") is True


def test_identify_matches_on_subject():
    parser = IciciStatementParser()
    assert parser.identify("", sender_email="noreply@example.com", subject="ICICI Bank Credit Card Statement") is True


def test_identify_rejects_unrelated():
    parser = IciciStatementParser()
    assert parser.identify("", sender_email="noreply@amazon.in", subject="Your order shipped") is False


def test_extract_statement_metadata():
    parser = IciciStatementParser()
    statement = parser.extract_statement_metadata(load_fixture_text())

    assert statement.card_last_four == "1234"
    # Values print in reversed order relative to their labels in the real
    # layout — verifies the max()=total / min()=minimum heuristic works.
    assert statement.total_amount_due == Decimal("3824.59")
    assert statement.minimum_amount_due == Decimal("192.00")
    assert statement.previous_balance == Decimal("0.00")
    assert statement.purchases == Decimal("3824.59")
    assert statement.cash_advances == Decimal("0.00")
    assert statement.payments_received == Decimal("0.00")
    assert statement.closing_balance == Decimal("3824.59")
    assert str(statement.statement_period_end) == "2026-07-28"
    assert str(statement.due_date) == "2026-08-15"
    assert statement.extraction_confidence == "high"


def test_extract_transactions():
    parser = IciciStatementParser()
    transactions = parser.extract_transactions(load_fixture_text())

    assert len(transactions) == 3
    swiggy = next(t for t in transactions if "SWIGGY" in t.original_description)
    assert swiggy.merchant_name == "Swiggy Bangalore"
    assert swiggy.amount == Decimal("800.00")
    assert swiggy.transaction_type == "purchase"

    total = sum(t.amount for t in transactions)
    assert total == Decimal("3824.59")


def test_reconciliation_passes_on_consistent_fixture():
    parser = IciciStatementParser()
    statement = parser.extract_statement_metadata(load_fixture_text())
    result = parser.validate(statement)

    assert result.ok is True, result.explanation


def test_reconciliation_flags_mismatch():
    parser = IciciStatementParser()
    statement = parser.extract_statement_metadata(load_fixture_text())
    statement.closing_balance = Decimal("99999.00")

    result = parser.validate(statement)

    assert result.ok is False
