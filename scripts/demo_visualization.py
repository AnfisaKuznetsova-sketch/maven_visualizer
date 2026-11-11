"""Создание пяти SVG-примеров, включая три настоящих пакета Maven."""

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SUCCESS_EXIT_CODE = 0
DEMO_ERROR_EXIT_CODE = 1


def examples():
    """Возвращает примеры с отдельным SVG для каждого пакета или графа."""
    for name, filename in (("diamond", "diamond.json"),
                           ("cycle", "cycle.json")):
        yield name, ["--package", "A", "--test-mode", "--repository",
                     f"tests/fixtures/{filename}"]
    for name, package in (
        ("junit", "junit:junit:4.13.2"),
        ("hamcrest", "org.hamcrest:hamcrest-library:1.3"),
        ("slf4j", "org.slf4j:slf4j-simple:1.7.36"),
    ):
        yield name, ["--package", package, "--repository",
                     "https://repo.maven.apache.org/maven2/"]


def main():
    """Генерирует примеры и проверяет создание SVG и исходников Mermaid."""
    folder = ROOT / "output/examples"
    folder.mkdir(parents=True, exist_ok=True)
    for name, args in examples():
        output = folder / f"{name}.svg"
        command = [sys.executable, str(ROOT / "src/main.py"), *args,
                   "--output", str(output), "--ascii-tree"]
        print(f"\nПример: {name}", flush=True)
        result = subprocess.run(
            command, cwd=ROOT, check=False,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        if result.returncode or not output.is_file():
            return DEMO_ERROR_EXIT_CODE
    print(f"\nПять SVG-примеров сохранены: {folder}")
    return SUCCESS_EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
