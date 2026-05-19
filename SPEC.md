# agent-rerun — v0.1 specification

**Status:** stable. Reference implementation at v0.1.0. See [CHANGELOG.md](./CHANGELOG.md) for the release log.

## Contents

- [Abstract](#abstract)
- [1. Terminology](#1-terminology)
- [2. Bundle schema](#2-bundle-schema)
- [3. Tolerance levels](#3-tolerance-levels)
- [4. Operations](#4-operations)
- [5. Actual record shape](#5-actual-record-shape)
- [6. Security considerations](#6-security-considerations)
- [7. Conformance](#7-conformance)
- [8. References](#8-references)

## Abstract

`agent-rerun` defines a portable JSON bundle that pins the inputs, sampling parameters, and expected output of a single AI-agent step. Given the bundle and the original inputs, any compatible runtime should reproduce the output within a declared tolerance.

The bundle composes existing primitives — RFC 8785 JCS for canonical encoding, SHA-256 for content hashing, Ed25519 for optional signing — and adds nothing novel. The contribution is the envelope shape and the conformance rules around it.

## 1. Terminology

- **Step** — one LLM request/response, possibly including tool calls and results.
- **Bundle** — the JSON envelope pinning inputs + params + expected output + signature.
- **Actual record** — a JSON document representing one performed step, supplied to `verify` alongside a bundle.
- **Tolerance** — the strictness level used when comparing the actual record's output to the bundle's expected output.
- **Embedder** — a model used to produce a fixed-dimensional vector from text for semantic comparison. Default: `sentence-transformers/all-MiniLM-L6-v2` (384 dims).

## 2. Bundle schema

A bundle is a JSON object with the keys below. Keys marked `?` are optional. All hashes are `sha256:<hex>` over the JCS encoding of the source value.

```
{
  "rerun_version": "0.1",
  "model": {
    "vendor": "anthropic" | "openai" | "google" | "local-vllm" | ...,
    "id": "<model id>",                     // e.g. "claude-opus-4-7"
    "fingerprint?": "<vendor system fingerprint>"
  },
  "sampling": {
    "temperature": <number>,
    "top_p":       <number>,
    "seed?":       <int>,
    "max_tokens?": <int>
  },
  "inputs": {
    "system_prompt_sha256": "sha256:<hex>",
    "messages_sha256":      "sha256:<hex>",   // over JCS(messages array)
    "tools_sha256?":        "sha256:<hex>"    // over JCS(tool schemas array)
  },
  "runtime": {
    "class": "cloud" | "local-vllm" | "local-transformers",
    "tool_versions?": { "python": "3.12.3", ... }
  },
  "expected": {
    "transcript_sha256?":  "sha256:<hex>",     // over JCS of a scroll-canonical transcript
    "semantic_embedding?": "<base64 float32>"  // for semantic comparison
  },
  "tolerance": {
    "level":     "byte" | "semantic" | "structural",
    "threshold?": <number>                     // e.g. 0.98 for cosine similarity
  },
  "signature?": {
    "alg":    "ed25519",
    "pubkey": "<base64>",
    "sig":    "<base64>"                       // over JCS(bundle without "signature")
  }
}
```

**Required keys:** `rerun_version`, `model.vendor`, `model.id`, `sampling.temperature`, `sampling.top_p`, `inputs.system_prompt_sha256`, `inputs.messages_sha256`, `runtime.class`, `tolerance.level`.

**Conditional requirements:**
- If `tolerance.level == "byte"`, `expected.transcript_sha256` MUST be present.
- If `tolerance.level == "semantic"`, `expected.semantic_embedding` and `tolerance.threshold` MUST be present.

**Encoding.** Implementations MUST produce JCS-encoded bytes when computing any hash or signature. Numeric and string serialization follows RFC 8785 (sorted keys, no insignificant whitespace, IEEE 754 number formatting).

**Strictness.** Implementations MUST reject bundles that contain unknown fields at any level defined in this section. Forward-compatible extensions are introduced via a `rerun_version` bump, not by smuggling unknown fields into a v0.1 bundle. The same rule applies to the actual-record shape (§5).

## 3. Tolerance levels

- **`byte`** — `actual.transcript_sha256 == expected.transcript_sha256`. Achievable for `temperature=0` on deterministic runtimes (e.g. vLLM with batch-invariant kernels). Expected to fail cross-vendor; that is a feature, not a bug.
- **`semantic`** — `cosine(embed(actual), embed(expected)) >= threshold`. Both `bundle.expected.semantic_embedding` and `actual.output.embedding` MUST be precomputed by the **same embedder**. The default embedder for v0.1 is `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional float32, base64-encoded little-endian).
- **`structural`** — tool-call graph match: same tools called in same order with same `args_hash`, but message bodies may differ. Useful when bodies are high-temperature prose. v0.1 reference implementations MAY return "unsupported" for this level; v0.2 makes it required.

## 4. Operations

### 4.1 Capture

```
rerun capture <step.json> -o bundle.rr
```

`step.json` is one LLM step containing model, sampling, inputs, expected output, and tolerance choice. `capture` JCS-canonicalizes each input field, computes SHA-256 hashes, packages the bundle, and (optionally) signs with an Ed25519 key.

### 4.2 Apply

```
rerun apply bundle.rr --inputs step-inputs.json --runtime=<vendor>
```

Re-executes the step against the configured runtime and emits a new actual record. Because the bundle stores hashes only, the original inputs MUST be supplied separately. The v0.1 reference implementation does not ship `apply`; callers replay manually with their vendor SDK and pipe the output to `verify`.

### 4.3 Verify

```
rerun verify bundle.rr actual.json
```

Compares `actual.json` against `bundle.expected` using `bundle.tolerance` per the rules in §5. Exit code `0` on pass, `1` on fail. Prints per-rule verdict (schema, signature, input hashes, tolerance comparison).

## 5. Actual record shape

An **actual record** is the JSON document supplied to `verify` alongside a bundle. It carries the inputs that were actually sent to the runtime and the output that was produced.

```
{
  "inputs": {
    "system_prompt": "<verbatim text>",
    "messages":      [...],                 // verbatim messages supplied to the runtime
    "tools?":        [...]                  // verbatim tool schemas supplied
  },
  "output": {
    "transcript?":   {...},                 // scroll-canonical produced transcript
    "embedding?":    "<base64 float32>"     // precomputed embedding for semantic tolerance
  },
  "runtime?": {
    "fingerprint?": "<vendor system fingerprint at replay time>"
  }
}
```

`verify` MUST:

1. Validate the bundle and actual record against this schema; reject on schema violation.
2. Recompute `sha256(JCS(actual.inputs.system_prompt))` and compare to `bundle.inputs.system_prompt_sha256`. Reject on mismatch.
3. Recompute `sha256(JCS(actual.inputs.messages))` and compare to `bundle.inputs.messages_sha256`. Reject on mismatch (C4).
4. If `bundle.inputs.tools_sha256` is present, recompute the tools hash and compare. Reject on mismatch.
5. If `bundle.signature` is present, verify the Ed25519 signature over `JCS(bundle without "signature")`. Reject on invalid signature (C3).
6. Apply the tolerance check per `bundle.tolerance.level`:
   - **`byte`**: `sha256(JCS(actual.output.transcript)) == bundle.expected.transcript_sha256`.
   - **`semantic`**: `cosine(decode(actual.output.embedding), decode(bundle.expected.semantic_embedding)) >= bundle.tolerance.threshold`.
   - **`structural`**: as defined in v0.2 (v0.1 returns unsupported).

`verify` returns a structured result enumerating the verdict for each rule above.

## 6. Security considerations

- **Signatures are advisory**, not authoritative. A signed bundle tells you who claims these expected outputs; it does not guarantee the model will produce them.
- **Fingerprint drift**: when `bundle.model.fingerprint` is set and `actual.runtime.fingerprint` is set and they differ, verifiers MUST emit a `FingerprintDrift` warning. The warning is informational and does not flip `verified` — the tolerance check decides. (In practice `byte` tolerance with drift will fail on the transcript hash anyway; `semantic` and `structural` are designed to tolerate drift.) The reference implementation emits `FingerprintDrift:bundle=<fp>,actual=<fp>`.
- **Tamper detection**: mutating bundle bytes invalidates the signature (if present). The input hashes inside the bundle protect input integrity independently of the signature; mutation of `inputs.*_sha256` is detected at the canonical-encoding/JCS layer when a verifier recomputes the hashes from the actual record.
- **Determinism is best-effort** across vendors. `byte` tolerance is expected to fail cross-vendor; that is a feature, not a bug.
- **Privacy**: bundles store hashes of inputs, not the inputs themselves. Publishing a bundle does not leak system prompts or tool args. Actual records DO contain plaintext inputs and SHOULD be treated accordingly.
- **Embedder agreement**: bundle and actual MUST use the same embedder for `semantic` tolerance. Mismatched embedders produce meaningless cosine values and SHOULD be rejected by surrounding tooling (e.g. CI configuration). v0.1 fixes the embedder to MiniLM-L6-v2; future versions may add an `embedder_id` field to the bundle.

## 7. Conformance

A conforming v0.1 implementation MUST:

- **(C1)** Capture a bundle from a step record; verify a byte-level replay (same runtime, `temperature=0`) passes.
- **(C2)** Verify a semantic replay across runtimes passes when cosine ≥ threshold (using precomputed embeddings on both sides).
- **(C3)** Verify MUST fail when bundle bytes are mutated and a signature is present (signature invalid).
- **(C4)** Verify MUST fail when `inputs.messages_sha256` does not match `sha256(JCS(actual.inputs.messages))`.

A conforming v0.1 implementation MAY:

- Return `unsupported` for `tolerance.level == "structural"` (becomes MUST in v0.2).
- Decline to ship an `apply` operation (becomes RECOMMENDED in v0.2).

Test vectors live in `conformance/`. The vectors include precomputed embeddings so conformance does not require a live embedder at test time.

## 8. References

- [`agent-scroll` spec](../agent-scroll/SPEC.md) — canonical transcript referenced by `expected.transcript_sha256`
- [`agent-id` spec](../agent-id/SPEC.md) — DID + capability VC, optional source of `signature.pubkey`
- [RFC 8785 JCS](https://www.rfc-editor.org/rfc/rfc8785) — JSON Canonicalization Scheme
- [RFC 8032 Ed25519](https://www.rfc-editor.org/rfc/rfc8032) — Edwards-curve Digital Signature Algorithm
- [SLSA v1.0 provenance](https://slsa.dev/spec/v1.0/provenance) — closest-shape prior art
- ["Defeating Nondeterminism in LLM Inference" (Thinking Machines, Sep 2025)](https://thinkingmachines.ai/) — runtime-level determinism work
