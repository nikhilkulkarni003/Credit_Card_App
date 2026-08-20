"""
Command-line entry points for the local agent. Run from services/local-agent with
the venv active, e.g.:

    python -m src.cli connect-gmail
    python -m src.cli scan-gmail
"""

from __future__ import annotations

import sys

from src.config import load_config
from src.gmail.auth import GmailAuthError, get_credentials, is_connected
from src.gmail.client import GmailClient
from src.gmail.detector import guess_bank_code, looks_like_statement_email


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


COMMANDS = {
    "connect-gmail": connect_gmail,
    "scan-gmail": scan_gmail,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"Usage: python -m src.cli <{'|'.join(COMMANDS)}>")
        sys.exit(1)
    COMMANDS[sys.argv[1]]()


if __name__ == "__main__":
    main()
