from __future__ import annotations

import subprocess
import sys


def run(command: list[str]) -> None:
    print(f"Running: {' '.join(command)}", flush=True)
    subprocess.run(command, check=True)


def main() -> None:
    run([sys.executable, "-m", "ruff", "check", "."])
    run([sys.executable, "-m", "pytest", "-q"])


if __name__ == "__main__":
    main()
