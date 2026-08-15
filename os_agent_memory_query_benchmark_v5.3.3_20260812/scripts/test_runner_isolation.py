#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ADAPTER = r'''import hashlib, json, pathlib, sys
state = []
marker = pathlib.Path("stream_marker.txt")
for line in sys.stdin:
    request = json.loads(line)
    kind = request.get("type")
    if kind == "initialize_stream":
        if marker.exists():
            raise SystemExit("cross-stream working-directory contamination")
        marker.write_text(request["stream_id"], encoding="utf-8")
        state = list(request.get("initial_memory_items", []))
        response = {"ok": True}
    elif kind == "query":
        response = {"response_text":"","selected_memory_ids":[],"supporting_event_ids":[],"predicted_action_keys":[],"predicted_operation_state_labels":[],"memory_write_delta":{"writes":[],"deletes":[]}}
    elif kind == "append_turn_history":
        response = {"ok": True}
    else:
        response = {"ok": True}
    response["state_sha256"] = hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()
    print(json.dumps(response, separators=(",", ":")), flush=True)
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    runner = args.agent_root / "scripts" / "run_online_session.py"
    with tempfile.TemporaryDirectory(prefix="runner_isolation_test_") as temporary:
        root = Path(temporary)
        adapter = root / "isolation_probe.py"
        adapter.write_text(ADAPTER, encoding="utf-8")
        key = root / "receipt.key"
        key.write_bytes(b"runner-isolation-test-key-32-bytes!!")
        trace = root / "trace.ndjson"
        system_command = f'"{sys.executable}" -B "{adapter}"'
        result = subprocess.run([
            sys.executable, "-B", str(runner), "--agent-root", str(args.agent_root),
            "--system-command", system_command, "--receipt-key-file", str(key),
            "--partition", "test", "--output", str(trace), "--max-streams", "2",
            "--query-timeout-seconds", "10",
        ], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        if result.returncode:
            raise SystemExit(result.stderr or result.stdout)
        stream_ids = {json.loads(line)["stream_id"] for line in trace.read_text(encoding="utf-8").splitlines() if line.strip()}
        if len(stream_ids) != 2:
            raise SystemExit(f"expected two isolated streams, got {len(stream_ids)}")
    print(json.dumps({"status": "pass", "isolated_streams": 2}, ensure_ascii=False))


if __name__ == "__main__":
    main()
