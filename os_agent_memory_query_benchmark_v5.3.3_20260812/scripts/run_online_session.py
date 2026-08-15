#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import hmac
import json
import os
import queue
import secrets
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
from collections import deque
from pathlib import Path

from validate_release import verify_release


SYSTEM_FIELDS = {
    "response_text", "selected_memory_ids", "supporting_event_ids", "predicted_action_keys",
    "predicted_operation_state_labels", "memory_write_delta", "recognized_active_config",
    "effective_behavior", "state_sha256",
}


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256(value) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def gz_rows(path: Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def start_stdout_reader(process: subprocess.Popen) -> queue.Queue:
    assert process.stdout
    output: queue.Queue = queue.Queue()

    def read_stdout() -> None:
        for line in process.stdout:
            output.put(line)
        output.put(None)

    threading.Thread(target=read_stdout, daemon=True).start()
    return output


def start_stderr_reader(process: subprocess.Popen) -> deque[str]:
    assert process.stderr
    lines: deque[str] = deque(maxlen=200)

    def read_stderr() -> None:
        for line in process.stderr:
            lines.append(line.rstrip())

    threading.Thread(target=read_stderr, daemon=True).start()
    return lines


def exchange(process: subprocess.Popen, payload: dict, stdout_queue: queue.Queue, stderr_lines: deque[str], timeout_seconds: float) -> dict:
    assert process.stdin and process.stdout
    process.stdin.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    process.stdin.flush()
    try:
        line = stdout_queue.get(timeout=timeout_seconds)
    except queue.Empty as exc:
        process.kill()
        process.wait(timeout=5)
        detail = "\n".join(stderr_lines)
        raise RuntimeError(f"system response timed out after {timeout_seconds:g}s: {detail}") from exc
    if not line:
        detail = "\n".join(stderr_lines)
        raise RuntimeError(f"system process ended before returning JSON: {detail}")
    response = json.loads(line)
    if not isinstance(response, dict):
        raise RuntimeError("system response must be a JSON object")
    return response


def require_string_list(value, field: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise RuntimeError(f"system field {field} must be an array of strings")
    return value


def require_string_map(value, field: str) -> dict[str, str]:
    if not isinstance(value, dict) or any(not isinstance(key, str) or not isinstance(item, str) for key, item in value.items()):
        raise RuntimeError(f"system field {field} must be an object with string values")
    return value


def validate_query_response(response: dict) -> dict:
    normalized = {
        "response_text": response.get("response_text", ""),
        "selected_memory_ids": response.get("selected_memory_ids", []),
        "supporting_event_ids": response.get("supporting_event_ids", []),
        "predicted_action_keys": response.get("predicted_action_keys", []),
        "predicted_operation_state_labels": response.get("predicted_operation_state_labels", []),
        "memory_write_delta": response.get("memory_write_delta", {"writes": [], "deletes": []}),
        "recognized_active_config": response.get("recognized_active_config", {"config_id": "", "behavior": {}}),
        "effective_behavior": response.get("effective_behavior", {"behavior": {}, "source": {}, "overridden_dimensions": []}),
        "state_sha256": response.get("state_sha256", ""),
    }
    if not isinstance(normalized["response_text"], str) or not isinstance(normalized["state_sha256"], str):
        raise RuntimeError("system response_text and state_sha256 must be strings")
    for field in ("selected_memory_ids", "supporting_event_ids", "predicted_action_keys"):
        require_string_list(normalized[field], field)

    labels = normalized["predicted_operation_state_labels"]
    if not isinstance(labels, list):
        raise RuntimeError("system field predicted_operation_state_labels must be an array")
    for index, item in enumerate(labels):
        if not isinstance(item, dict) or set(item) != {"role", "episode_id", "state"}:
            raise RuntimeError(f"predicted_operation_state_labels[{index}] must contain only role, episode_id and state")
        if any(not isinstance(item[field], str) or not item[field] for field in ("role", "episode_id", "state")):
            raise RuntimeError(f"predicted_operation_state_labels[{index}] fields must be non-empty strings")

    delta = normalized["memory_write_delta"]
    if not isinstance(delta, dict) or set(delta) - {"writes", "deletes"}:
        raise RuntimeError("system field memory_write_delta must contain only writes and deletes")
    for field in ("writes", "deletes"):
        items = delta.setdefault(field, [])
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise RuntimeError(f"memory_write_delta.{field} must be an array of objects")

    recognized = normalized["recognized_active_config"]
    if not isinstance(recognized, dict) or set(recognized) != {"config_id", "behavior"}:
        raise RuntimeError("recognized_active_config must contain only config_id and behavior")
    if not isinstance(recognized["config_id"], str):
        raise RuntimeError("recognized_active_config.config_id must be a string")
    require_string_map(recognized["behavior"], "recognized_active_config.behavior")

    effective = normalized["effective_behavior"]
    if not isinstance(effective, dict) or set(effective) != {"behavior", "source", "overridden_dimensions"}:
        raise RuntimeError("effective_behavior must contain behavior, source and overridden_dimensions")
    require_string_map(effective["behavior"], "effective_behavior.behavior")
    require_string_map(effective["source"], "effective_behavior.source")
    require_string_list(effective["overridden_dimensions"], "effective_behavior.overridden_dimensions")
    if set(effective["source"]) != set(effective["behavior"]):
        raise RuntimeError("effective_behavior.source must describe every effective behavior dimension")
    if not set(effective["overridden_dimensions"]) <= set(effective["behavior"]):
        raise RuntimeError("effective_behavior.overridden_dimensions must reference effective behavior dimensions")
    return normalized


def read_receipt_key(path: Path) -> bytes:
    value = path.read_bytes().strip()
    if len(value) < 32:
        raise ValueError("runner receipt key must contain at least 32 bytes")
    return value


def signed_trace(core: dict, key: bytes) -> dict:
    result = dict(core)
    result["runner_record_sha256"] = sha256(core)
    result["runner_chain_after_sha256"] = result["runner_record_sha256"]
    payload = canonical(result).encode("utf-8")
    result["runner_receipt_hmac_sha256"] = hmac.new(key, payload, hashlib.sha256).hexdigest()
    return result


def history_append_payload(stream_id: str, step: dict, response: dict) -> dict:
    query_id = step["query_id"]
    return {
        "type": "append_turn_history",
        "stream_id": stream_id,
        "query_id": query_id,
        "query_event": step["current_query"],
        "assistant_response_event": {
            "event_id": f"{query_id}_ASSISTANT_RESPONSE",
            "speaker": "assistant",
            "text": response.get("response_text", ""),
        },
        "memory_delta_event": {
            "event_id": f"{query_id}_MEMORY_DELTA",
            "event_type": "memory_delta",
            "delta": response.get("memory_write_delta", {"writes": [], "deletes": []}),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Judge-controlled persistent online runner. Gold files must not exist below --agent-root.")
    parser.add_argument("--agent-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--system-command", required=True, help="absolute command for a JSONL stdio adapter")
    parser.add_argument("--receipt-key-file", type=Path, required=True, help="judge-held HMAC key; never place it in the agent release")
    parser.add_argument("--partition", choices=["train", "dev", "test"], default="test")
    parser.add_argument("--runtime", default="test_dataset/runtime_streams.ndjson.gz")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-streams", type=int)
    parser.add_argument("--system-workdir", type=Path)
    parser.add_argument("--query-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--process-exit-timeout-seconds", type=float, default=5.0)
    args = parser.parse_args()

    verify_release(args.agent_root)

    forbidden = [
        args.agent_root / "test_dataset" / "answer_key.csv", args.agent_root / "judge",
        args.agent_root / "review", args.agent_root / "source_data",
    ]
    if any(path.exists() for path in forbidden):
        raise SystemExit("agent root contains judge/review/source files; use the isolated agent release")

    key = read_receipt_key(args.receipt_key_file)
    pools = {item["memory_pool_id"]: item for item in gz_rows(args.agent_root / "memory_pools" / "initial_memory_pools.ndjson.gz")}
    streams = [item for item in gz_rows(args.agent_root / args.runtime) if item["dataset_partition"] == args.partition]
    if args.max_streams:
        streams = streams[:args.max_streams]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    command_parts = shlex.split(args.system_command, posix=os.name != "nt")
    if os.name == "nt":
        command_parts = [part[1:-1] if len(part) >= 2 and part[0] == part[-1] == '"' else part for part in command_parts]
    if not Path(command_parts[0]).is_absolute():
        raise SystemExit("system-command executable must be an absolute path")

    safe_env = {
        key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP") if key in os.environ
    }
    safe_env["PYTHONIOENCODING"] = "utf-8"
    session_id = secrets.token_hex(24)
    with tempfile.TemporaryDirectory(prefix="os_agent_eval_") as temporary, args.output.open("w", encoding="utf-8", newline="\n") as output:
        workdir_root = (args.system_workdir or Path(temporary)).resolve()
        workdir_root.mkdir(parents=True, exist_ok=True)
        for stream in streams:
            child_cwd = tempfile.mkdtemp(prefix=f"stream_{stream['stream_id']}_", dir=str(workdir_root))
            process = subprocess.Popen(
                command_parts, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace", bufsize=1, env=safe_env, cwd=child_cwd,
            )
            stdout_queue = start_stdout_reader(process)
            stderr_lines = start_stderr_reader(process)
            try:
                pool = pools[stream["memory_pool_id"]]
                initialize_payload = {
                    "type": "initialize_stream", "stream_id": stream["stream_id"], "user_id": stream["user_id"],
                    "memory_pool_id": stream["memory_pool_id"], "initial_memory_items": pool["items"],
                }
                pool_sha = sha256(initialize_payload)
                reset = exchange(process, initialize_payload, stdout_queue, stderr_lines, args.query_timeout_seconds)
                system_state = reset.get("state_sha256", "")
                chain_before = sha256({"session_id": session_id, "stream_id": stream["stream_id"], "initial_pool_sha256": pool_sha})
                for step in stream["steps"]:
                    query_payload = {
                        "type": "query", "stream_id": stream["stream_id"], "query_id": step["query_id"],
                        "step_index": step["step_index"], "query_time": step["query_time"],
                        "new_raw_events": step["new_raw_events"], "current_query": step["current_query"],
                    }
                    started = time.perf_counter()
                    response = validate_query_response(exchange(process, query_payload, stdout_queue, stderr_lines, args.query_timeout_seconds))
                    latency_ms = (time.perf_counter() - started) * 1000
                    filtered = {key: response.get(key) for key in SYSTEM_FIELDS if key in response}
                    history_append = history_append_payload(stream["stream_id"], step, response)
                    history_ack = exchange(process, history_append, stdout_queue, stderr_lines, args.query_timeout_seconds)
                    if history_ack.get("ok") is not True or not isinstance(history_ack.get("state_sha256", ""), str):
                        raise RuntimeError("system must acknowledge append_turn_history with ok=true and state_sha256")
                    core = {
                        "runner_protocol": "trusted_online_runner_v4_history_append", "runner_session_id": session_id,
                        "stream_id": stream["stream_id"], "query_id": step["query_id"], "step_index": step["step_index"],
                        "initial_pool_sha256": pool_sha, "input_sha256": sha256(query_payload),
                        "system_output_sha256": sha256(filtered), "history_append_sha256": sha256(history_append),
                        "runner_chain_before_sha256": chain_before,
                        "response_text": response.get("response_text", ""),
                        "selected_memory_ids": response.get("selected_memory_ids", []),
                        "supporting_event_ids": response.get("supporting_event_ids", []),
                        "predicted_action_keys": response.get("predicted_action_keys", []),
                        "predicted_operation_state_labels": response.get("predicted_operation_state_labels", []),
                        "memory_write_delta": response.get("memory_write_delta", {}),
                        "recognized_active_config": response["recognized_active_config"],
                        "effective_behavior": response["effective_behavior"],
                        "system_state_before_sha256": system_state,
                        "system_state_after_sha256": history_ack.get("state_sha256", ""),
                        "runner_measured_latency_ms": latency_ms,
                    }
                    trace = signed_trace(core, key)
                    output.write(json.dumps(trace, ensure_ascii=False, separators=(",", ":")) + "\n")
                    output.flush()
                    chain_before = trace["runner_record_sha256"]
                    system_state = history_ack.get("state_sha256", "")
                exchange(process, {"type": "close_stream", "stream_id": stream["stream_id"]}, stdout_queue, stderr_lines, args.query_timeout_seconds)
            finally:
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=args.process_exit_timeout_seconds)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                shutil.rmtree(child_cwd, ignore_errors=True)


if __name__ == "__main__":
    main()
