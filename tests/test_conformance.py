"""Conformance suite: walk every fixture under `vectors/` and assert verify matches expected."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_rerun import verify

VECTORS = Path(__file__).resolve().parent.parent / "vectors"


def _vector_dirs() -> list[Path]:
    return sorted(p for p in VECTORS.iterdir() if p.is_dir())


@pytest.mark.parametrize("vector_dir", _vector_dirs(), ids=lambda p: p.name)
def test_vector(vector_dir: Path) -> None:
    bundle = json.loads((vector_dir / "bundle.rr").read_text(encoding="utf-8"))
    actual = json.loads((vector_dir / "actual.json").read_text(encoding="utf-8"))
    expected = json.loads((vector_dir / "expected.json").read_text(encoding="utf-8"))

    result = verify(bundle, actual)

    assert result.verified == expected["verified"], (
        f"{vector_dir.name}: expected verified={expected['verified']}, got "
        f"verified={result.verified}; errors={result.errors}; warnings={result.warnings}"
    )
    for needle in expected.get("errorContains", []):
        assert any(needle in e for e in result.errors), (
            f"{vector_dir.name}: expected error containing {needle!r}, got {result.errors}"
        )
    for needle in expected.get("warningContains", []):
        assert any(needle in w for w in result.warnings), (
            f"{vector_dir.name}: expected warning containing {needle!r}, got {result.warnings}"
        )
