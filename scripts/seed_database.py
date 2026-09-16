"""Preview or apply the supplied Bright Path seed data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bright_path.settings import DATABASE_PATH, SOURCE_DATA_DIR
from bright_path.storage.seed import import_source, preview_source


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("preview", "apply"), default="preview")
    parser.add_argument("--source-dir", type=Path, default=SOURCE_DATA_DIR)
    parser.add_argument("--database", type=Path, default=DATABASE_PATH)
    return parser.parse_args()


def main() -> None:
    arguments = parse_args()
    if arguments.mode == "preview":
        summary = {"mode": "preview", **preview_source(arguments.source_dir).summary()}
    else:
        result = import_source(arguments.database, arguments.source_dir)
        summary = {"mode": "apply", **result.summary()}
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
