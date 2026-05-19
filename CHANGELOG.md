# Changelog

All notable changes to `agent-rerun` (Python) are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses [Semantic Versioning](https://semver.org).

The **format version** (`rerun_version` inside a bundle) and the **package version** are tracked independently. This port targets `rerun.json` v0.1.

## [Unreleased]

## [0.1.0] — 2026-05-19

### Added

- Initial Python port of [`@p-vbordei/agent-rerun`](https://github.com/p-vbordei/agent-rerun) v0.1.
- `capture`, `verify`, `sign_bundle`, `verify_bundle_signature`, `generate_key_pair`, `cosine`, `encode_embedding`, `decode_embedding`, `sha256_hex`, `sha256_of_jcs`, `jcs_bytes`, and the bundle / actual / step record validators.
- `rerun` CLI: `capture` and `verify` subcommands. Exit `0` on pass, `1` on fail.
- All 11 conformance vectors from the TS reference pass (C1–C4 plus seven bonus negatives covering schema strictness, embedding-dim mismatch, structural-unsupported, fingerprint drift).
- 37 tests total (11 conformance, 26 unit). Full suite under 100 ms.

[Unreleased]: https://github.com/p-vbordei/agent-rerun-py/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/p-vbordei/agent-rerun-py/releases/tag/v0.1.0
