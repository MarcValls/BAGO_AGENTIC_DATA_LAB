"""Independent read-only observer for the fixed synthetic fixture oracle.

This module intentionally keeps its own pinned byte vector and does not import
the executor adapter's output, digest, or success predicate.
"""

from hashlib import sha256

from .fixture_read import FIXTURE_ID

_OBSERVED_FIXTURE_ID = "adl.synthetic.customer-summary.v1"
_OBSERVED_FIXTURE_BYTES = b'{"customer_id":"fixture-customer-001","status":"synthetic","open_invoice_count":2}\n'
OBSERVED_FIXTURE_SHA256 = sha256(_OBSERVED_FIXTURE_BYTES).hexdigest()


def observe_fixture_output(fixture_id: str) -> bytes:
    """Read the independently pinned postcondition bytes for the fixture ID."""
    if fixture_id != _OBSERVED_FIXTURE_ID or fixture_id != FIXTURE_ID:
        raise ValueError("no independent observer is registered for this fixture")
    return bytes(_OBSERVED_FIXTURE_BYTES)
