"""Exact MIT source segments; AUTH_EXTRACTION.json and THIRD_PARTY_LICENSE_BAGO.txt."""
from __future__ import annotations
import json

def _parse_status_hosts(output: str) -> dict[str, list[dict]]:
    """Parse `gh auth status --json hosts` output into a hostname -> accounts map."""
    try:
        data = json.loads(output) if output else {}
    except json.JSONDecodeError:
        return {}
    hosts = data.get("hosts", {}) if isinstance(data, dict) else {}
    if not isinstance(hosts, dict):
        return {}
    return {str(host): [a for a in (accts or []) if isinstance(a, dict)] for host, accts in hosts.items()}


def _valid_accounts(hosts: dict[str, list[dict]]) -> list[dict]:
    return [acct for accts in hosts.values() for acct in accts if acct.get("state") == "success"]


def _credential_storage_for(account: dict) -> str:
    """Map the account tokenSource reported by gh to the public credentialStorage contract."""
    src = str(account.get("tokenSource") or "")
    if not src:
        return "unknown"
    low = src.lower()
    if "keyring" in low or "keychain" in low:
        return "secure"
    if "_TOKEN" in src or src.startswith(("GH_", "GITHUB_", "COPILOT_")):
        return "unknown"  # environment-provided, not stored locally
    return "plaintext"  # remaining sources are on-disk config files


def _extract_auth_info(code: int, output: str, error: str) -> dict:
    """Extract auth info from `gh auth status --json hosts`, never exposing tokens.

    With --json, gh exits zero even when there are authentication issues, so
    `authenticated` is derived strictly from the hosts/accounts payload.
    """
    checked_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    if code == 127:
        return {
            "installed": False,
            "authenticated": False,
            "credentialStorage": "unknown",
            "error": error or "gh no está instalado",
            "checkedAt": checked_at,
        }

    hosts = _parse_status_hosts(output)
    valid = _valid_accounts(hosts)

    if not valid:
        return {
            "installed": True,
            "authenticated": False,
            "credentialStorage": "unknown",
            "error": error or None,
            "checkedAt": checked_at,
        }

    active = next((a for a in valid if a.get("active")), valid[0])
    username = str(active.get("login") or "") or None
    hostname = str(active.get("host") or "") or None
    scopes = [s.strip() for s in str(active.get("scopes") or "").split(",") if s.strip()]

    return {
        "installed": True,
        "authenticated": True,
        "hostname": hostname,
        "username": username,
        "activeAccount": username,
        "scopes": scopes,
        "credentialStorage": _credential_storage_for(active),
        "error": None,
        "checkedAt": checked_at,
    }
