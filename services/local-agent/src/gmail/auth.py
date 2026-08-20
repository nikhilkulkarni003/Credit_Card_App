"""
Gmail OAuth 2.0 flow.

Threat model note (see docs/security.md): the OAuth refresh token is exactly as
sensitive as a password — anyone holding it can read the user's Gmail (readonly
scope only, per the consent screen config). It is therefore stored the same way
statement passwords are: via `keyring` (OS credential store), never as a plaintext
`token.json` file on disk, and never logged.
"""

from __future__ import annotations

import json
import logging

import keyring
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

logger = logging.getLogger("local_agent.gmail.auth")

_SERVICE_NAMESPACE = "credit-card-cfo"
_TOKEN_KEY = "gmail-oauth-token"

# Read-only: the agent only ever needs to search/read messages and download
# attachments. It must never be granted send/modify/delete scopes.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailAuthError(Exception):
    """Raised on OAuth/token failures. Message must never include token values."""


def _load_stored_credentials() -> Credentials | None:
    raw = keyring.get_password(_SERVICE_NAMESPACE, _TOKEN_KEY)
    if not raw:
        return None
    data = json.loads(raw)
    return Credentials.from_authorized_user_info(data, scopes=SCOPES)


def _store_credentials(creds: Credentials) -> None:
    keyring.set_password(_SERVICE_NAMESPACE, _TOKEN_KEY, creds.to_json())
    logger.info("Gmail OAuth token stored in OS credential store.")


def clear_stored_credentials() -> None:
    try:
        keyring.delete_password(_SERVICE_NAMESPACE, _TOKEN_KEY)
        logger.info("Gmail OAuth token cleared.")
    except keyring.errors.PasswordDeleteError:
        pass


def get_credentials(client_id: str, client_secret: str) -> Credentials:
    """
    Return valid Gmail API credentials, running the interactive OAuth consent
    flow only if no stored token exists or the stored one can't be refreshed.
    """
    creds = _load_stored_credentials()

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _store_credentials(creds)
            return creds
        except Exception as exc:  # refresh token revoked/expired
            logger.warning("Gmail token refresh failed; re-authorization required.")
            clear_stored_credentials()
            raise GmailAuthError("Gmail authorization expired. Please reconnect Gmail.") from exc

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0)
    _store_credentials(creds)
    return creds


def is_connected() -> bool:
    creds = _load_stored_credentials()
    return creds is not None and (creds.valid or bool(creds.refresh_token))
