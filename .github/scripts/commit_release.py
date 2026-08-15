import argparse
import subprocess


def git(*arguments: str) -> None:
    """Run a git command, raising when it fails."""

    subprocess.run(["git", *arguments], check=True)


def main() -> None:
    """Commit the version bump, tag it, and push both to the current branch."""

    parser = argparse.ArgumentParser()
    parser.add_argument("version")
    arguments = parser.parse_args()

    git("config", "user.name", "github-actions")
    git("config", "user.email", "github-actions@github.com")

    git("commit", "-am", f"chore(release): bump version to {arguments.version}")
    git("tag", arguments.version)

    git("push", "origin", "HEAD")
    git("push", "origin", "--tags")


if __name__ == "__main__":
    main()
