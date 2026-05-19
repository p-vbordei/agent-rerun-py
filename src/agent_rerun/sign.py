"""Ed25519 signing/verification over the JCS bytes of a bundle (signature removed)."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .jcs import jcs_bytes
from .schema import Bundle


@dataclass(frozen=True)
class KeyPair:
    """Raw 32-byte Ed25519 keypair."""

    public_key: bytes
    private_key: bytes


def generate_key_pair() -> KeyPair:
    """Generate a random Ed25519 keypair (raw 32-byte halves)."""
    sk = Ed25519PrivateKey.generate()
    return KeyPair(public_key=_pub_raw(sk), private_key=_priv_raw(sk))


def sign_bundle(bundle: Bundle, private_key: bytes) -> Bundle:
    """Sign a bundle's JCS bytes (without `signature`) and return a new bundle with a signature."""
    sk = Ed25519PrivateKey.from_private_bytes(_ensure_32(private_key))
    payload = {k: v for k, v in bundle.items() if k != "signature"}
    sig = sk.sign(jcs_bytes(payload))
    pub = _pub_raw(sk)
    return {  # type: ignore[return-value]
        **payload,
        "signature": {
            "alg": "ed25519",
            "pubkey": base64.b64encode(pub).decode("ascii"),
            "sig": base64.b64encode(sig).decode("ascii"),
        },
    }


def verify_bundle_signature(bundle: Bundle) -> dict[str, Any]:
    """Verify a bundle's signature. Unsigned bundles return `{ "valid": True }`."""
    if "signature" not in bundle or bundle["signature"] is None:
        return {"valid": True}
    sig_block = bundle["signature"]
    payload = {k: v for k, v in bundle.items() if k != "signature"}
    try:
        pub_bytes = base64.b64decode(sig_block["pubkey"], validate=False)
        sig_bytes = base64.b64decode(sig_block["sig"], validate=False)
        pk = Ed25519PublicKey.from_public_bytes(pub_bytes)
        pk.verify(sig_bytes, jcs_bytes(payload))
        return {"valid": True}
    except InvalidSignature:
        return {"valid": False, "reason": "signature does not match payload"}
    except Exception as e:  # noqa: BLE001 — match TS try/catch wrap
        return {"valid": False, "reason": str(e)}


def _ensure_32(key: bytes) -> bytes:
    if len(key) != 32:
        raise ValueError(f"ed25519 private key must be 32 bytes, got {len(key)}")
    return key


def _pub_raw(sk: Ed25519PrivateKey) -> bytes:
    return sk.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def _priv_raw(sk: Ed25519PrivateKey) -> bytes:
    return sk.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
