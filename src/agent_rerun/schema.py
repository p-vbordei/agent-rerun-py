"""Schema validation for the agent-rerun bundle, actual record, and step record.

The TS reference uses Zod with `.strict()` (unknown keys rejected) and `superRefine`
for conditional requirements. This module reimplements that logic without a third-party
schema library so the dependency surface stays small.
"""

from __future__ import annotations

import re
from typing import Any, Literal, TypedDict

# Type aliases for clarity. We use TypedDict only for documentation; runtime
# validation goes through the explicit checkers below.

ToleranceLevel = Literal["byte", "semantic", "structural"]
RuntimeClass = Literal["cloud", "local-vllm", "local-transformers"]


class Signature(TypedDict):
    alg: Literal["ed25519"]
    pubkey: str
    sig: str


class Bundle(TypedDict, total=False):
    rerun_version: Literal["0.1"]
    model: dict[str, Any]
    sampling: dict[str, Any]
    inputs: dict[str, Any]
    runtime: dict[str, Any]
    expected: dict[str, Any]
    tolerance: dict[str, Any]
    signature: Signature


class ActualRecord(TypedDict, total=False):
    inputs: dict[str, Any]
    output: dict[str, Any]
    runtime: dict[str, Any]


class StepRecord(TypedDict, total=False):
    model: dict[str, Any]
    sampling: dict[str, Any]
    inputs: dict[str, Any]
    runtime: dict[str, Any]
    expected: dict[str, Any]
    tolerance: dict[str, Any]


_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class ValidationError(Exception):
    """Raised when schema validation fails. The message mirrors a Zod-style report."""


def _is_int(x: Any) -> bool:
    # bool is a subclass of int — exclude it explicitly.
    return isinstance(x, int) and not isinstance(x, bool)


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _require_keys(obj: Any, required: set[str], allowed: set[str], path: str) -> None:
    if not isinstance(obj, dict):
        raise ValidationError(f"{path}: expected object, got {type(obj).__name__}")
    extra = set(obj.keys()) - allowed
    if extra:
        raise ValidationError(f"{path}: unrecognized key(s) {sorted(extra)}")
    missing = required - set(obj.keys())
    if missing:
        raise ValidationError(f"{path}: missing required key(s) {sorted(missing)}")


def _sha256(s: Any, path: str) -> None:
    if not isinstance(s, str) or not _SHA256_RE.match(s):
        raise ValidationError(f"{path}: expected sha256:<64-hex>")


def _validate_model(model: Any, path: str) -> None:
    _require_keys(model, {"vendor", "id"}, {"vendor", "id", "fingerprint"}, path)
    if not (isinstance(model["vendor"], str) and len(model["vendor"]) >= 1):
        raise ValidationError(f"{path}.vendor: non-empty string required")
    if not (isinstance(model["id"], str) and len(model["id"]) >= 1):
        raise ValidationError(f"{path}.id: non-empty string required")
    if "fingerprint" in model and not isinstance(model["fingerprint"], str):
        raise ValidationError(f"{path}.fingerprint: string required")


def _validate_sampling(sampling: Any, path: str) -> None:
    _require_keys(
        sampling,
        {"temperature", "top_p"},
        {"temperature", "top_p", "seed", "max_tokens"},
        path,
    )
    if not _is_number(sampling["temperature"]):
        raise ValidationError(f"{path}.temperature: number required")
    if not _is_number(sampling["top_p"]):
        raise ValidationError(f"{path}.top_p: number required")
    if "seed" in sampling and not _is_int(sampling["seed"]):
        raise ValidationError(f"{path}.seed: integer required")
    if "max_tokens" in sampling:
        if not _is_int(sampling["max_tokens"]) or sampling["max_tokens"] <= 0:
            raise ValidationError(f"{path}.max_tokens: positive integer required")


def _validate_runtime(runtime: Any, path: str) -> None:
    _require_keys(runtime, {"class"}, {"class", "tool_versions"}, path)
    if runtime["class"] not in ("cloud", "local-vllm", "local-transformers"):
        raise ValidationError(
            f"{path}.class: must be one of 'cloud' | 'local-vllm' | 'local-transformers'"
        )
    if "tool_versions" in runtime:
        tv = runtime["tool_versions"]
        if not isinstance(tv, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in tv.items()
        ):
            raise ValidationError(f"{path}.tool_versions: record of string→string required")


def _validate_tolerance(tolerance: Any, path: str) -> None:
    _require_keys(tolerance, {"level"}, {"level", "threshold"}, path)
    if tolerance["level"] not in ("byte", "semantic", "structural"):
        raise ValidationError(f"{path}.level: must be one of 'byte' | 'semantic' | 'structural'")
    if "threshold" in tolerance and not _is_number(tolerance["threshold"]):
        raise ValidationError(f"{path}.threshold: number required")


def _validate_signature(sig: Any, path: str) -> None:
    _require_keys(sig, {"alg", "pubkey", "sig"}, {"alg", "pubkey", "sig"}, path)
    if sig["alg"] != "ed25519":
        raise ValidationError(f"{path}.alg: must be 'ed25519'")
    if not (isinstance(sig["pubkey"], str) and len(sig["pubkey"]) >= 1):
        raise ValidationError(f"{path}.pubkey: non-empty string required")
    if not (isinstance(sig["sig"], str) and len(sig["sig"]) >= 1):
        raise ValidationError(f"{path}.sig: non-empty string required")


