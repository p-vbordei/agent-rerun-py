"""SHA-256 hashing helpers."""

from __future__ import annotations

import hashlib
from typing import Any

from .jcs import jcs_bytes


def sha256_hex(data: bytes) -> str:
    """Hex-encoded SHA-256 prefixed with `sha256:`."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def sha256_of_jcs(value: Any) -> str:
    """SHA-256 of the RFC 8785 JCS encoding of `value`."""
    return sha256_hex(jcs_bytes(value))
