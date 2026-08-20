from src.parsers.icici import IciciStatementParser


def test_identify_matches_on_sender():
    parser = IciciStatementParser()
    assert parser.identify("", sender_email="credit_card@icici.bank.in", subject="Your Statement") is True


def test_identify_matches_on_subject():
    parser = IciciStatementParser()
    assert parser.identify("", sender_email="noreply@example.com", subject="ICICI Bank Credit Card Statement") is True


def test_identify_rejects_unrelated():
    parser = IciciStatementParser()
    assert parser.identify("", sender_email="noreply@amazon.in", subject="Your order shipped") is False


def test_extract_statement_metadata_returns_low_confidence_on_empty_text():
    # Honest behavior check: with no calibrated patterns matching, fields
    # should come back None/low-confidence rather than a guessed value.
    parser = IciciStatementParser()
    statement = parser.extract_statement_metadata("some unrelated text with no recognizable fields")

    assert statement.total_amount_due is None
    assert statement.minimum_amount_due is None
    assert statement.extraction_confidence == "low"
    assert statement.transactions == []
