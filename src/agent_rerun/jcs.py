"""RFC 8785 JCS canonical JSON encoding."""

from __future__ import annotations

from typing import Any

import jcs as _jcs


def jcs_bytes(value: Any) -> bytes:
    """UTF-8 bytes of the RFC 8785 JCS encoding of `value`."""
    return _jcs.canonicalize(value)
