"""Unit tests covering capture, sign/verify, JCS, hash, cosine, and embedding codec."""

from __future__ import annotations

import base64
import struct

import pytest

from agent_rerun import (
    CaptureOptions,
    KeyPair,
    capture,
    cosine,
    decode_embedding,
    encode_embedding,
    generate_key_pair,
    jcs_bytes,
    sha256_hex,
    sha256_of_jcs,
    sign_bundle,
    validate_actual_record,
    validate_bundle,
    validate_step_record,
    verify,
    verify_bundle_signature,
)
from agent_rerun.schema import ValidationError


# ----------------------------- jcs / hash --------------------------------- #


def test_jcs_sorts_keys() -> None:
    assert jcs_bytes({"b": 1, "a": 2}) == b'{"a":2,"b":1}'


def test_sha256_hex_known() -> None:
    assert sha256_hex(b"") == (
        "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


def test_sha256_of_jcs_matches_canonical_bytes() -> None:
    value = {"messages": [{"role": "user", "content": "hi"}]}
    assert sha256_of_jcs(value) == sha256_hex(jcs_bytes(value))


# ----------------------------- cosine ------------------------------------- #


def test_cosine_identical() -> None:
    assert cosine([1.0, 0.0, 0.0], [1.0, 0.0, 0.0]) == pytest.approx(1.0)


def test_cosine_orthogonal_zero() -> None:
    assert cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_dimension_mismatch() -> None:
    with pytest.raises(ValueError, match="dimension mismatch"):
        cosine([1.0], [1.0, 0.0])


def test_cosine_zero_vector() -> None:
    with pytest.raises(ValueError, match="zero-magnitude"):
        cosine([0.0, 0.0], [1.0, 0.0])


def test_embedding_roundtrip() -> None:
    v = [1.0, -2.5, 0.0, 3.25]
    out = decode_embedding(encode_embedding(v))
    assert out == pytest.approx(v)


def test_embedding_decode_bad_length() -> None:
    with pytest.raises(ValueError, match="multiple of 4"):
        decode_embedding(base64.b64encode(b"abc").decode())


# ----------------------------- sign / verify ------------------------------ #


def _base_step() -> dict:
    return {
        "model": {"vendor": "anthropic", "id": "claude-opus-4-7"},
        "sampling": {"temperature": 0, "top_p": 1, "seed": 42},
        "inputs": {
            "system_prompt": "you are a helpful assistant",
            "messages": [{"role": "user", "content": "say hi"}],
        },
        "runtime": {"class": "cloud"},
        "expected": {"transcript": {"messages": [{"role": "assistant", "content": "hi"}]}},
        "tolerance": {"level": "byte"},
    }


def test_capture_then_verify_byte() -> None:
    step = _base_step()
    bundle = capture(step)
    actual = {
        "inputs": {
            "system_prompt": step["inputs"]["system_prompt"],
            "messages": step["inputs"]["messages"],
        },
        "output": {"transcript": step["expected"]["transcript"]},
    }
    res = verify(bundle, actual)
    assert res.verified, res.errors


def test_sign_and_verify_signature_roundtrip() -> None:
    kp: KeyPair = generate_key_pair()
    step = _base_step()
    bundle = capture(step, CaptureOptions(signing_key=kp.private_key))
    assert "signature" in bundle
    assert verify_bundle_signature(bundle)["valid"]

    # Mutate after sign — signature must fail.
    tampered = {**bundle, "sampling": {**bundle["sampling"], "temperature": 0.7}}
    assert not verify_bundle_signature(tampered)["valid"]


def test_unsigned_bundle_verifies_as_valid_signature() -> None:
    bundle = capture(_base_step())
    assert verify_bundle_signature(bundle)["valid"]


def test_sign_bundle_strips_existing_signature() -> None:
    kp = generate_key_pair()
    bundle = capture(_base_step(), CaptureOptions(signing_key=kp.private_key))
    # Re-sign with a new key — the new signature MUST validate.
    kp2 = generate_key_pair()
    resigned = sign_bundle(bundle, kp2.private_key)
    assert verify_bundle_signature(resigned)["valid"]


# ----------------------------- schema ------------------------------------- #


def test_validate_bundle_rejects_extra_field() -> None:
    bundle = capture(_base_step())
    bundle_with_extra = {**bundle, "MYSTERY": "extra"}
    with pytest.raises(ValidationError, match="unrecognized key"):
        validate_bundle(bundle_with_extra)


def test_validate_bundle_rejects_extra_inputs_field() -> None:
    bundle = capture(_base_step())
    bad_inputs = {**bundle["inputs"], "fake_sha256": "sha256:" + "0" * 64}
    with pytest.raises(ValidationError, match="unrecognized key"):
        validate_bundle({**bundle, "inputs": bad_inputs})


def test_validate_bundle_bad_version() -> None:
    bundle = capture(_base_step())
    with pytest.raises(ValidationError, match="rerun_version"):
        validate_bundle({**bundle, "rerun_version": "0.2"})


def test_validate_bundle_byte_requires_transcript_sha256() -> None:
    bundle = capture(_base_step())
    with pytest.raises(ValidationError, match="byte tolerance requires"):
        validate_bundle({**bundle, "expected": {}})


def test_validate_bundle_semantic_requires_threshold() -> None:
    step = _base_step()
    step["expected"] = {"semantic_embedding": encode_embedding([1.0, 0.0])}
    step["tolerance"] = {"level": "semantic", "threshold": 0.5}
    bundle = capture(step)
    bad = {**bundle, "tolerance": {"level": "semantic"}}
    with pytest.raises(ValidationError):
        validate_bundle(bad)


def test_validate_step_record_strict_extra() -> None:
    step = _base_step()
    step["MYSTERY"] = "x"
    with pytest.raises(ValidationError, match="unrecognized key"):
        validate_step_record(step)


def test_validate_actual_record_extra_inputs_field() -> None:
    actual = {
        "inputs": {
            "system_prompt": "s",
            "messages": [],
            "BAD": 1,
        },
        "output": {},
    }
    with pytest.raises(ValidationError):
        validate_actual_record(actual)


# ----------------------------- verify edge cases ------------------------- #


def test_byte_tolerance_missing_transcript_in_actual() -> None:
    step = _base_step()
    bundle = capture(step)
    actual = {
        "inputs": {
            "system_prompt": step["inputs"]["system_prompt"],
            "messages": step["inputs"]["messages"],
        },
        "output": {},
    }
    res = verify(bundle, actual)
    assert not res.verified
    assert any("TranscriptHashMismatch" in e for e in res.errors)


def test_semantic_tolerance_missing_embedding() -> None:
    step = _base_step()
    step["expected"] = {"semantic_embedding": encode_embedding([1.0, 0.0])}
    step["tolerance"] = {"level": "semantic", "threshold": 0.5}
    bundle = capture(step)
    actual = {
        "inputs": {
            "system_prompt": step["inputs"]["system_prompt"],
            "messages": step["inputs"]["messages"],
        },
        "output": {},
    }
    res = verify(bundle, actual)
    assert not res.verified
    assert any("MissingEmbedding" in e for e in res.errors)


def test_tools_hash_check() -> None:
    step = _base_step()
    step["inputs"]["tools"] = [{"name": "echo", "args": "string"}]
    bundle = capture(step)
    assert "tools_sha256" in bundle["inputs"]
    actual = {
        "inputs": {
            "system_prompt": step["inputs"]["system_prompt"],
            "messages": step["inputs"]["messages"],
            "tools": [{"name": "OTHER", "args": "string"}],
        },
        "output": {"transcript": step["expected"]["transcript"]},
    }
    res = verify(bundle, actual)
    assert any("tools_sha256" in e for e in res.errors)


def test_tools_hash_missing_in_actual() -> None:
    step = _base_step()
    step["inputs"]["tools"] = [{"name": "echo"}]
    bundle = capture(step)
    actual = {
        "inputs": {
            "system_prompt": step["inputs"]["system_prompt"],
            "messages": step["inputs"]["messages"],
        },
        "output": {"transcript": step["expected"]["transcript"]},
    }
    res = verify(bundle, actual)
    assert any("tools_sha256" in e for e in res.errors)


def test_test_key_signs_and_verifies() -> None:
    """The fixed test key in vectors/test-key.json must produce a valid signature."""
    import json
    from pathlib import Path

    key_doc = json.loads(
        (Path(__file__).resolve().parent.parent / "vectors" / "test-key.json").read_text()
    )
    priv = base64.b64decode(key_doc["privateKey"])
    bundle = capture(_base_step(), CaptureOptions(signing_key=priv))
    assert verify_bundle_signature(bundle)["valid"]
    # Encoded pubkey matches the doc.
    assert bundle["signature"]["pubkey"] == key_doc["publicKey"]


# ----------------------------- float pack sanity -------------------------- #


def test_float32_endianness_is_little() -> None:
    """The TS reference encodes Float32Array as native little-endian."""
    raw = base64.b64decode(encode_embedding([1.0]))
    assert raw == struct.pack("<f", 1.0)
