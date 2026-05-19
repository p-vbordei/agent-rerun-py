# agent-rerun (Python)

[![CI](https://github.com/p-vbordei/agent-rerun-py/actions/workflows/ci.yml/badge.svg)](https://github.com/p-vbordei/agent-rerun-py/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/agent-rerun)](https://pypi.org/project/agent-rerun/)
[![Spec](https://img.shields.io/badge/spec-v0.1-blue)](./SPEC.md)
[![License](https://img.shields.io/badge/license-Apache%202.0-green)](./LICENSE)

> **Idiomatic Python port of [@p-vbordei/agent-rerun](https://github.com/p-vbordei/agent-rerun).** Portable reproducibility seed bundle for AI-agent steps — capture every input that determines an output, share the bundle, verify it elsewhere. Byte-deterministic-compatible with the TS reference; passes the same conformance vectors.

## What's in the box

- `capture(step, opts)` — step record → JCS-canonical `rerun.json` v0.1 bundle, optionally signed.
- `verify(bundle, actual)` — bundle + actual record → `VerifyResult { verified, errors, warnings }`. Enforces byte / semantic tolerances, fingerprint drift warnings, schema strictness.
- `sign_bundle`, `verify_bundle_signature`, `generate_key_pair` — raw 32-byte Ed25519 over `JCS(bundle without "signature")`.
- `cosine`, `encode_embedding`, `decode_embedding` — little-endian float32 base64 codec + cosine similarity for semantic tolerance.
- `sha256_hex`, `sha256_of_jcs`, `jcs_bytes` — RFC 8785 canonicalization and the `sha256:<hex>` format used throughout the spec.
- `rerun capture` / `rerun verify` — stdlib-only CLI. Exit `0` on pass, `1` on fail.

## Install

```bash
pip install agent-rerun
```

## Quickstart

```python
from agent_rerun import CaptureOptions, capture, generate_key_pair, jcs_bytes, sha256_hex, verify

kp = generate_key_pair()
step = {
    "model": {"vendor": "anthropic", "id": "claude-opus-4-7"},
    "sampling": {"temperature": 0, "top_p": 1, "seed": 42},
    "inputs": {"system_prompt": "you are a helpful assistant",
               "messages": [{"role": "user", "content": "say hi"}]},
    "runtime": {"class": "cloud"},
    "expected": {"transcript": {"messages": [{"role": "assistant", "content": "hi"}]}},
    "tolerance": {"level": "byte"},
}

bundle = capture(step, CaptureOptions(signing_key=kp.private_key))
print("CID:", sha256_hex(jcs_bytes(bundle)))

actual = {"inputs": step["inputs"], "output": {"transcript": step["expected"]["transcript"]}}
print("verified:", verify(bundle, actual).verified)
```

Run it:

```bash
uv run python examples/quickstart.py
# bundle bytes : 673
# bundle CID   : sha256:a93141461f4aae88192255d911f5b4e61f2e59b736706897faad562140fe629d
# original     : PASS
# tampered     : FAIL (BadSignature:signature does not match payload)
```

## How it relates

| Repo | Language | Status |
|---|---|---|
| [`agent-rerun`](https://github.com/p-vbordei/agent-rerun) | TypeScript | Reference (source of truth). |
| [`agent-rerun-py`](https://github.com/p-vbordei/agent-rerun-py) | Python | This port (PyPI). |
| [`agent-rerun-rs`](https://github.com/p-vbordei/agent-rerun-rs) | Rust | Sibling port. |

## Conformance

```bash
uv sync --extra dev && uv run pytest -v
```

Verified against the same fixture set as the TypeScript reference. Each `vectors/<name>/` directory carries a `bundle.rr`, `actual.json`, and `expected.json` — `verify()` output must match (`verified` flag plus every substring in `errorContains[]` / `warningContains[]`).

| Clause | Vector | Behaviour |
|---|---|---|
| C1 | `c1-byte-replay-passes` | Signed bundle + matching actual + byte tolerance → pass. |
| C2 | `c2-semantic-replay-passes` | Signed bundle + cosine ≥ threshold → pass. |
| C3 | `c3-mutated-bundle-rejected` | Edited bundle after signing → fail with `BadSignature`. |
| C4 | `c4-messages-mismatch-rejected` | Actual carries different messages → fail with `InputHashMismatch`. |

Plus seven bonus vectors covering schema strictness, embedding-dim mismatch, structural-unsupported, and fingerprint drift.

## Architecture

See [docs/architecture.md](docs/architecture.md).

## Development

```bash
git clone https://github.com/p-vbordei/agent-rerun-py
cd agent-rerun-py
uv sync --extra dev
uv run pytest -v
```

## License

Apache-2.0 — see [LICENSE](./LICENSE).
