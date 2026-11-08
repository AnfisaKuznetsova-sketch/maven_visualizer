"""Демонстрирует успешные запуски и ошибки всех шести параметров."""

import os
from pathlib import Path
import subprocess
import sys

SUCCESS_EXIT_CODE = 0
INVALID_ARGUMENTS_EXIT_CODE = 2
DEMO_FAILURE_EXIT_CODE = 1

ROOT = Path(__file__).resolve().parents[1]
BASE = [
    "--package", "junit:junit:4.13.2",
    "--repository", "https://repo.maven.apache.org/maven2/",
]


def scenarios():
    """Возвращает названия, аргументы и ожидаемые коды завершения."""
    yield "Maven: значения по умолчанию", BASE, SUCCESS_EXIT_CODE

    yield "Все параметры: тестовый режим", [
        "--package", "A",
        "--repository", "tests/fixtures/repository.json",
        "--test-mode",
        "--output", "demo.svg",
        "--ascii-tree",
        "--filter", "B",
    ], SUCCESS_EXIT_CODE

    errors = [
        ("--package", ["--package", "bad"]),
        ("--repository", ["--repository", "bad-url"]),
        ("--test-mode", ["--test-mode=false"]),
        ("--output", ["--output", "graph.png"]),
        ("--ascii-tree", ["--ascii-tree=1"]),
        ("--filter", ["--filter", ""]),
    ]
    for option, args in errors:
        yield f"Ошибка {option}", BASE + args, INVALID_ARGUMENTS_EXIT_CODE

    yield "Отсутствует тестовый файл", [
        "--package", "A",
        "--test-mode",
        "--repository", "missing.json",
    ], INVALID_ARGUMENTS_EXIT_CODE


def run_case(title, args, expected):
    """Показывает результат примера и отличает ожидаемую ошибку от сбоя."""
    command = [sys.executable, str(ROOT / "src" / "main.py"), *args]
    print(f"\n{title}")
    if expected == INVALID_ARGUMENTS_EXIT_CODE:
        print("Ожидается отказ: намеренно переданы неверные параметры.")
    else:
        print("Ожидается успешный запуск.")
    print(subprocess.list2cmdline(command))
    result = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print("Сообщение программы:")
        print(result.stderr.rstrip())
    passed = result.returncode == expected
    status = "OK" if passed else "FAIL"
    print(f"[{status}] Код: {result.returncode}; ожидаемый: {expected}")
    return passed


def main():
    """Запускает все примеры и выводит итог демонстрации."""
    print("Демонстрация: успешные запуски и обработка неверных параметров.")
    print("Ошибки в отрицательных примерах ожидаемы и проверяются.")
    cases = list(scenarios())
    passed = sum(run_case(*case) for case in cases)
    print(f"\nИтог: пройдено {passed} из {len(cases)} проверок.")
    if passed == len(cases):
        print("Все проверки пройдены. Ожидаемые ошибки обработаны верно.")
        return SUCCESS_EXIT_CODE
    print("Есть неожиданные результаты: см. строки [FAIL] выше.")
    return DEMO_FAILURE_EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
