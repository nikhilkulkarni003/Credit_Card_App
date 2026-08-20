from src.gmail.detector import GmailMessageSummary, guess_bank_code, looks_like_statement_email


def make_msg(**overrides) -> GmailMessageSummary:
    defaults = dict(
        message_id="m1",
        thread_id="t1",
        sender_email="statements@hdfcbank.net",
        subject="Your HDFC Bank Credit Card Statement",
        has_pdf_attachment=True,
        snippet="Your monthly e-statement is attached.",
    )
    defaults.update(overrides)
    return GmailMessageSummary(**defaults)


def test_matches_on_subject_keyword():
    msg = make_msg(subject="Your Credit Card Statement for August", sender_email="noreply@somebank.com", snippet="")
    assert looks_like_statement_email(msg) is True


def test_matches_on_sender_domain_even_without_keyword():
    msg = make_msg(subject="Important update", snippet="", sender_email="alerts@hdfcbank.net")
    assert looks_like_statement_email(msg) is True


def test_rejects_without_pdf_attachment():
    msg = make_msg(has_pdf_attachment=False)
    assert looks_like_statement_email(msg) is False


def test_rejects_unrelated_email():
    msg = make_msg(
        subject="Your Amazon order has shipped",
        snippet="Track your package",
        sender_email="ship-confirm@amazon.in",
        has_pdf_attachment=True,
    )
    assert looks_like_statement_email(msg) is False


def test_guess_bank_code_hdfc():
    msg = make_msg(sender_email="estatements@hdfcbank.net")
    assert guess_bank_code(msg) == "HDFC"


def test_guess_bank_code_unknown_sender():
    msg = make_msg(sender_email="someone@example.com")
    assert guess_bank_code(msg) is None


def test_guess_bank_code_icici():
    msg = make_msg(sender_email="credit_card@icici.bank.in")
    assert guess_bank_code(msg) == "ICICI"
