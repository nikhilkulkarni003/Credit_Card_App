"""
Thin wrapper around the Gmail API: search for candidate statement emails,
list PDF attachments, download attachment bytes. No parsing/decryption here —
that stays in src/pdf and src/parsers, kept separate on purpose.
"""

from __future__ import annotations

import base64
import logging

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from src.gmail.detector import GmailMessageSummary, build_search_query

logger = logging.getLogger("local_agent.gmail.client")


class GmailClient:
    def __init__(self, credentials: Credentials) -> None:
        self._service = build("gmail", "v1", credentials=credentials, cache_discovery=False)

    def search_candidate_statements(self, max_results: int = 50) -> list[GmailMessageSummary]:
        query = build_search_query()
        response = (
            self._service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )
        message_ids = [m["id"] for m in response.get("messages", [])]

        summaries: list[GmailMessageSummary] = []
        for message_id in message_ids:
            summaries.append(self._get_summary(message_id))
        logger.info("Gmail search returned %d candidate message(s).", len(summaries))
        return summaries

    def _get_summary(self, message_id: str) -> GmailMessageSummary:
        # Gmail's format="metadata" never includes the MIME parts tree at all
        # (only headers), so attachment presence can only be determined with
        # format="full". Costs more quota per message but is the only way to
        # know has_pdf_attachment correctly.
        msg = self._service.users().messages().get(userId="me", id=message_id, format="full").execute()

        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        has_pdf = any(_is_pdf_part(part) for part in _walk_parts(msg.get("payload", {})))
        return GmailMessageSummary(
            message_id=msg["id"],
            thread_id=msg.get("threadId", ""),
            sender_email=headers.get("From", ""),
            subject=headers.get("Subject", ""),
            has_pdf_attachment=has_pdf,
            snippet=msg.get("snippet", ""),
        )

    def download_pdf_attachments(self, message_id: str) -> list[tuple[str, bytes]]:
        """Returns [(filename, pdf_bytes), ...] for every PDF attachment on the message, at any MIME nesting depth."""
        msg = self._service.users().messages().get(userId="me", id=message_id, format="full").execute()

        results: list[tuple[str, bytes]] = []
        for part in _walk_parts(msg.get("payload", {})):
            if not _is_pdf_part(part):
                continue
            attachment_id = part.get("body", {}).get("attachmentId")
            if not attachment_id:
                continue
            attachment = (
                self._service.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=message_id, id=attachment_id)
                .execute()
            )
            data = base64.urlsafe_b64decode(attachment["data"])
            results.append((part.get("filename", "statement.pdf"), data))

        logger.info("Downloaded %d PDF attachment(s) for message %s.", len(results), message_id)
        return results


def _walk_parts(payload: dict) -> list[dict]:
    """Flatten a Gmail MIME payload tree (parts can nest arbitrarily deep)."""
    parts: list[dict] = []
    stack = [payload]
    while stack:
        node = stack.pop()
        parts.append(node)
        stack.extend(node.get("parts", []) or [])
    return parts


def _is_pdf_part(part: dict) -> bool:
    filename = part.get("filename", "")
    if filename.lower().endswith(".pdf"):
        return True
    return part.get("mimeType", "") == "application/pdf"
