"""Verify an actual record against a bundle per the bundle's tolerance level."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .cosine import cosine, decode_embedding
from .hash import sha256_of_jcs
from .schema import ValidationError, validate_actual_record, validate_bundle
from .sign import verify_bundle_signature


@dataclass
class VerifyResult:
    verified: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def verify(bundle: Any, actual: Any) -> VerifyResult:
    """Verify an actual record against a bundle per the bundle's tolerance level."""
    errors: list[str] = []
    warnings: list[str] = []

    try:
        b = validate_bundle(bundle)
    except ValidationError as e:
        return VerifyResult(verified=False, errors=[f"SchemaViolation:bundle: {e}"])
    try:
        a = validate_actual_record(actual)
    except ValidationError as e:
        return VerifyResult(verified=False, errors=[f"SchemaViolation:actual: {e}"])

    # Signature (C3).
    if "signature" in b and b["signature"] is not None:
        sig_check = verify_bundle_signature(b)
        if not sig_check.get("valid"):
            reason = sig_check.get("reason", "invalid")
            errors.append(f"BadSignature:{reason}")

    # Fingerprint drift (SPEC §6).
    bundle_fp = b["model"].get("fingerprint")
    actual_fp = (a.get("runtime") or {}).get("fingerprint")
    if bundle_fp is not None and actual_fp is not None and bundle_fp != actual_fp:
        warnings.append(f"FingerprintDrift:bundle={bundle_fp},actual={actual_fp}")

    # Input hashes (C4 et al.)
    if sha256_of_jcs(a["inputs"]["system_prompt"]) != b["inputs"]["system_prompt_sha256"]:
        errors.append("InputHashMismatch:system_prompt_sha256")
    if sha256_of_jcs(a["inputs"]["messages"]) != b["inputs"]["messages_sha256"]:
        errors.append("InputHashMismatch:messages_sha256")
    if "tools_sha256" in b["inputs"]:
        if "tools" not in a["inputs"]:
            errors.append("InputHashMismatch:tools_sha256")
        elif sha256_of_jcs(a["inputs"]["tools"]) != b["inputs"]["tools_sha256"]:
            errors.append("InputHashMismatch:tools_sha256")

    # Tolerance check.
    level = b["tolerance"]["level"]
    if level == "byte":
        if "transcript" not in a["output"] or a["output"]["transcript"] is None:
            errors.append("TranscriptHashMismatch:actual.output.transcript missing")
        elif sha256_of_jcs(a["output"]["transcript"]) != b["expected"]["transcript_sha256"]:
            errors.append("TranscriptHashMismatch")
    elif level == "semantic":
        if "embedding" not in a["output"] or not a["output"]["embedding"]:
            errors.append("MissingEmbedding:actual.output.embedding required for semantic tolerance")
        else:
            exp = decode_embedding(b["expected"]["semantic_embedding"])
            act = decode_embedding(a["output"]["embedding"])
            if len(exp) != len(act):
                errors.append(f"EmbeddingDimensionMismatch:expected {len(exp)}, got {len(act)}")
            else:
                sim = cosine(exp, act)
                threshold = b["tolerance"]["threshold"]
                if sim < threshold:
                    errors.append(
                        f"SemanticBelowThreshold:cosine={sim:.4f},threshold={threshold}"
                    )
    elif level == "structural":
        errors.append("UnsupportedTolerance:structural")

    return VerifyResult(verified=(len(errors) == 0), errors=errors, warnings=warnings)
