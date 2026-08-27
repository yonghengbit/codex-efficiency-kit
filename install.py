#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
from datetime import datetime


BEGIN = "<!-- BEGIN CODEX EFFICIENCY KIT -->"
END = "<!-- END CODEX EFFICIENCY KIT -->"


def backup(path: Path, stamp: str) -> None:
    # This local installation was explicitly requested without backups.
    return


def install_agents(src: Path, dst: Path, stamp: str) -> None:
    section = src.read_text(encoding="utf-8").strip()
    wrapped = f"{BEGIN}\n{section}\n{END}\n"

    if not dst.exists():
        dst.write_text(wrapped, encoding="utf-8")
        return

    original = dst.read_text(encoding="utf-8")
    backup(dst, stamp)
    if BEGIN in original and END in original:
        start = original.index(BEGIN)
        finish = original.index(END, start) + len(END)
        merged = original[:start].rstrip() + "\n\n" + wrapped + original[finish:].lstrip("\n")
    else:
        merged = original.rstrip() + "\n\n" + wrapped
    dst.write_text(merged, encoding="utf-8")


def install_skill(src: Path, skills_home: Path, stamp: str) -> None:
    dst = skills_home / src.name
    if dst.exists():
        backup(dst, stamp)
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def is_guardian_hook(group: dict) -> bool:
    for hook in group.get("hooks", []):
        if "context_guardian.py" in str(hook.get("command", "")):
            return True
    return False


def merge_hooks(hooks_path: Path, guardian_script: Path, stamp: str) -> None:
    if hooks_path.exists():
        backup(hooks_path, stamp)
        try:
            data = json.loads(hooks_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise SystemExit(f"Cannot parse existing {hooks_path}: {exc}")
    else:
        data = {"description": "User Codex lifecycle hooks.", "hooks": {}}

    hooks = data.setdefault("hooks", {})
    for event in ("SessionStart", "PostCompact", "Stop", "PostToolUse"):
        groups = hooks.get(event)
        if groups is None:
            continue
        groups[:] = [g for g in groups if not is_guardian_hook(g)]
        if not groups:
            hooks.pop(event, None)

    posix = f'python3 "{guardian_script}"'
    windows = f'py -3 "{guardian_script}"'

    hooks.setdefault("PostCompact", []).append({
        "matcher": "^(auto|manual)$",
        "hooks": [{"type":"command","command":posix,"commandWindows":windows,
                   "timeout":5,"statusMessage":"Recording context compaction"}],
    })
    hooks.setdefault("Stop", []).append({
        "hooks": [{"type":"command","command":posix,"commandWindows":windows,
                   "timeout":5,"statusMessage":"Checking context handoff gate"}],
    })
    hooks.setdefault("PostToolUse", []).append({
        "hooks": [{"type":"command","command":posix,"commandWindows":windows,"timeout":5}],
    })
    hooks_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install Codex Efficiency Kit.")
    parser.add_argument(
        "--codex-home",
        type=Path,
        default=Path.home() / ".codex",
        help="Codex home directory (default: ~/.codex)",
    )
    args = parser.parse_args()

    kit = Path(__file__).resolve().parent
    home = args.codex_home.expanduser().resolve()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    home.mkdir(parents=True, exist_ok=True)
    (home / "skills").mkdir(parents=True, exist_ok=True)
    (home / "context-guardian").mkdir(parents=True, exist_ok=True)

    install_agents(kit / "AGENTS.md", home / "AGENTS.md", stamp)

    for skill in sorted((kit / "skills").iterdir()):
        if skill.is_dir() and (skill / "SKILL.md").exists():
            install_skill(skill, home / "skills", stamp)

    guardian_dst = home / "context-guardian" / "context_guardian.py"
    shutil.copy2(kit / "context-guardian" / "context_guardian.py", guardian_dst)
    guardian_dst.chmod(0o755)

    config_dst = home / "context-guardian" / "config.json"
    if not config_dst.exists():
        shutil.copy2(kit / "context-guardian" / "config.json", config_dst)

    merge_hooks(home / "hooks.json", guardian_dst, stamp)

    print(f"Installed Codex Efficiency Kit into: {home}")
    print(f"Global rules: {home / 'AGENTS.md'}")
    print(f"Skills: {home / 'skills'}")
    print(f"Context Guardian: {guardian_dst}")
    print(f"Hooks: {home / 'hooks.json'}")
    print()
    print("Next: start Codex, open /hooks, review and trust the new hooks, then start a fresh thread.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
