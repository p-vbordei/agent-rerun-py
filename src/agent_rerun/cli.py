"""CLI: `rerun capture` and `rerun verify`."""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from typing import Any

from .capture import CaptureOptions, capture
from .jcs import jcs_bytes
from .schema import ValidationError, validate_step_record
from .verify import verify

USAGE = """agent-rerun v0.1

Usage:
  rerun capture <step.json> -o <bundle.rr> [--key <key.json>]
    Read a step record, write a bundle. With --key, sign with the Ed25519 private
    key in the file (JSON: { "privateKey": "<base64>" }).

  rerun verify <bundle.rr> <actual.json>
    Verify the actual record against the bundle. Exit 0 on pass, 1 on fail.
    Prints a JSON result: { verified, errors, warnings }.
"""


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        sys.stderr.write(USAGE)
        return 1
    cmd, rest = args[0], args[1:]
    try:
        if cmd == "capture":
            return _capture_cmd(rest)
        if cmd == "verify":
            return _verify_cmd(rest)
        sys.stderr.write(USAGE)
        return 1
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"{e}\n")
        return 1


def _capture_cmd(args: list[str]) -> int:
    opts = _parse_args(args, ["-o", "--key"])
    if not opts.positional or "-o" not in opts.flags:
        sys.stderr.write(USAGE)
        return 1
    step_path = opts.positional[0]
    out_path = opts.flags["-o"]
    key_path = opts.flags.get("--key")
    step_json = _load_json(step_path, "step record")
    try:
        step = validate_step_record(step_json)
    except ValidationError as e:
        raise RuntimeError(f"invalid step record at {step_path}: {e}") from e
    signing_key = _load_private_key(key_path) if key_path else None
    bundle = capture(step, CaptureOptions(signing_key=signing_key))
    Path(out_path).write_bytes(jcs_bytes(bundle))
    return 0


def _verify_cmd(args: list[str]) -> int:
    if len(args) < 2:
        sys.stderr.write(USAGE)
        return 1
    bundle_path, actual_path = args[0], args[1]
    bundle = _load_json(bundle_path, "bundle")
    actual = _load_json(actual_path, "actual record")
    result = verify(bundle, actual)
    sys.stdout.write(
        json.dumps(
            {
                "verified": result.verified,
                "errors": result.errors,
                "warnings": result.warnings,
            },
            indent=2,
        )
        + "\n"
    )
    return 0 if result.verified else 1


def _load_json(path: str, label: str) -> Any:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        raise RuntimeError(f"cannot read {label} at {path}: {e}") from e
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"invalid JSON in {label} at {path}: {e}") from e


def _load_private_key(path: str) -> bytes:
    content = _load_json(path, "key file")
    if not isinstance(content, dict) or not isinstance(content.get("privateKey"), str):
        raise RuntimeError(f"key file at {path} is missing a base64 `privateKey` field")
    return base64.b64decode(content["privateKey"], validate=False)


class _ParsedArgs:
    def __init__(self) -> None:
        self.positional: list[str] = []
        self.flags: dict[str, str] = {}


def _parse_args(argv: list[str], flags: list[str]) -> _ParsedArgs:
    out = _ParsedArgs()
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in flags:
            if i + 1 >= len(argv):
                raise RuntimeError(f"flag {a} requires a value")
            out.flags[a] = argv[i + 1]
            i += 2
        else:
            out.positional.append(a)
            i += 1
    return out


if __name__ == "__main__":
    sys.exit(main())
