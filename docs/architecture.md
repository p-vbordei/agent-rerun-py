# Architecture — agent-rerun (Python)

## Goal

Port the [`agent-rerun` v0.1 spec](../SPEC.md) to idiomatic Python. The port is **byte-determinism-compatible** with the [TypeScript reference](https://github.com/p-vbordei/agent-rerun): given the same step record and signing key, both implementations produce the same JCS-canonical bundle bytes and the same Ed25519 signature, and both accept/reject the shared conformance vectors identically.

## Module map

The Python package mirrors the TS reference module-for-module so changes in either repo are easy to cross-reference.

| Python (`src/agent_rerun/`) | TS reference (`src/`) | Responsibility |
|---|---|---|
| `jcs.py` | `jcs.ts` | RFC 8785 JCS bytes via the `jcs` PyPI package. |
| `hash.py` | `hash.ts` | `sha256:<hex>` of arbitrary bytes / of JCS bytes. |
| `cosine.py` | `cosine.ts` | float32 base64 codec + cosine similarity. |
| `schema.py` | `schema.ts` (Zod) | Hand-rolled strict validation for bundle / actual / step records. |
| `sign.py` | `sign.ts` | Ed25519 sign/verify of JCS-canonical bundle bytes (signature field stripped). |
| `capture.py` | `capture.ts` | Step record → bundle, optional sign. |
| `verify.py` | `verify.ts` | Bundle + actual record → `VerifyResult { verified, errors, warnings }`. |
| `cli.py` | `cli.ts` | `rerun capture` and `rerun verify` subcommands. |

## Dependency choices

- **`cryptography>=42`** for Ed25519. Battle-tested, audited, wheels on every supported platform. No optional dependency dance.
- **`jcs>=0.2.1`** for RFC 8785 canonicalization. Independent implementation from the TS path, which is precisely what we want for a conformance port.
- **No schema library.** Re-implementing strict validation in `schema.py` (~150 LoC) is cheaper than pulling in `pydantic` and arguing with its coercion rules. The TS reference uses Zod's `.strict()`; we mirror its semantics directly.
- **Stdlib-only CLI.** No `click` / `typer`. The CLI has two subcommands and four flags total.

## Byte-determinism invariants

Two implementations are interoperable iff they agree on:

1. **JCS bytes.** Both repos delegate to a maintained RFC 8785 implementation (`jcs` on PyPI, `safe-stable-stringify` + ECMA-262 number rules in TS). The Python `jcs` library matches the TS path byte-for-byte for every schema-valid bundle in v0.1 (no integers above 2^53 by construction — see "Schema bounds" below).
2. **Hash format.** Always `sha256:<64-lower-hex>`. The `sha256:` prefix is part of the string. There is no separate "raw digest" path.
3. **Signature payload.** Ed25519 signs `JCS(bundle without "signature")`. The `signature` field is removed *before* canonicalization, then re-attached. This is the only ordering of operations that survives JSON key reordering.
4. **Embedding encoding.** Little-endian float32 base64. `encode_embedding` / `decode_embedding` round-trip; `test_float32_endianness_is_little` pins the format.

## Schema bounds (why no number normalization is needed)

The bundle schema in v0.1 only admits integers for `sampling.seed`, `sampling.max_tokens`, and inside user-defined `messages`/`tools` arrays. All hash and embedding fields are strings. In practice we have not seen a vector that exercises the 2^53 boundary, so the Python port does not run the `normalize_numbers` walker that the Rust port uses defensively. If a v0.2 spec change exposes large integers, the port will adopt the same coercion path.

## Testing strategy

`uv run pytest -v`:

- **11 conformance vectors** in `tests/test_conformance.py`. Each `vectors/<name>/` directory carries the same `bundle.rr`, `actual.json`, `expected.json` triple as the TS reference. The test asserts `verified` plus every substring listed under `errorContains[]` / `warningContains[]`.
- **26 unit tests** in `tests/test_unit.py` covering JCS, hashing, cosine + embeddings, signing roundtrip, schema strictness on all three record types, byte/semantic/structural tolerance, fingerprint drift, tools-hash variants, fixed-key signing, and float32 endianness.

Full suite under 100 ms on a 2023 M3.

## CLI determinism

`rerun capture step.json -o bundle.rr` writes `jcs_bytes(bundle)` directly — no `json.dumps`, no trailing newline. The bytes on disk are exactly what `verify_bundle_signature` reads back. This is the single point where "byte-deterministic" becomes a property of the file system, not just the in-memory value.
