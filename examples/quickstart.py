"""agent-rerun quickstart: capture a step, sign it, verify, then tamper.

Run with:
    uv run python examples/quickstart.py
"""

from __future__ import annotations

from agent_rerun import CaptureOptions, capture, generate_key_pair, jcs_bytes, sha256_hex, verify

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
bundle_bytes = jcs_bytes(bundle)
bundle_cid = sha256_hex(bundle_bytes)
print(f"bundle bytes : {len(bundle_bytes)}")
print(f"bundle CID   : {bundle_cid}")

actual = {
    "inputs": step["inputs"],
    "output": {"transcript": step["expected"]["transcript"]},
}

result = verify(bundle, actual)
print(f"original     : {'PASS' if result.verified else 'FAIL'}")
assert result.verified, result.errors

tampered = dict(bundle)
tampered["sampling"] = {**bundle["sampling"], "temperature": 0.7}
tampered_result = verify(tampered, actual)
status = "PASS" if tampered_result.verified else f"FAIL ({tampered_result.errors[0]})"
print(f"tampered     : {status}")
assert not tampered_result.verified
