import argparse
import subprocess


def main() -> None:
    """Commit the version bump, tag it, and push both to the current branch."""

    parser = argparse.ArgumentParser()
    parser.add_argument("version")
    arguments = parser.parse_args()

    commands = (
        (
            "-c",
            "user.name=github-actions",
            "-c",
            "user.email=github-actions@github.com",
            "commit",
            "pyproject.toml",
            "-m",
            f"chore(release): bump version to {arguments.version}",
        ),
        ("tag", arguments.version),
        ("push", "--atomic", "origin", "HEAD", f"refs/tags/{arguments.version}"),
    )

    for command in commands:
        subprocess.run(["git", *command], check=True)


if __name__ == "__main__":
    main()
