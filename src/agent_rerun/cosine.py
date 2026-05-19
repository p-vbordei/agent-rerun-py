"""Cosine similarity + base64 little-endian float32 embedding codec."""

from __future__ import annotations

import base64
import math
import struct
from typing import Sequence


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity of two equal-length non-zero vectors."""
    if len(a) != len(b):
        raise ValueError(f"cosine: dimension mismatch ({len(a)} vs {len(b)})")
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0 or nb == 0:
        raise ValueError("cosine: zero-magnitude vector")
    return dot / math.sqrt(na * nb)


def encode_embedding(v: Sequence[float]) -> str:
    """Encode a float32 sequence as base64 (little-endian)."""
    packed = struct.pack(f"<{len(v)}f", *v)
    return base64.b64encode(packed).decode("ascii")


def decode_embedding(b64: str) -> list[float]:
    """Decode a base64 string into a list of float32 values."""
    raw = base64.b64decode(b64, validate=False)
    if len(raw) % 4 != 0:
        raise ValueError(
            f"decode_embedding: byte length {len(raw)} is not a multiple of 4 (Float32)"
        )
    count = len(raw) // 4
    return list(struct.unpack(f"<{count}f", raw))
