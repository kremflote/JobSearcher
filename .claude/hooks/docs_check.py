"""Stop hook: block the session from ending if code changed but docs/HANDOVER.md did not.

Enforces the "Definition of done" in AGENTS.md. Looks at uncommitted changes and
commits not yet pushed. Exit code 2 sends the message back to the agent so it can
update the docs before stopping.
"""

import json
import subprocess
import sys

CODE_PREFIXES = ("src/", "config/", "context/prompts/", "scripts/", "pyproject.toml", "alembic.ini")
HANDOVER = "docs/HANDOVER.md"


def git(*args: str) -> list[str]:
    result = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def changed_paths() -> set[str]:
    paths = set()
    for line in git("status", "--porcelain", "--untracked-files=all"):
        path = line[3:].strip().strip('"')
        if " -> " in path:  # rename
            path = path.split(" -> ", 1)[1]
        paths.add(path)
    # Committed but not yet pushed: compare with upstream, or with main for a new branch
    for base in ("@{upstream}", "origin/main", "main"):
        if git("rev-parse", "--verify", "--quiet", base):
            paths.update(git("diff", "--name-only", f"{base}...HEAD"))
            break
    return paths


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}
    # The agent is already continuing because of this hook; don't loop.
    if payload.get("stop_hook_active"):
        return 0

    paths = changed_paths()
    code = sorted(p for p in paths if p.startswith(CODE_PREFIXES))
    if not code or HANDOVER in paths:
        return 0

    shown = "\n".join(f"  - {p}" for p in code[:15])
    more = f"\n  ... and {len(code) - 15} more" if len(code) > 15 else ""
    print(
        "Code changed but docs/HANDOVER.md was not updated (AGENTS.md -> Definition of done).\n"
        f"Changed files:\n{shown}{more}\n"
        "Before stopping: check the 'What triggers a doc update' table in AGENTS.md, "
        "update the affected docs (ARCHITECTURE sections, README, prompt versions), "
        "then update docs/HANDOVER.md and list the docs you changed in your final message.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
