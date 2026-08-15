"""
Local statement-password vault.

Storage mechanism: the OS-protected credential store, via the `keyring` library.
On Windows this resolves to Windows Credential Manager, which is backed by DPAPI
and tied to the logged-in Windows user account. We deliberately do NOT invent our
own encryption scheme — `keyring` delegates to the OS-native, audited mechanism.

Threat model (see docs/security.md for the full writeup):
  - Passwords are never written to disk in plaintext by this module.
  - Passwords are never logged (see `_redact` and the logging discipline below).
  - Passwords are never included in any object that gets serialized for Supabase sync
    (there is no password field on any sync model — see src/models).
  - A password is only ever held in a Python variable for the duration of a single
    decrypt call; callers MUST NOT cache it beyond that.

Scope model: a password can be registered per-bank ("use for all cards from this bank")
or per-card (a specific card overrides the bank-level password). Card-level lookup is
tried first, then falls back to bank-level.
"""

from __future__ import annotations

import ctypes
import logging
from dataclasses import dataclass

import keyring
from keyring.errors import PasswordDeleteError

logger = logging.getLogger("local_agent.vault")

_SERVICE_NAMESPACE = "credit-card-cfo"


class VaultError(Exception):
    """Base error for vault operations. Messages must never include a password value."""


class PasswordNotConfigured(VaultError):
    """Raised when no password is configured for the requested bank/card scope."""


def _bank_key(bank_code: str) -> str:
    return f"{_SERVICE_NAMESPACE}:bank:{bank_code.upper()}"


def _card_key(bank_code: str, card_id: str) -> str:
    return f"{_SERVICE_NAMESPACE}:card:{bank_code.upper()}:{card_id}"


def _redact(_: str) -> str:
    # Defensive helper: if a password value is ever accidentally passed to a
    # logging call, this guarantees the literal value never reaches the log sink.
    return "***REDACTED***"


def _wipe(value: bytearray) -> None:
    """Best-effort overwrite of a mutable buffer holding sensitive data."""
    ctypes.memset(ctypes.addressof((ctypes.c_char * len(value)).from_buffer(value)), 0, len(value))


@dataclass(frozen=True)
class PasswordScope:
    bank_code: str
    card_id: str | None = None  # None => bank-wide password


class PasswordVault:
    """CRUD + lookup for statement passwords, backed by the OS credential store."""

    def __init__(self, keyring_backend=None) -> None:
        # Allows injecting an in-memory backend for tests; production uses the
        # OS-default backend (Windows Credential Manager via keyring's WinVaultKeyring).
        self._backend = keyring_backend or keyring.get_keyring()

    def set_password(self, scope: PasswordScope, password: str) -> None:
        if not password:
            raise VaultError("Refusing to store an empty password.")
        key = self._key_for(scope)
        self._backend.set_password(_SERVICE_NAMESPACE, key, password)
        logger.info("Statement password configured for scope=%s", self._safe_scope_label(scope))

    def has_password(self, scope: PasswordScope) -> bool:
        key = self._key_for(scope)
        return self._backend.get_password(_SERVICE_NAMESPACE, key) is not None

    def get_password(self, bank_code: str, card_id: str | None = None) -> str:
        """
        Resolve a password for decrypting a statement: try the card-specific
        override first, then fall back to the bank-wide password.
        Raises PasswordNotConfigured if neither exists.
        """
        if card_id:
            card_scope = PasswordScope(bank_code=bank_code, card_id=card_id)
            value = self._backend.get_password(_SERVICE_NAMESPACE, self._key_for(card_scope))
            if value is not None:
                return value

        bank_scope = PasswordScope(bank_code=bank_code, card_id=None)
        value = self._backend.get_password(_SERVICE_NAMESPACE, self._key_for(bank_scope))
        if value is not None:
            return value

        raise PasswordNotConfigured(
            f"No statement password configured for bank={bank_code}"
            + (f", card={card_id}" if card_id else "")
        )

    def delete_password(self, scope: PasswordScope) -> None:
        key = self._key_for(scope)
        try:
            self._backend.delete_password(_SERVICE_NAMESPACE, key)
        except PasswordDeleteError:
            raise PasswordNotConfigured("No password configured for that scope; nothing to delete.")
        logger.info("Statement password deleted for scope=%s", self._safe_scope_label(scope))

    def test_password(self, bank_code: str, candidate_password: str, decrypt_probe) -> bool:
        """
        Verify a candidate password without persisting it, by handing it to a
        caller-supplied decrypt probe (e.g. "try opening this sample/real PDF").
        The candidate password is never logged or stored by this method.
        """
        try:
            return bool(decrypt_probe(candidate_password))
        finally:
            del candidate_password

    @staticmethod
    def _key_for(scope: PasswordScope) -> str:
        if scope.card_id:
            return _card_key(scope.bank_code, scope.card_id)
        return _bank_key(scope.bank_code)

    @staticmethod
    def _safe_scope_label(scope: PasswordScope) -> str:
        return f"bank={scope.bank_code}" + (f" card={scope.card_id}" if scope.card_id else " (bank-wide)")
