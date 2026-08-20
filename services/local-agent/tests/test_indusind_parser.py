from src.parsers.indusind import IndusindStatementParser


def test_identify_matches_on_sender():
    parser = IndusindStatementParser()
    assert parser.identify("", sender_email="creditcard.estatements@indusind.com", subject="Your Statement") is True


def test_identify_matches_on_subject():
    parser = IndusindStatementParser()
    assert parser.identify("", sender_email="noreply@example.com", subject="IndusInd Bank Credit Card statement") is True


def test_identify_rejects_unrelated():
    parser = IndusindStatementParser()
    assert parser.identify("", sender_email="noreply@amazon.in", subject="Your order shipped") is False


def test_extract_statement_metadata_returns_low_confidence_on_empty_text():
    parser = IndusindStatementParser()
    statement = parser.extract_statement_metadata("some unrelated text with no recognizable fields")

    assert statement.total_amount_due is None
    assert statement.minimum_amount_due is None
    assert statement.extraction_confidence == "low"
    assert statement.transactions == []
