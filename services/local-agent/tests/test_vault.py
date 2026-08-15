"""
Security tests for the password vault.

Uses keyring's in-memory test backend (keyring.backends.fail / a fake backend)
so these tests never touch the real Windows Credential Manager.
"""

import logging

import pytest
from keyring.backend import KeyringBackend
from keyring.errors import PasswordDeleteError

from src.vault.vault import PasswordVault, PasswordScope, PasswordNotConfigured, VaultError


class InMemoryKeyring(KeyringBackend):
    """Fake keyring backend for tests — stores values in a plain dict."""

    priority = 1

    def __init__(self):
        self._store: dict[tuple[str, str], str] = {}

    def set_password(self, service, username, password):
        self._store[(service, username)] = password

    def get_password(self, service, username):
        return self._store.get((service, username))

    def delete_password(self, service, username):
        if (service, username) not in self._store:
            raise PasswordDeleteError("not found")
        del self._store[(service, username)]


@pytest.fixture
def vault():
    return PasswordVault(keyring_backend=InMemoryKeyring())


def test_set_and_get_bank_level_password(vault):
    scope = PasswordScope(bank_code="hdfc")
    vault.set_password(scope, "s3cr3t-statement-pw")
    assert vault.get_password("hdfc") == "s3cr3t-statement-pw"


def test_card_level_password_overrides_bank_level(vault):
    vault.set_password(PasswordScope(bank_code="hdfc"), "bank-wide-pw")
    vault.set_password(PasswordScope(bank_code="hdfc", card_id="card-123"), "card-specific-pw")

    assert vault.get_password("hdfc", card_id="card-123") == "card-specific-pw"
    assert vault.get_password("hdfc", card_id="other-card") == "bank-wide-pw"


def test_get_password_raises_when_not_configured(vault):
    with pytest.raises(PasswordNotConfigured):
        vault.get_password("icici")


def test_empty_password_rejected(vault):
    with pytest.raises(VaultError):
        vault.set_password(PasswordScope(bank_code="hdfc"), "")


def test_delete_password(vault):
    scope = PasswordScope(bank_code="hdfc")
    vault.set_password(scope, "pw")
    assert vault.has_password(scope) is True
    vault.delete_password(scope)
    assert vault.has_password(scope) is False


def test_delete_nonexistent_password_raises(vault):
    with pytest.raises(PasswordNotConfigured):
        vault.delete_password(PasswordScope(bank_code="axis"))


def test_password_never_appears_in_log_output(vault, caplog):
    secret = "super-secret-statement-password-12345"
    with caplog.at_level(logging.DEBUG):
        vault.set_password(PasswordScope(bank_code="hdfc"), secret)
        vault.get_password("hdfc")
        vault.delete_password(PasswordScope(bank_code="hdfc"))

    for record in caplog.records:
        assert secret not in record.getMessage(), (
            "Statement password leaked into log output — this must never happen."
        )


def test_test_password_does_not_persist_candidate(vault):
    probe_calls = []

    def fake_probe(pw):
        probe_calls.append(pw)
        return pw == "correct-pw"

    assert vault.test_password("hdfc", "correct-pw", fake_probe) is True
    assert vault.test_password("hdfc", "wrong-pw", fake_probe) is False
    # test_password must never call set_password internally
    assert vault.has_password(PasswordScope(bank_code="hdfc")) is False
