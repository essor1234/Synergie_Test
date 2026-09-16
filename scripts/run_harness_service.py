from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

SERVICES = {
    "api": ("bright_path.api.server", "run"),
    "ui": ("bright_path.ui.server", "run"),
}


def run_service(service_name: str) -> None:
    if service_name not in SERVICES:
        raise SystemExit(f"Unknown harness service: {service_name}")

    project_root = Path(__file__).resolve().parents[1]
    source_root = project_root / "src"
    log_directory = project_root / "data" / "harness"
    log_directory.mkdir(parents=True, exist_ok=True)
    os.chdir(project_root)
    sys.path.insert(0, str(source_root))

    module_name, function_name = SERVICES[service_name]
    with (
        (log_directory / f"{service_name}.out.log").open(
            "a", encoding="utf-8", buffering=1
        ) as output,
        (log_directory / f"{service_name}.err.log").open(
            "a", encoding="utf-8", buffering=1
        ) as error,
    ):
        sys.stdout = output
        sys.stderr = error
        module = importlib.import_module(module_name)
        getattr(module, function_name)()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: run_harness_service.py <service>")
    run_service(sys.argv[1])
