import json
import os
import subprocess
from pathlib import Path
from typing import Final

ROOT: Final[Path] = Path(__file__).resolve().parents[2]
SOURCE_ROOTS: Final[tuple[str, ...]] = ("fastapi_custom_responses/",)
SOURCE_FILES: Final[tuple[str, ...]] = ("pyproject.toml", "poetry.lock", "poetry.toml")


def git(*arguments: str) -> str:
    """Read git output, failing when a revision cannot be resolved."""

    return subprocess.check_output(["git", *arguments], cwd=ROOT, text=True)


def is_application_source(path: str) -> bool:
    """Classify application inputs without counting documentation or test fixtures."""

    parts = Path(path).parts

    return (
        (path.startswith(SOURCE_ROOTS) or path in SOURCE_FILES)
        and not any(part in {"tests", "test", "__tests__", "docs", "audits"} for part in parts)
        and not path.endswith((".md", ".rst"))
        and not any(part.endswith((".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx")) for part in parts)
    )


def main() -> None:
    """Select revision or whole-branch lint before dependency installation."""

    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    event_name = os.environ["GITHUB_EVENT_NAME"]
    head = os.environ["GITHUB_SHA"]
    base = ""

    if event_name == "pull_request":
        head = event["pull_request"]["head"]["sha"]
        if event["action"] == "synchronize":
            base = event["before"]
        else:
            base = git("merge-base", event["pull_request"]["base"]["sha"], head).strip()
    elif event_name == "push":
        base = event["before"]

    if base and set(base) == {"0"}:
        base = git("hash-object", "-t", "tree", os.devnull).strip()

    if (
        base
        and subprocess.run(
            ["git", "cat-file", "-e", base], cwd=ROOT, check=False, capture_output=True
        ).returncode
    ):
        subprocess.run(["git", "fetch", "--no-tags", "origin", base], cwd=ROOT, check=True)

    changed = git("diff", "--name-only", "--no-renames", "-z", base, head).split("\0") if base else []

    run = event_name in {"pull_request", "workflow_dispatch"} or any(
        is_application_source(path) for path in changed
    )
    revision = base if event_name == "pull_request" else ""

    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        output.write(f"run={str(run).lower()}\nbase={revision}\n")

    print(f"Lint scope: {event_name}; selected: {run}; revision: {revision or 'whole branch'}")


if __name__ == "__main__":
    main()
