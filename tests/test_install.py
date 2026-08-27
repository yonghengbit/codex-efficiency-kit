from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("kit_install", ROOT / "install.py")
assert SPEC and SPEC.loader
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def test_skill_upgrade_creates_default_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source" / "example"
            destination_home = root / "skills"
            existing = destination_home / "example"
            source.mkdir(parents=True)
            existing.mkdir(parents=True)
            (source / "SKILL.md").write_text("new", encoding="utf-8")
            (existing / "SKILL.md").write_text("old", encoding="utf-8")
            backup_root = root / "backups" / "stamp" / "skills"

            installer.install_skill(
                source,
                destination_home,
                "stamp",
                True,
                backup_root,
            )

            self.assertEqual((existing / "SKILL.md").read_text(encoding="utf-8"), "new")
            backup = backup_root / "example"
            self.assertEqual((backup / "SKILL.md").read_text(encoding="utf-8"), "old")
            self.assertEqual(list(destination_home.glob("*.bak-*")), [])

    def test_mixed_hook_group_preserves_non_guardian_command(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            hooks_path = root / "hooks.json"
            guardian_script = root / "context_guardian.py"
            hooks_path.write_text(json.dumps({
                "hooks": {
                    "PostToolUse": [{
                        "matcher": ".*",
                        "hooks": [
                            {"type": "command", "command": f'python3 "{guardian_script}"'},
                            {"type": "command", "command": "python3 user_hook.py"},
                        ],
                    }],
                },
            }), encoding="utf-8")

            installer.merge_hooks(hooks_path, guardian_script, "stamp", False)

            data = json.loads(hooks_path.read_text(encoding="utf-8"))
            commands = [
                hook["command"]
                for group in data["hooks"]["PostToolUse"]
                for hook in group["hooks"]
            ]
            self.assertIn("python3 user_hook.py", commands)
            self.assertEqual(sum("context_guardian.py" in command for command in commands), 1)

    def test_no_backup_option_skips_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "AGENTS.md"
            path.write_text("old", encoding="utf-8")
            self.assertIsNone(installer.backup(path, "stamp", False))
            self.assertFalse((root / "AGENTS.md.bak-stamp").exists())


if __name__ == "__main__":
    unittest.main()
