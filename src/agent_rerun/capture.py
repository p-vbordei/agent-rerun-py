"""Build a v0.1 bundle from a step record, optionally signing it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .hash import sha256_of_jcs
from .schema import Bundle, StepRecord, validate_bundle, validate_step_record
from .sign import sign_bundle


@dataclass(frozen=True)
class CaptureOptions:
    """If `signing_key` is provided (32-byte Ed25519), the returned bundle is signed."""

    signing_key: bytes | None = None


def capture(input_step: StepRecord, opts: CaptureOptions | None = None) -> Bundle:
    """Build a `rerun.json` v0.1 bundle from a step record, optionally signing it."""
    if opts is None:
        opts = CaptureOptions()
    step = validate_step_record(input_step)

    inputs_block: dict[str, Any] = {
        "system_prompt_sha256": sha256_of_jcs(step["inputs"]["system_prompt"]),
        "messages_sha256": sha256_of_jcs(step["inputs"]["messages"]),
    }
    if "tools" in step["inputs"] and step["inputs"]["tools"] is not None:
        inputs_block["tools_sha256"] = sha256_of_jcs(step["inputs"]["tools"])

    expected_block: dict[str, Any] = {}
    if "transcript" in step["expected"] and step["expected"]["transcript"] is not None:
        expected_block["transcript_sha256"] = sha256_of_jcs(step["expected"]["transcript"])
    if (
        "semantic_embedding" in step["expected"]
        and step["expected"]["semantic_embedding"] is not None
    ):
        expected_block["semantic_embedding"] = step["expected"]["semantic_embedding"]

    bundle: Bundle = {  # type: ignore[assignment]
        "rerun_version": "0.1",
        "model": step["model"],
        "sampling": step["sampling"],
        "inputs": inputs_block,
        "runtime": step["runtime"],
        "expected": expected_block,
        "tolerance": step["tolerance"],
    }

    validated = validate_bundle(bundle)
    return sign_bundle(validated, opts.signing_key) if opts.signing_key else validated
