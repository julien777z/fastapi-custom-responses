import os
import subprocess
from pathlib import Path
from typing import Final

ROOT: Final[Path] = Path(__file__).resolve().parents[2]


def main() -> int:
    """Run each native lint tool once, scoped to existing changed files on pull requests."""

    base = os.environ.get("LINT_BASE_REVISION", "")
    changed = []

    if base:
        changed = subprocess.check_output(
            ["git", "diff", "--name-only", "--no-renames", "--diff-filter=ACM", "-z", base, "HEAD"],
            cwd=ROOT,
            text=True,
        ).split("\0")

        changed = [path for path in changed if path.endswith((".py", ".pyi")) and (ROOT / path).is_file()]

    result = 0

    for tool in ("black", "isort", "pylint"):
        targets = changed if base else ["."]
        if tool == "pylint":
            targets = (
                [
                    path
                    for path in changed
                    if path.startswith(("fastapi_custom_responses/", ".github/scripts/"))
                ]
                if base
                else ["fastapi_custom_responses/", ".github/scripts/"]
            )

        if not targets:
            print(f"No changed {tool} targets; skipping lint.")
            continue

        flags = ["--check"] if tool == "black" else ["--check-only"] if tool == "isort" else []
        status = subprocess.call(["poetry", "run", tool, *flags, *targets], cwd=ROOT)
        result = result or status

    return result


if __name__ == "__main__":
    raise SystemExit(main())
