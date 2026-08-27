from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "context_guardian",
    ROOT / "context-guardian" / "context_guardian.py",
)
assert SPEC and SPEC.loader
guardian = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guardian)


class ContextGuardianTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.cfg = guardian.validate_config({})

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def capture(self, function, *args) -> str:
        output = io.StringIO()
        with redirect_stdout(output):
            function(*args)
        return output.getvalue().strip()

    def compact_twice(self, session_id: str) -> None:
        payload = {
            "hook_event_name": "PostCompact",
            "session_id": session_id,
            "model": "gpt-5.6-sol",
            "cwd": str(self.base),
        }
        self.capture(guardian.post_compact, payload, self.base, self.cfg)
        self.capture(guardian.post_compact, payload, self.base, self.cfg)

    def test_stop_requires_verified_or_bounded_blocked_state(self) -> None:
        self.compact_twice("verified-session")
        first = json.loads(self.capture(
            guardian.stop,
            {"session_id": "verified-session", "turn_id": "turn-1", "stop_hook_active": False},
            self.base,
            self.cfg,
        ))
        self.assertEqual(first["decision"], "block")
        self.capture(
            guardian.mark_handoff,
            self.base,
            "verified-session",
            "verified",
            "target-thread",
        )
        allowed = self.capture(
            guardian.stop,
            {"session_id": "verified-session", "turn_id": "turn-1", "stop_hook_active": True},
            self.base,
            self.cfg,
        )
        self.assertEqual(allowed, "{}")
        next_turn = json.loads(self.capture(
            guardian.stop,
            {"session_id": "verified-session", "turn_id": "turn-2", "stop_hook_active": False},
            self.base,
            self.cfg,
        ))
        self.assertEqual(next_turn["decision"], "block")

        self.compact_twice("failed-session")
        self.capture(
            guardian.stop,
            {"session_id": "failed-session", "turn_id": "turn-1", "stop_hook_active": False},
            self.base,
            self.cfg,
        )
        retry = json.loads(self.capture(
            guardian.stop,
            {"session_id": "failed-session", "turn_id": "turn-1", "stop_hook_active": True},
            self.base,
            self.cfg,
        ))
        self.assertEqual(retry["decision"], "block")
        exhausted = json.loads(self.capture(
            guardian.stop,
            {"session_id": "failed-session", "turn_id": "turn-1", "stop_hook_active": True},
            self.base,
            self.cfg,
        ))
        self.assertIn("HANDOFF_START_FAILED", exhausted["reason"])
        state = guardian.load_state_unlocked(self.base, "failed-session")
        self.assertEqual(state["handoff_status"], "blocked")
        self.assertEqual(
            self.capture(
                guardian.stop,
                {"session_id": "failed-session", "turn_id": "turn-1", "stop_hook_active": True},
                self.base,
                self.cfg,
            ),
            "{}",
        )

    def test_wait_and_explicit_failure_are_not_counted(self) -> None:
        payload = {
            "session_id": "tools",
            "model": "gpt-5.6-sol",
            "cwd": str(self.base),
        }
        self.capture(guardian.post_compact, payload, self.base, self.cfg)
        for _ in range(3):
            self.capture(
                guardian.post_tool,
                {
                    "session_id": "tools",
                    "tool_name": "wait_threads",
                    "tool_input": {"timeoutMs": 30000},
                    "tool_response": {"status": "ok"},
                },
                self.base,
                self.cfg,
            )
            self.capture(
                guardian.post_tool,
                {
                    "session_id": "tools",
                    "tool_name": "Bash",
                    "tool_input": {"command": "false"},
                    "tool_response": {"exit_code": 1},
                },
                self.base,
                self.cfg,
            )
        state = guardian.load_state_unlocked(self.base, "tools")
        self.assertEqual(state["tool_fingerprints"], {})

        last = ""
        for _ in range(3):
            last = self.capture(
                guardian.post_tool,
                {
                    "session_id": "tools",
                    "tool_name": "mcp__fs__read",
                    "tool_input": {"path": "README.md"},
                    "tool_response": {"status": "ok"},
                },
                self.base,
                self.cfg,
            )
        self.assertIn("drift signal", last)

    def test_concurrent_state_updates_do_not_drop_counts(self) -> None:
        def increment() -> None:
            def apply(state: dict) -> None:
                state["test_count"] = int(state.get("test_count", 0)) + 1

            guardian.update_state(self.base, "concurrent", apply)

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: increment(), range(40)))
        state = guardian.load_state_unlocked(self.base, "concurrent")
        self.assertEqual(state["test_count"], 40)

    def test_invalid_config_falls_back_to_defaults(self) -> None:
        (self.base / "config.json").write_text(
            '{"soft_compactions": 3, "hard_compactions": 2}',
            encoding="utf-8",
        )
        self.assertEqual(guardian.load_config(self.base), guardian.DEFAULTS)


if __name__ == "__main__":
    unittest.main()
