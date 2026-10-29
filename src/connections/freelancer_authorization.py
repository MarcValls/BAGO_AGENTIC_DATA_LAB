"""One-use, in-memory human approval for a bounded Freelancer read."""
from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time
from copy import deepcopy
from typing import Any

from .freelancer_readonly import FreelancerReadError, build_read_request


class FreelancerAuthorizationError(ValueError):
    def __init__(self, code: str, status: int = 403):
        self.code = code
        self.status = status
        super().__init__(code)


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class FreelancerReadChallenges:
    """Short-lived challenge records; never persisted and consumed exactly once."""

    TTL_SECONDS = 90
    MAX_PENDING = 128

    def __init__(self, *, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._items: dict[str, dict[str, Any]] = {}

    def issue(self, *, connection_id: str, connection_revision: str,
              environment: str, account_id: int, operation: str,
              arguments: dict[str, Any], conversation_id: str,
              conversation_revision: int) -> dict[str, Any]:
        if not all(isinstance(value, str) and value for value in
                   (connection_id, connection_revision, conversation_id)):
            raise FreelancerAuthorizationError("invalid_binding", 422)
        if environment not in {"sandbox", "production"} or type(account_id) is not int or account_id < 1:
            raise FreelancerAuthorizationError("invalid_binding", 422)
        if type(conversation_revision) is not int or conversation_revision < 0:
            raise FreelancerAuthorizationError("invalid_binding", 422)
        try:
            path, params = build_read_request(operation, arguments)
        except FreelancerReadError as error:
            raise FreelancerAuthorizationError(error.code, 422) from None
        identifier = "fln_challenge_" + secrets.token_urlsafe(24)
        binding = {
            "connection_id": connection_id,
            "connection_revision": connection_revision,
            "environment": environment,
            "account_id": account_id,
            "operation": operation,
            "arguments": deepcopy(arguments),
            "request": {"path": path, "params": params},
            "conversation_id": conversation_id,
            "conversation_revision": conversation_revision,
        }
        expires_at = self._clock() + self.TTL_SECONDS
        with self._lock:
            now = self._clock()
            self._items = {key: row for key, row in self._items.items() if row["expires"] > now}
            if len(self._items) >= self.MAX_PENDING:
                raise FreelancerAuthorizationError("too_many_pending_reads", 429)
            self._items[identifier] = {"binding": binding, "expires": expires_at}
        return {
            "challenge_id": identifier,
            "connection_id": connection_id,
            "environment": environment,
            "account_id": account_id,
            "operation": operation,
            "arguments": deepcopy(arguments),
            "conversation_id": conversation_id,
            "conversation_revision": conversation_revision,
            "expires_in_seconds": self.TTL_SECONDS,
            "request_fingerprint": _digest(binding),
        }

    def consume(self, challenge_id: str, *, connection_id: str,
                connection_revision: str, environment: str, account_id: int,
                conversation_id: str, conversation_revision: int) -> dict[str, Any]:
        if not isinstance(challenge_id, str) or not challenge_id.startswith("fln_challenge_"):
            raise FreelancerAuthorizationError("authorization_invalid")
        with self._lock:
            row = self._items.pop(challenge_id, None)
        if row is None or row["expires"] <= self._clock():
            raise FreelancerAuthorizationError("authorization_expired")
        binding = row["binding"]
        expected = {
            "connection_id": connection_id,
            "connection_revision": connection_revision,
            "environment": environment,
            "account_id": account_id,
            "conversation_id": conversation_id,
            "conversation_revision": conversation_revision,
        }
        if any(binding.get(key) != value for key, value in expected.items()):
            raise FreelancerAuthorizationError("authorization_binding_mismatch")
        return {key: deepcopy(binding[key]) for key in ("operation", "arguments")}
