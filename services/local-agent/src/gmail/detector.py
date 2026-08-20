"""
Statement-email detection heuristics.

Deliberately conservative: the product spec requires a human review step
("New Statements Found") before anything is processed, so a false positive
here just means one extra row for the user to dismiss — never auto-processed.
False negatives are worse (a real statement silently missed), so keyword
matching is intentionally broad.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_STATEMENT_KEYWORDS = re.compile(
    r"\b(e-?statement|credit card statement|monthly statement|card statement)\b",
    re.IGNORECASE,
)

_BANK_SENDER_DOMAINS = {
    "HDFC": ("hdfcbank.net", "hdfcbank.com"),
    "ICICI": ("icici.bank.in", "icicibank.com"),
    "INDUSIND": ("indusind.com",),
}


@dataclass(frozen=True)
class GmailMessageSummary:
    message_id: str
    thread_id: str
    sender_email: str
    subject: str
    has_pdf_attachment: bool
    snippet: str = ""


def looks_like_statement_email(msg: GmailMessageSummary) -> bool:
    if not msg.has_pdf_attachment:
        return False

    subject_hit = bool(_STATEMENT_KEYWORDS.search(msg.subject))
    snippet_hit = bool(_STATEMENT_KEYWORDS.search(msg.snippet))
    sender_hit = any(
        domain in msg.sender_email.lower()
        for domains in _BANK_SENDER_DOMAINS.values()
        for domain in domains
    )

    return subject_hit or snippet_hit or sender_hit


def guess_bank_code(msg: GmailMessageSummary) -> str | None:
    sender = msg.sender_email.lower()
    for bank_code, domains in _BANK_SENDER_DOMAINS.items():
        if any(domain in sender for domain in domains):
            return bank_code
    return None


def build_search_query() -> str:
    """
    Gmail search query for the discovery scan. Broad on purpose (relies on
    looks_like_statement_email() for the real filtering) — attachments only,
    recent enough to be a monthly cycle, common statement subject words.
    """
    return (
        "has:attachment filename:pdf "
        '(subject:statement OR subject:"e-statement" OR subject:"credit card")'
    )
