"""
Command-line entry points for the local agent. Run from services/local-agent with
the venv active, e.g.:

    python -m src.cli connect-gmail
    python -m src.cli scan-gmail
    python -m src.cli set-password HDFC
    python -m src.cli process-statement <gmail-message-id> HDFC
    python -m src.cli debug-extract <gmail-message-id> HDFC
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

from src.config import load_config
from src.gmail.auth import GmailAuthError, get_credentials, is_connected
from src.gmail.client import GmailClient
from src.gmail.detector import guess_bank_code, looks_like_statement_email
from src.parsers.base import StatementParseError
from src.parsers.registry import get_parser
from src.pdf.decrypt import PdfDecryptError, decrypt_and_extract_text
from src.vault import PasswordNotConfigured, PasswordScope, PasswordVault


def connect_gmail() -> None:
    config = load_config()
    if not config.gmail_oauth_client_id or not config.gmail_oauth_client_secret:
        print("GMAIL_OAUTH_CLIENT_ID / GMAIL_OAUTH_CLIENT_SECRET not set in .env")
        sys.exit(1)

    if is_connected():
        print("Gmail is already connected.")
        return

    print("Opening browser for Gmail authorization (read-only access)...")
    try:
        get_credentials(config.gmail_oauth_client_id, config.gmail_oauth_client_secret)
    except GmailAuthError as exc:
        print(f"Gmail authorization failed: {exc}")
        sys.exit(1)
    print("Gmail connected. Token stored in the OS credential store.")


def scan_gmail() -> None:
    config = load_config()
    if not is_connected():
        print("Gmail is not connected yet. Run: python -m src.cli connect-gmail")
        sys.exit(1)

    creds = get_credentials(config.gmail_oauth_client_id, config.gmail_oauth_client_secret)
    client = GmailClient(creds)
    candidates = client.search_candidate_statements()

    matches = [m for m in candidates if looks_like_statement_email(m)]
    print(f"Found {len(candidates)} candidate email(s), {len(matches)} look like statements:\n")
    for msg in matches:
        bank = guess_bank_code(msg) or "unknown"
        print(f"  [{bank}] {msg.subject!r} from {msg.sender_email} (id={msg.message_id})")

    if not matches:
        print("  (none matched — this only lists candidates; nothing is processed automatically)")


def set_password() -> None:
    if len(sys.argv) < 3:
        print("Usage: python -m src.cli set-password <BANK_CODE> [CARD_LAST_FOUR]")
        sys.exit(1)
    bank_code = sys.argv[2]
    card_id = sys.argv[3] if len(sys.argv) > 3 else None

    password = getpass.getpass(f"Statement password for {bank_code}{f' card ...{card_id}' if card_id else ' (all cards)'}: ")
    if not password:
        print("No password entered; aborting.")
        sys.exit(1)

    vault = PasswordVault()
    vault.set_password(PasswordScope(bank_code=bank_code, card_id=card_id), password)
    del password
    print(f"Password stored for {bank_code} in the OS credential store.")


def process_statement() -> None:
    if len(sys.argv) < 4:
        print("Usage: python -m src.cli process-statement <gmail-message-id> <BANK_CODE> [CARD_LAST_FOUR]")
        sys.exit(1)
    message_id, bank_code = sys.argv[2], sys.argv[3]
    card_id = sys.argv[4] if len(sys.argv) > 4 else None

    config = load_config()
    if not is_connected():
        print("Gmail is not connected yet. Run: python -m src.cli connect-gmail")
        sys.exit(1)

    vault = PasswordVault()
    try:
        password = vault.get_password(bank_code, card_id=card_id)
    except PasswordNotConfigured:
        print(f"No password configured for {bank_code}. Run: python -m src.cli set-password {bank_code}")
        sys.exit(1)

    try:
        parser = get_parser(bank_code)
    except KeyError:
        print(f"No parser registered for bank_code={bank_code!r}.")
        sys.exit(1)

    creds = get_credentials(config.gmail_oauth_client_id, config.gmail_oauth_client_secret)
    client = GmailClient(creds)
    attachments = client.download_pdf_attachments(message_id)
    if not attachments:
        print("No PDF attachments found on that message.")
        sys.exit(1)

    filename, pdf_bytes = attachments[0]
    print(f"Downloaded {filename!r} ({len(pdf_bytes)} bytes). Decrypting locally...")

    try:
        text = decrypt_and_extract_text(pdf_bytes, password)
    except PdfDecryptError as exc:
        print(f"Could not decrypt PDF: {exc}")
        sys.exit(1)
    finally:
        del password
        del pdf_bytes

    try:
        statement = parser.extract_statement_metadata(text)
    except StatementParseError as exc:
        print(f"Could not parse statement: {exc}")
        sys.exit(1)

    reconciliation = parser.validate(statement)

    print("\n--- Statement summary ---")
    print(f"Card last 4:        {statement.card_last_four}")
    print(f"Statement date:     {statement.statement_date}")
    print(f"Due date:           {statement.due_date}")
    print(f"Total amount due:   {statement.total_amount_due}")
    print(f"Minimum amount due: {statement.minimum_amount_due}")
    print(f"Closing balance:    {statement.closing_balance}")
    print(f"Extraction conf.:   {statement.extraction_confidence}")
    print(f"Transactions found: {len(statement.transactions)}")
    print(f"\n--- Reconciliation ---")
    print(f"OK: {reconciliation.ok}")
    print(reconciliation.explanation)

    if statement.transactions:
        print("\n--- First 10 transactions ---")
        for txn in statement.transactions[:10]:
            print(f"  {txn.transaction_date}  {txn.merchant_name:<30} {txn.amount:>10}  ({txn.transaction_type})")


def debug_extract() -> None:
    """
    Decrypts one statement locally and writes the RAW extracted text to a local,
    git-ignored file — nothing is sent anywhere, including to this chat. Use this
    to inspect the real layout when a bank parser's regexes don't match yet.
    """
    if len(sys.argv) < 4:
        print("Usage: python -m src.cli debug-extract <gmail-message-id> <BANK_CODE> [CARD_LAST_FOUR]")
        sys.exit(1)
    message_id, bank_code = sys.argv[2], sys.argv[3]
    card_id = sys.argv[4] if len(sys.argv) > 4 else None

    config = load_config()
    if not is_connected():
        print("Gmail is not connected yet. Run: python -m src.cli connect-gmail")
        sys.exit(1)

    vault = PasswordVault()
    try:
        password = vault.get_password(bank_code, card_id=card_id)
    except PasswordNotConfigured:
        print(f"No password configured for {bank_code}. Run: python -m src.cli set-password {bank_code}")
        sys.exit(1)

    creds = get_credentials(config.gmail_oauth_client_id, config.gmail_oauth_client_secret)
    client = GmailClient(creds)
    attachments = client.download_pdf_attachments(message_id)
    if not attachments:
        print("No PDF attachments found on that message.")
        sys.exit(1)

    filename, pdf_bytes = attachments[0]
    try:
        text = decrypt_and_extract_text(pdf_bytes, password)
    except PdfDecryptError as exc:
        print(f"Could not decrypt PDF: {exc}")
        sys.exit(1)
    finally:
        del password
        del pdf_bytes

    out_dir = Path(__file__).resolve().parents[1] / "tmp"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "debug_extract.txt"
    out_path.write_text(text, encoding="utf-8")

    print(f"Wrote {len(text)} characters of extracted text to:\n  {out_path}")
    print("This file is git-ignored and was never sent anywhere. Open it locally to inspect the layout.")


COMMANDS = {
    "connect-gmail": connect_gmail,
    "scan-gmail": scan_gmail,
    "set-password": set_password,
    "process-statement": process_statement,
    "debug-extract": debug_extract,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"Usage: python -m src.cli <{'|'.join(COMMANDS)}> [args...]")
        sys.exit(1)
    COMMANDS[sys.argv[1]]()


if __name__ == "__main__":
    main()
