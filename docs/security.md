# Security Model

## Golden rule

**Statement passwords never leave the local machine.** Not to Supabase, not to Vercel, not to Gemini/OpenAI, not in logs, not in error messages, not in Git.

## Threat model

- **Cloud database compromise (Supabase):** must not expose any statement password, OAuth token, or raw PDF content — because none of those are ever stored there.
- **Local machine compromise:** the vault is protected by the OS user account (Windows DPAPI / Credential Manager via the `keyring` library, backed by `pywin32`/`win32crypt` under the hood). An attacker with the same OS session as the user could access it — this is the accepted boundary, equivalent to how browsers/password managers protect saved credentials on Windows.
- **Network interception:** Gmail access uses OAuth 2.0 over HTTPS; no password is ever transmitted to Gmail. Supabase access uses HTTPS with the anon/public key from the browser (RLS-enforced) and the service-role key only from trusted local/server contexts, never the browser.
- **Malicious/careless logging:** logging code is required to pass only IDs and safe metadata; passwords and tokens must never be interpolated into log strings (enforced by code review discipline + a redaction test in `services/local-agent/tests`).

## Statement password storage

- Primary mechanism: Windows Credential Manager, accessed via the Python `keyring` library (`keyring.set_password` / `get_password`), which on Windows uses DPAPI-backed storage tied to the logged-in user account.
- Passwords are stored per bank (with the option of a more specific per-card override) — never in a database table, never in a plaintext file.
- Passwords are read into memory only for the duration of a single PDF decrypt call, then the local variable is overwritten/dereferenced immediately after use.
- No password is ever included in a Supabase insert/update payload — the sync layer's data models (`services/local-agent/src/models`) do not even have a password field, so it is structurally impossible to serialize one by accident.

## OAuth token storage

- Gmail OAuth tokens (refresh + access token) are stored using the same OS-protected mechanism as statement passwords (`keyring`), not as a plaintext `token.json` on disk.
- OAuth client secret (from Google Cloud Console) is supplied via a local-only `.env` file for `services/local-agent`, which is git-ignored and never synced to any cloud service.

## What is sent to Gemini (AI fallback), and what is never sent

Sent (only for transactions with no matching rule): merchant string, normalized description, amount, currency.
Never sent: statement password, OAuth tokens, full statement PDF/text, any other transaction on the statement, card number, personal identifiers beyond what's needed to categorize a single line item.

## Database security (Supabase)

- Row Level Security is enabled on every user-owned table; policies check `auth.uid()` against the row's `user_id` (directly or via the parent `card_id`/`statement_id` chain).
- The Supabase **service-role key** is used only by the local agent's sync process (a trusted, local, non-browser context) and is never bundled into the Next.js client. The web app uses the anon key + Supabase Auth session, relying on RLS.

## Local agent network exposure

If the web app and local agent need to talk over localhost, the local agent binds to `127.0.0.1` only, requires a per-session local token (generated at agent startup, never transmitted off-machine), and rejects any request without it. It is never exposed to `0.0.0.0` or the public internet.

## What happens if the local machine is lost

Statement passwords stored in Windows Credential Manager are lost with the machine (or recoverable only via Windows account backup/sync, which is a Microsoft-managed mechanism, not something this app relies on). This is a deliberate trade-off: **no plaintext password recovery/escrow is implemented**, because doing so would require storing passwords somewhere recoverable, which violates the golden rule. Recovery = re-enter the statement passwords (which the user already knows) on a new machine. This is documented so it is a known, accepted trade-off rather than a surprise.

## Audit

See `docs/security-audit.md` (created in the hardening phase) for the point-in-time repo-wide secret scan and verification checklist.
