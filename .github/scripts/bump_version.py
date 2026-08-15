import argparse
import os
import subprocess
from pathlib import Path


def poetry_version(*arguments: str) -> str:
    """Run `poetry version`, returning the version it reports."""

    completed = subprocess.run(
        ["poetry", "version", "--short", *arguments], capture_output=True, check=True, text=True
    )

    return completed.stdout.strip()


def main() -> None:
    """Bump the project version and publish the previous and new values as step outputs."""

    parser = argparse.ArgumentParser()
    parser.add_argument("increment", choices=("patch", "minor", "major"))
    arguments = parser.parse_args()

    current_version = poetry_version()
    new_version = poetry_version(arguments.increment)

    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        output.write(f"current={current_version}\nnew={new_version}\n")


if __name__ == "__main__":
    main()
