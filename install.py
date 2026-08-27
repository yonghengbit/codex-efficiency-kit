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


def backup(
    path: Path,
    stamp: str,
    enabled: bool,
    backup_root: Path | None = None,
) -> Path | None:
    if not enabled or not path.exists():
        return None
    candidate = (
        backup_root / path.name
        if backup_root is not None
        else path.with_name(f"{path.name}.bak-{stamp}")
    )
    candidate.parent.mkdir(parents=True, exist_ok=True)
    index = 1
    while candidate.exists():
        candidate = candidate.with_name(f"{path.name}-{index}")
        index += 1
    if path.is_dir():
        shutil.copytree(path, candidate, symlinks=True)
    else:
        shutil.copy2(path, candidate)
    return candidate


def install_agents(
    src: Path,
    dst: Path,
    stamp: str,
    backup_enabled: bool,
    backup_root: Path | None = None,
) -> None:
    section = src.read_text(encoding="utf-8").strip()
    wrapped = f"{BEGIN}\n{section}\n{END}\n"

    if not dst.exists():
        dst.write_text(wrapped, encoding="utf-8")
        return

    original = dst.read_text(encoding="utf-8")
    backup(dst, stamp, backup_enabled, backup_root)
    if BEGIN in original and END in original:
        start = original.index(BEGIN)
        finish = original.index(END, start) + len(END)
        merged = original[:start].rstrip() + "\n\n" + wrapped + original[finish:].lstrip("\n")
    else:
        merged = original.rstrip() + "\n\n" + wrapped
    dst.write_text(merged, encoding="utf-8")


def install_skill(
    src: Path,
    skills_home: Path,
    stamp: str,
    backup_enabled: bool,
    backup_root: Path | None = None,
) -> None:
    dst = skills_home / src.name
    if dst.exists():
        backup(dst, stamp, backup_enabled, backup_root)
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def is_guardian_command(hook: object) -> bool:
    return isinstance(hook, dict) and "context_guardian.py" in str(hook.get("command", ""))


def remove_guardian_commands(groups: object, event: str) -> list[dict]:
    if not isinstance(groups, list):
        raise SystemExit(f"Cannot merge hooks: hooks.{event} must be a list")
    kept_groups: list[dict] = []
    for group in groups:
        if not isinstance(group, dict):
            raise SystemExit(f"Cannot merge hooks: hooks.{event} contains a non-object group")
        commands = group.get("hooks", [])
        if not isinstance(commands, list):
            raise SystemExit(f"Cannot merge hooks: hooks.{event}.hooks must be a list")
        kept_commands = [hook for hook in commands if not is_guardian_command(hook)]
        if kept_commands:
            updated = dict(group)
            updated["hooks"] = kept_commands
            kept_groups.append(updated)
    return kept_groups


def merge_hooks(
    hooks_path: Path,
    guardian_script: Path,
    stamp: str,
    backup_enabled: bool,
    backup_root: Path | None = None,
) -> None:
    if hooks_path.exists():
        backup(hooks_path, stamp, backup_enabled, backup_root)
        try:
            data = json.loads(hooks_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise SystemExit(f"Cannot parse existing {hooks_path}: {exc}")
    else:
        data = {"description": "User Codex lifecycle hooks.", "hooks": {}}

    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise SystemExit(f"Cannot merge hooks: {hooks_path} field 'hooks' must be an object")
    for event in ("SessionStart", "PostCompact", "Stop", "PostToolUse"):
        groups = hooks.get(event)
        if groups is None:
            continue
        kept_groups = remove_guardian_commands(groups, event)
        if kept_groups:
            hooks[event] = kept_groups
        else:
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
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="replace Kit-managed files without creating timestamped backups",
    )
    args = parser.parse_args()

    kit = Path(__file__).resolve().parent
    home = args.codex_home.expanduser().resolve()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    home.mkdir(parents=True, exist_ok=True)
    (home / "skills").mkdir(parents=True, exist_ok=True)
    (home / "context-guardian").mkdir(parents=True, exist_ok=True)

    backup_enabled = not args.no_backup
    backup_root = home / "backups" / stamp if backup_enabled else None

    install_agents(
        kit / "AGENTS.md",
        home / "AGENTS.md",
        stamp,
        backup_enabled,
        backup_root,
    )

    for skill in sorted((kit / "skills").iterdir()):
        if skill.is_dir() and (skill / "SKILL.md").exists():
            install_skill(
                skill,
                home / "skills",
                stamp,
                backup_enabled,
                backup_root / "skills" if backup_root else None,
            )

    guardian_dst = home / "context-guardian" / "context_guardian.py"
    backup(
        guardian_dst,
        stamp,
        backup_enabled,
        backup_root / "context-guardian" if backup_root else None,
    )
    shutil.copy2(kit / "context-guardian" / "context_guardian.py", guardian_dst)
    guardian_dst.chmod(0o755)

    config_dst = home / "context-guardian" / "config.json"
    if not config_dst.exists():
        shutil.copy2(kit / "context-guardian" / "config.json", config_dst)

    merge_hooks(
        home / "hooks.json",
        guardian_dst,
        stamp,
        backup_enabled,
        backup_root,
    )

    print(f"Installed Codex Efficiency Kit into: {home}")
    print(f"Global rules: {home / 'AGENTS.md'}")
    print(f"Skills: {home / 'skills'}")
    print(f"Context Guardian: {guardian_dst}")
    print(f"Hooks: {home / 'hooks.json'}")
    print(f"Backups: {'disabled by --no-backup' if args.no_backup else 'enabled'}")
    print()
    print("Next: start Codex, open /hooks, review and trust the new hooks, then start a fresh thread.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
