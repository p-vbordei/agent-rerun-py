# agent-rerun (Python)

> **Portable reproducibility seed bundle for AI-agent steps.** Python port of [`@p-vbordei/agent-rerun`](https://github.com/p-vbordei/agent-rerun) — passes the same C1–C4 conformance vectors.

[![CI](https://github.com/p-vbordei/agent-rerun-py/actions/workflows/ci.yml/badge.svg)](https://github.com/p-vbordei/agent-rerun-py/actions/workflows/ci.yml)
[![spec: v0.1 stable](https://img.shields.io/badge/spec-v0.1%20stable-blue)](./SPEC.md)
[![license: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green)](./LICENSE)

A `rerun.json` v0.1 bundle pins the inputs, sampling parameters, and expected output of one LLM step so any compatible runtime can reproduce it within a declared tolerance. The bundle is one JSON file, JCS-canonical bytes in, Ed25519-signed out.

```python
from agent_rerun import capture, verify, CaptureOptions, generate_key_pair

kp = generate_key_pair()

step = {
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

bundle = capture(step, CaptureOptions(signing_key=kp.private_key))

actual = {
    "inputs": {"system_prompt": step["inputs"]["system_prompt"], "messages": step["inputs"]["messages"]},
    "output": {"transcript": step["expected"]["transcript"]},
}
result = verify(bundle, actual)
print("match" if result.verified else result.errors)
```

## Install

```bash
pip install agent-rerun
```

## CLI

```bash
rerun capture step.json -o bundle.rr [--key key.json]
rerun verify bundle.rr actual.json
```

Exit `0` on pass, `1` on fail. Result is `{ "verified", "errors", "warnings" }` JSON on stdout.

## Why this exists

OpenAI's `seed` is best-effort. vLLM determinism is runtime-specific. SLSA proves builds, not LLM outputs. There was no vendor-agnostic envelope for an LLM step's inputs, params, and expected output you can sign, share, and verify on a different runtime within a declared tolerance. `agent-rerun` is that envelope. See the TS reference [README](https://github.com/p-vbordei/agent-rerun#readme) for the full landscape.

## Conformance

This port is verified against the same fixture set as the TypeScript reference. Each `vectors/<name>/` directory carries a `bundle.rr` (JCS-canonical bytes), an `actual.json`, and an `expected.json`. The Python `verify()` output must match `expected.json` (verified flag plus every substring in `errorContains[]` / `warningContains[]`).

```bash
uv sync --extra dev
uv run pytest -v
```

| Clause | Vector | Behavior |
|---|---|---|
| C1 | `c1-byte-replay-passes` | Signed bundle + matching actual + byte tolerance → pass. |
| C2 | `c2-semantic-replay-passes` | Signed bundle + cosine ≥ threshold → pass. |
| C3 | `c3-mutated-bundle-rejected` | Edited bundle after signing → fail with BadSignature. |
| C4 | `c4-messages-mismatch-rejected` | Actual carries different messages → fail with InputHashMismatch. |

Plus seven bonus vectors covering schema strictness, embedding dim mismatch, structural-unsupported, and fingerprint drift.

## Where it fits

- [`agent-rerun`](https://github.com/p-vbordei/agent-rerun) — TS reference (this port's source of truth).
- [`agent-rerun-rs`](https://github.com/p-vbordei/agent-rerun-rs) — Rust port (same vectors).
- [`agent-scroll-py`](https://github.com/p-vbordei/agent-scroll-py) — canonical transcript hashed into `expected.transcript_sha256`.

## License

Apache 2.0 — see [LICENSE](./LICENSE).
