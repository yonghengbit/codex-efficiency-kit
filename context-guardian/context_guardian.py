#!/usr/bin/env python3
"""Context Guardian v3.3.

PostCompact counts context degradation. Stop gates unfinished work until a
same-model fresh-root handoff is verified or explicitly reported blocked.
PostToolUse emits bounded repetition signals for useful, non-failing actions.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Callable, Iterator


DEFAULTS = {
    "soft_compactions": 2,
    "hard_compactions": 3,
    "max_handoff_attempts": 2,
    "repeat_threshold": 3,
    "max_state_entries": 256,
    "track_repetition_after_compaction": True,
}
TERMINAL_HANDOFF_STATES = {"verified", "blocked", "completed"}
IGNORED_TOOL_NAMES = {
    "agent",
    "apply_patch",
    "followup_task",
    "get_handoff_status",
    "get_status",
    "interrupt_agent",
    "list_agents",
    "send_message",
    "send_message_to_thread",
    "wait",
    "wait_agent",
    "wait_threads",
    "write_stdin",
}
MUTATING_TOOL_TERMS = {"apply", "copy", "create", "delete", "edit", "move", "remove", "update", "write"}
PATH_KEYS = {"path", "file_path", "filepath", "file", "filename"}


def home_dir() -> Path:
    override = os.environ.get("CODEX_CONTEXT_GUARDIAN_DIR")
    return Path(override).expanduser() if override else Path.home() / ".codex" / "context-guardian"


def validate_config(value: dict[str, Any]) -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    cfg.update(value)
    integer_fields = (
        "soft_compactions",
        "hard_compactions",
        "max_handoff_attempts",
        "repeat_threshold",
        "max_state_entries",
    )
    if any(isinstance(cfg[key], bool) or not isinstance(cfg[key], int) for key in integer_fields):
        raise ValueError("numeric thresholds must be integers")
    if cfg["soft_compactions"] < 1 or cfg["hard_compactions"] <= cfg["soft_compactions"]:
        raise ValueError("require 1 <= soft_compactions < hard_compactions")
    if cfg["max_handoff_attempts"] < 1:
        raise ValueError("max_handoff_attempts must be at least 1")
    if cfg["repeat_threshold"] < 2:
        raise ValueError("repeat_threshold must be at least 2")
    if cfg["max_state_entries"] < 32:
        raise ValueError("max_state_entries must be at least 32")
    if not isinstance(cfg["track_repetition_after_compaction"], bool):
        raise ValueError("track_repetition_after_compaction must be boolean")
    return cfg


def load_config(base: Path) -> dict[str, Any]:
    path = base / "config.json"
    if not path.exists():
        return dict(DEFAULTS)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("top-level value must be an object")
        return validate_config(value)
    except Exception as exc:
        print(f"Context Guardian: invalid config at {path}; using defaults: {exc}", file=os.sys.stderr)
        return dict(DEFAULTS)


def safe_session_id(session_id: str) -> str:
    return "".join(char if char.isalnum() or char in "-_." else "_" for char in session_id)


def state_path(base: Path, session_id: str) -> Path:
    return base / "state" / f"{safe_session_id(session_id)}.json"


def fresh_state(session_id: str) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "compactions": 0,
        "last_model": None,
        "last_cwd": None,
        "handoff_status": "idle",
        "handoff_compaction": None,
        "handoff_turn_id": None,
        "handoff_attempts": 0,
        "target_thread_id": None,
        "tool_fingerprints": {},
        "path_accesses": {},
    }


def normalize_state(value: dict[str, Any], session_id: str) -> dict[str, Any]:
    state = fresh_state(session_id)
    state.update(value)
    state["session_id"] = session_id
    if "handoff_status" not in value:
        # v3.2 only recorded that a prompt was emitted, not that handoff succeeded.
        state["handoff_status"] = "idle"
        state["handoff_compaction"] = None
        state["handoff_turn_id"] = None
        state["handoff_attempts"] = 0
    state.pop("handoff_prompted_at", None)
    state.pop("path_reads", None)
    return state


def load_state_unlocked(base: Path, session_id: str) -> dict[str, Any]:
    path = state_path(base, session_id)
    if path.exists():
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                return normalize_state(value, session_id)
        except Exception:
            pass
    return fresh_state(session_id)


def save_state_unlocked(base: Path, state: dict[str, Any]) -> None:
    path = state_path(base, str(state["session_id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f"{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            json.dump(state, temporary, indent=2, sort_keys=True)
            temporary.write("\n")
            temporary_name = temporary.name
        os.replace(temporary_name, path)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)


@contextmanager
def state_lock(base: Path, session_id: str, timeout: float = 4.0) -> Iterator[None]:
    lock_path = state_path(base, session_id).with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    if handle.tell() == 0:
        handle.write(b"\0")
        handle.flush()
    deadline = time.monotonic() + timeout
    acquired = False
    try:
        if os.name == "nt":
            import msvcrt

            while True:
                try:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    acquired = True
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"timed out locking {lock_path}")
                    time.sleep(0.02)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            acquired = True
        yield
    finally:
        try:
            handle.seek(0)
            if acquired and os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            elif acquired:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def update_state(
    base: Path,
    session_id: str,
    update: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    with state_lock(base, session_id):
        state = load_state_unlocked(base, session_id)
        update(state)
        save_state_unlocked(base, state)
        return state


def stable_json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except Exception:
        return repr(value)


def fingerprint(name: str, tool_input: Any) -> str:
    raw = f"{name}\0{stable_json(tool_input)}".encode()
    return hashlib.sha256(raw).hexdigest()[:20]


def extract_paths(value: Any) -> list[str]:
    paths: list[str] = []

    def walk(current: Any) -> None:
        if isinstance(current, dict):
            for key, child in current.items():
                if key.lower() in PATH_KEYS and isinstance(child, str) and child:
                    paths.append(child)
                else:
                    walk(child)
        elif isinstance(current, list):
            for child in current:
                walk(child)

    walk(value)
    return list(dict.fromkeys(paths))


def normalize_path(path: str, cwd: str | None) -> str | None:
    if "://" in path:
        return None
    try:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute() and cwd:
            candidate = Path(cwd) / candidate
        return os.path.normcase(os.path.normpath(str(candidate.resolve(strict=False))))
    except Exception:
        return os.path.normcase(os.path.normpath(path))


def tool_failed(response: Any) -> bool:
    if not isinstance(response, dict):
        return False
    if response.get("isError") is True or response.get("is_error") is True:
        return True
    exit_code = response.get("exit_code")
    if isinstance(exit_code, int) and exit_code != 0:
        return True
    status = response.get("status")
    return isinstance(status, str) and status.lower() in {"error", "failed", "failure"}


def should_track_tool(name: str, response: Any) -> bool:
    normalized = name.lower().rsplit("__", 1)[-1]
    tokens = set(normalized.replace("-", "_").split("_"))
    if (
        normalized in IGNORED_TOOL_NAMES
        or "wait" in normalized
        or tokens.intersection(MUTATING_TOOL_TERMS)
    ):
        return False
    return not tool_failed(response)


def trim_counts(counts: dict[str, int], limit: int) -> None:
    if len(counts) <= limit:
        return
    keep = sorted(counts.items(), key=lambda item: item[1], reverse=True)[:limit]
    counts.clear()
    counts.update(keep)


def emit_context(event: str, context: str, message: str | None = None) -> None:
    output: dict[str, Any] = {
        "hookSpecificOutput": {"hookEventName": event, "additionalContext": context}
    }
    if message:
        output["systemMessage"] = message
    print(json.dumps(output, ensure_ascii=False))


def require_session_id(payload: dict[str, Any]) -> str | None:
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        print("Context Guardian: hook payload has no session_id; event ignored", file=os.sys.stderr)
        return None
    return session_id


def post_compact(payload: dict[str, Any], base: Path, cfg: dict[str, Any]) -> None:
    del cfg
    session_id = require_session_id(payload)
    if not session_id:
        print("{}")
        return

    def apply(state: dict[str, Any]) -> None:
        state["compactions"] = int(state.get("compactions", 0)) + 1
        state["last_model"] = payload.get("model")
        state["last_cwd"] = payload.get("cwd")
        state["handoff_status"] = "idle"
        state["handoff_compaction"] = None
        state["handoff_turn_id"] = None
        state["handoff_attempts"] = 0
        state["target_thread_id"] = None

    state = update_state(base, session_id, apply)
    print(json.dumps({
        "systemMessage": (
            f"Context Guardian recorded compaction {state['compactions']}. Preserve confirmed facts and "
            "do not repeat completed investigation."
        )
    }, ensure_ascii=False))


def handoff_reason(state: dict[str, Any], level: str, retry: bool = False) -> str:
    session_id = state["session_id"]
    model = state.get("last_model") or "current primary model"
    prefix = "HANDOFF RETRY" if retry else "HANDOFF GATE"
    return (
        f"CONTEXT GUARDIAN {level} {prefix}: this root compacted {state['compactions']} times. "
        f"SOURCE_SESSION_ID={session_id}; PRIMARY_MODEL={model}. If the original task is complete, run the installed "
        f"context_guardian.py --mark-handoff completed --session-id {session_id}, then finalize. Otherwise execute "
        "the context-handoff skill now. Preserve any "
        "same-task, explicitly user-authorized WORKFLOW_MODE=sub-agent state, but never use a worker as the fresh "
        "root or spawn a duplicate active worker. Before stopping, verify the new root model and liveness, then "
        "mark Guardian status verified with its target thread id. If fresh-root handoff cannot be completed, mark "
        "status blocked and report the concrete blocker."
    )


def stop(payload: dict[str, Any], base: Path, cfg: dict[str, Any]) -> None:
    session_id = require_session_id(payload)
    if not session_id:
        print("{}")
        return

    with state_lock(base, session_id):
        state = load_state_unlocked(base, session_id)
        count = int(state.get("compactions", 0))
        soft = cfg["soft_compactions"]
        if count < soft:
            print("{}")
            return

        turn_id = payload.get("turn_id")
        status = str(state.get("handoff_status", "idle"))
        same_gate = (
            state.get("handoff_compaction") == count
            and state.get("handoff_turn_id") == turn_id
        )
        if same_gate and status in TERMINAL_HANDOFF_STATES:
            print("{}")
            return

        attempts = int(state.get("handoff_attempts", 0)) if same_gate else 0
        max_attempts = cfg["max_handoff_attempts"]
        active = payload.get("stop_hook_active") is True
        level = "HARD" if count >= cfg["hard_compactions"] else "SOFT"

        if active and attempts >= max_attempts:
            state["handoff_status"] = "blocked"
            state["handoff_compaction"] = count
            state["handoff_turn_id"] = turn_id
            save_state_unlocked(base, state)
            reason = (
                "CONTEXT GUARDIAN HANDOFF_START_FAILED: the bounded handoff attempts were not acknowledged. "
                "Report the unresolved blocker clearly and stop; do not silently claim success or spawn a worker "
                "as a replacement root."
            )
            print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
            return

        attempts += 1
        state["handoff_status"] = "requested"
        state["handoff_compaction"] = count
        state["handoff_turn_id"] = turn_id
        state["handoff_attempts"] = attempts
        save_state_unlocked(base, state)
        print(json.dumps({
            "decision": "block",
            "reason": handoff_reason(state, level, retry=attempts > 1),
        }, ensure_ascii=False))


def post_tool(payload: dict[str, Any], base: Path, cfg: dict[str, Any]) -> None:
    if not cfg["track_repetition_after_compaction"]:
        return
    session_id = require_session_id(payload)
    if not session_id:
        return
    name = str(payload.get("tool_name") or "unknown")
    response = payload.get("tool_response")
    if not should_track_tool(name, response):
        return

    tool_input = payload.get("tool_input")
    threshold = cfg["repeat_threshold"]
    result: dict[str, Any] = {"exact": False, "paths": []}

    def apply(state: dict[str, Any]) -> None:
        if int(state.get("compactions", 0)) < 1:
            return
        fingerprints = state.setdefault("tool_fingerprints", {})
        current_fingerprint = fingerprint(name, tool_input)
        fingerprints[current_fingerprint] = int(fingerprints.get(current_fingerprint, 0)) + 1
        result["exact"] = fingerprints[current_fingerprint] % threshold == 0

        accesses = state.setdefault("path_accesses", {})
        cwd = state.get("last_cwd")
        for raw_path in extract_paths(tool_input):
            path = normalize_path(raw_path, cwd)
            if not path:
                continue
            key = f"{name}:{path}"
            accesses[key] = int(accesses.get(key, 0)) + 1
            if accesses[key] % threshold == 0:
                result["paths"].append(path)
        trim_counts(fingerprints, cfg["max_state_entries"])
        trim_counts(accesses, cfg["max_state_entries"])

    state = update_state(base, session_id, apply)
    if int(state.get("compactions", 0)) < 1:
        return
    if not result["exact"] and not result["paths"]:
        return
    details: list[str] = []
    if result["exact"]:
        details.append(f"the same {name} action reached another {threshold}-call interval")
    if result["paths"]:
        details.append("the same path was accessed repeatedly: " + ", ".join(result["paths"][:3]))
    emit_context(
        "PostToolUse",
        "CONTEXT GUARDIAN drift signal: " + "; ".join(details)
        + ". Repeat only when new state requires it; do not redo completed investigation.",
        "Context Guardian: repeated post-compaction work detected.",
    )


def mark_handoff(
    base: Path,
    session_id: str,
    status: str,
    target_thread_id: str | None,
) -> None:
    if status == "verified" and not target_thread_id:
        raise SystemExit("--target-thread-id is required when status is verified")

    def apply(state: dict[str, Any]) -> None:
        state["handoff_status"] = status
        state["handoff_compaction"] = int(state.get("compactions", 0))
        state["target_thread_id"] = target_thread_id

    state = update_state(base, session_id, apply)
    print(json.dumps({
        "session_id": session_id,
        "handoff_status": state["handoff_status"],
        "target_thread_id": state.get("target_thread_id"),
    }, ensure_ascii=False))


def status(base: Path) -> int:
    directory = base / "state"
    if not directory.exists():
        print("No Context Guardian session state found.")
        return 0
    rows = []
    for path in sorted(directory.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows.append({
            "session": value.get("session_id"),
            "compactions": value.get("compactions", 0),
            "last_model": value.get("last_model"),
            "handoff_status": value.get("handoff_status", "legacy"),
            "handoff_turn_id": value.get("handoff_turn_id"),
            "handoff_attempts": value.get("handoff_attempts", 0),
            "target_thread_id": value.get("target_thread_id"),
            "cwd": value.get("last_cwd"),
        })
    print(json.dumps(rows[:20], indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--mark-handoff", choices=("verified", "blocked", "completed"))
    parser.add_argument("--session-id")
    parser.add_argument("--target-thread-id")
    args = parser.parse_args()

    base = home_dir()
    base.mkdir(parents=True, exist_ok=True)
    cfg = load_config(base)
    if args.status:
        return status(base)
    if args.mark_handoff:
        if not args.session_id:
            parser.error("--session-id is required with --mark-handoff")
        mark_handoff(base, args.session_id, args.mark_handoff, args.target_thread_id)
        return 0

    try:
        payload = json.load(os.sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0
    event = payload.get("hook_event_name")
    if event == "PostCompact":
        post_compact(payload, base, cfg)
    elif event == "Stop":
        stop(payload, base, cfg)
    elif event == "PostToolUse":
        post_tool(payload, base, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
