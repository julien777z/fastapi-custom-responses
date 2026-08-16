import argparse
import os
import subprocess
from pathlib import Path


def main() -> None:
    """Bump the project version and publish the new value as a step output."""

    parser = argparse.ArgumentParser()

    parser.add_argument("increment", choices=("patch", "minor", "major"))

    arguments = parser.parse_args()

    completed = subprocess.run(
        ["poetry", "version", "--short", arguments.increment],
        stdout=subprocess.PIPE,
        check=True,
        text=True,
    )

    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        output.write(f"new={completed.stdout.strip()}\n")


if __name__ == "__main__":
    main()
