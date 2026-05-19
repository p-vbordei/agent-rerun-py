# Contributing to agent-rerun (Python)

Thanks for taking the time. This port has a narrow job: stay byte-deterministic-compatible with the [TypeScript reference](https://github.com/p-vbordei/agent-rerun) and pass the same conformance vectors. Most contributions fit into one of a few buckets — please read the relevant section before opening a PR.

## Ground rules

1. **The TS reference is the source of truth.** If you find a behavioural disagreement between this port and the TS reference, the TS behaviour wins by default. Open an issue first so we can decide whether the bug is here or there.
2. **Don't change conformance vectors locally.** Vectors live in `vectors/` and are mirrored from the TS repo. Changing them masks real divergence. If a vector looks wrong, raise it upstream.
3. **Keep the dependency surface minimal.** New runtime dependencies need a justification in the PR description — what does it buy that the stdlib + `cryptography` + `jcs` can't?

## Dev setup

```bash
git clone https://github.com/p-vbordei/agent-rerun-py
cd agent-rerun-py
uv sync --extra dev
uv run pytest -v
```

Python ≥ 3.10. No native build steps.

## Running the tools

- `uv run pytest -v` — full suite (11 conformance vectors + 26 unit tests).
- `uv run ruff check src tests examples` — lint.
- `uv run python examples/quickstart.py` — sanity-check the end-to-end roundtrip.

## What goes in a PR

- A failing test (or a failing conformance vector) before the fix.
- Symmetric updates to docstrings if a public function changes shape.
- Append an entry to `CHANGELOG.md` under `[Unreleased]`.
- One logical change per PR. Refactors and behaviour fixes don't mix well in review.

## What does NOT go in a PR

- Reformatting / reflow of files you didn't otherwise touch.
- New optional dependencies that "might be nice".
- Speculative API surface ("we might want X later").

## Reporting issues

Include:

- Python version (`python --version`).
- Minimal step record + actual record that reproduces.
- Whether you also see the issue in the TS reference (`bun examples/demo.ts`) — this drastically narrows the search.

## License

By contributing, you agree your contributions are licensed under Apache-2.0 (see [LICENSE](./LICENSE)).