def validate_bundle(bundle: Any) -> Bundle:
    """Validate a bundle against the v0.1 schema. Raises ValidationError on failure."""
    allowed = {
        "rerun_version",
        "model",
        "sampling",
        "inputs",
        "runtime",
        "expected",
        "tolerance",
        "signature",
    }
    required = {
        "rerun_version",
        "model",
        "sampling",
        "inputs",
        "runtime",
        "expected",
        "tolerance",
    }
    _require_keys(bundle, required, allowed, "bundle")
    if bundle["rerun_version"] != "0.1":
        raise ValidationError("bundle.rerun_version: must be '0.1'")
    _validate_model(bundle["model"], "bundle.model")
    _validate_sampling(bundle["sampling"], "bundle.sampling")

    inputs = bundle["inputs"]
    _require_keys(
        inputs,
        {"system_prompt_sha256", "messages_sha256"},
        {"system_prompt_sha256", "messages_sha256", "tools_sha256"},
        "bundle.inputs",
    )
    _sha256(inputs["system_prompt_sha256"], "bundle.inputs.system_prompt_sha256")
    _sha256(inputs["messages_sha256"], "bundle.inputs.messages_sha256")
    if "tools_sha256" in inputs:
        _sha256(inputs["tools_sha256"], "bundle.inputs.tools_sha256")

    _validate_runtime(bundle["runtime"], "bundle.runtime")

    expected = bundle["expected"]
    _require_keys(
        expected,
        set(),
        {"transcript_sha256", "semantic_embedding"},
        "bundle.expected",
    )
    if "transcript_sha256" in expected:
        _sha256(expected["transcript_sha256"], "bundle.expected.transcript_sha256")
    if "semantic_embedding" in expected and not isinstance(expected["semantic_embedding"], str):
        raise ValidationError("bundle.expected.semantic_embedding: string required")

    _validate_tolerance(bundle["tolerance"], "bundle.tolerance")

    # Conditional requirements (Zod superRefine mirror).
    if bundle["tolerance"]["level"] == "byte" and "transcript_sha256" not in expected:
        raise ValidationError(
            "bundle.expected.transcript_sha256: byte tolerance requires expected.transcript_sha256"
        )
    if bundle["tolerance"]["level"] == "semantic":
        if "semantic_embedding" not in expected:
            raise ValidationError(
                "bundle.expected.semantic_embedding: semantic tolerance requires "
                "expected.semantic_embedding"
            )
        if "threshold" not in bundle["tolerance"]:
            raise ValidationError(
                "bundle.tolerance.threshold: semantic tolerance requires tolerance.threshold"
            )

    if "signature" in bundle:
        _validate_signature(bundle["signature"], "bundle.signature")
    return bundle  # type: ignore[return-value]


def validate_actual_record(actual: Any) -> ActualRecord:
    """Validate an actual record. Raises ValidationError on failure."""
    _require_keys(actual, {"inputs", "output"}, {"inputs", "output", "runtime"}, "actual")
    inputs = actual["inputs"]
    _require_keys(
        inputs,
        {"system_prompt", "messages"},
        {"system_prompt", "messages", "tools"},
        "actual.inputs",
    )
    if not isinstance(inputs["system_prompt"], str):
        raise ValidationError("actual.inputs.system_prompt: string required")
    if not isinstance(inputs["messages"], list):
        raise ValidationError("actual.inputs.messages: array required")
    if "tools" in inputs and not isinstance(inputs["tools"], list):
        raise ValidationError("actual.inputs.tools: array required")
    output = actual["output"]
    _require_keys(output, set(), {"transcript", "embedding"}, "actual.output")
    if "embedding" in output and not isinstance(output["embedding"], str):
        raise ValidationError("actual.output.embedding: string required")
    if "runtime" in actual:
        rt = actual["runtime"]
        _require_keys(rt, set(), {"fingerprint"}, "actual.runtime")
        if "fingerprint" in rt and not isinstance(rt["fingerprint"], str):
            raise ValidationError("actual.runtime.fingerprint: string required")
    return actual  # type: ignore[return-value]


def validate_step_record(step: Any) -> StepRecord:
    """Validate a step record (input to capture). Raises ValidationError on failure."""
    _require_keys(
        step,
        {"model", "sampling", "inputs", "runtime", "expected", "tolerance"},
        {"model", "sampling", "inputs", "runtime", "expected", "tolerance"},
        "step",
    )
    _validate_model(step["model"], "step.model")
    _validate_sampling(step["sampling"], "step.sampling")
    inputs = step["inputs"]
    _require_keys(
        inputs,
        {"system_prompt", "messages"},
        {"system_prompt", "messages", "tools"},
        "step.inputs",
    )
    if not isinstance(inputs["system_prompt"], str):
        raise ValidationError("step.inputs.system_prompt: string required")
    if not isinstance(inputs["messages"], list):
        raise ValidationError("step.inputs.messages: array required")
    if "tools" in inputs and not isinstance(inputs["tools"], list):
        raise ValidationError("step.inputs.tools: array required")
    _validate_runtime(step["runtime"], "step.runtime")
    expected = step["expected"]
    _require_keys(expected, set(), {"transcript", "semantic_embedding"}, "step.expected")
    if "semantic_embedding" in expected and not isinstance(expected["semantic_embedding"], str):
        raise ValidationError("step.expected.semantic_embedding: string required")
    _validate_tolerance(step["tolerance"], "step.tolerance")
    return step  # type: ignore[return-value]
