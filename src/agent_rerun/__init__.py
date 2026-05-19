"""agent-rerun — portable reproducibility seed bundle for AI-agent steps."""

from .capture import CaptureOptions, capture
from .cosine import cosine, decode_embedding, encode_embedding
from .hash import sha256_hex, sha256_of_jcs
from .jcs import jcs_bytes
from .schema import (
    ActualRecord,
    Bundle,
    Signature,
    StepRecord,
    ToleranceLevel,
    validate_actual_record,
    validate_bundle,
    validate_step_record,
)
from .sign import KeyPair, generate_key_pair, sign_bundle, verify_bundle_signature
from .verify import VerifyResult, verify

__all__ = [
    "ActualRecord",
    "Bundle",
    "CaptureOptions",
    "KeyPair",
    "Signature",
    "StepRecord",
    "ToleranceLevel",
    "VerifyResult",
    "capture",
    "cosine",
    "decode_embedding",
    "encode_embedding",
    "generate_key_pair",
    "jcs_bytes",
    "sha256_hex",
    "sha256_of_jcs",
    "sign_bundle",
    "validate_actual_record",
    "validate_bundle",
    "validate_step_record",
    "verify",
    "verify_bundle_signature",
]
