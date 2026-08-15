#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys


state = []


def digest() -> str:
    text = json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


for line in sys.stdin:
    request = json.loads(line)
    kind = request.get("type")
    if kind == "initialize_stream":
        state = list(request.get("initial_memory_items", []))
        response = {"ok": True, "state_sha256": digest()}
    elif kind == "query":
        state.extend(request.get("new_raw_events", []))
        response = {
            "response_text": "", "selected_memory_ids": [], "supporting_event_ids": [],
            "predicted_action_keys": [], "predicted_operation_state_labels": [],
            "memory_write_delta": {}, "state_sha256": digest(),
        }
    elif kind == "append_turn_history":
        state.append(request.get("query_event", {}))
        state.append(request.get("assistant_response_event", {}))
        state.append(request.get("memory_delta_event", {}))
        response = {"ok": True, "state_sha256": digest()}
    elif kind == "close_stream":
        response = {"ok": True, "state_sha256": digest()}
    else:
        response = {"error": "unknown request type", "state_sha256": digest()}
    print(json.dumps(response, ensure_ascii=False, separators=(",", ":")), flush=True)
