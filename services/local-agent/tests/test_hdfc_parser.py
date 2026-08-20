from decimal import Decimal
from pathlib import Path

from src.parsers.hdfc import HdfcStatementParser

FIXTURE = (
    Path(__file__).resolve().parents[2].parent / "tests" / "fixtures" / "hdfc_synthetic_statement.txt"
)


def load_fixture_text() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_identify_matches_hdfc_content():
    parser = HdfcStatementParser()
    text = load_fixture_text()
    assert parser.identify(text, sender_email="statements@hdfcbank.net", subject="Your HDFC Credit Card Statement") is True
    assert parser.identify(text, sender_email="other@bank.com", subject="Random") is True  # content_hit


def test_extract_statement_metadata():
    parser = HdfcStatementParser()
    statement = parser.extract_statement_metadata(load_fixture_text())

    assert statement.card_last_four == "1234"
    assert statement.total_amount_due == Decimal("15315.00")
    assert statement.minimum_amount_due == Decimal("766.00")
    assert statement.previous_balance == Decimal("10000.00")
    assert statement.payments_received == Decimal("10000.00")
    assert statement.purchases == Decimal("15115.00")
    assert statement.interest == Decimal("200.00")
    assert statement.closing_balance == Decimal("15315.00")
    assert str(statement.due_date) == "2026-08-14"
    assert str(statement.statement_period_end) == "2026-07-25"


def test_extract_transactions_count_and_normalization():
    parser = HdfcStatementParser()
    transactions = parser.extract_transactions(load_fixture_text())

    assert len(transactions) == 10
    swiggy = next(t for t in transactions if "SWIGGY" in t.original_description)
    assert swiggy.merchant_name == "Swiggy"
    assert swiggy.amount == Decimal("450.00")
    assert swiggy.transaction_type == "purchase"

    payment = next(t for t in transactions if "BPPY CC PAYMENT" in t.original_description)
    assert payment.amount == Decimal("-10000.00")
    assert payment.transaction_type == "payment"
    # the long alnum reference token and "(Ref# ...)" block must be stripped from the normalized name
    assert "DP216194TUHZ5LCU71L" not in payment.merchant_name
    assert "Ref" not in payment.merchant_name


def test_reconciliation_passes_on_consistent_fixture():
    parser = HdfcStatementParser()
    statement = parser.extract_statement_metadata(load_fixture_text())
    result = parser.validate(statement)

    assert result.ok is True, result.explanation


def test_reconciliation_flags_mismatch():
    parser = HdfcStatementParser()
    statement = parser.extract_statement_metadata(load_fixture_text())
    statement.closing_balance = Decimal("99999.00")  # force a mismatch

    result = parser.validate(statement)

    assert result.ok is False
    assert "does not match" in result.explanation
