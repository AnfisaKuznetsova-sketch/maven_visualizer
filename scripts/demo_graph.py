"""Демонстрация третьего этапа на тестовых графах без интернета."""

import os
from pathlib import Path
import subprocess
import sys

SUCCESS_EXIT_CODE = 0
DATA_ERROR_EXIT_CODE = 1
ROOT = Path(__file__).resolve().parents[1]


def cases():
    """Задаёт сценарии, параметры, коды и ожидаемые фрагменты вывода."""
    examples = [
        ("Цепочка", "chain.json", [], "Порядок DFS: A -> B -> C"),
        ("Общая зависимость", "diamond.json", [],
         "Порядок DFS: A -> B -> D -> C"),
        ("Цикл", "cycle.json", [], "A -> B -> C -> A"),
        ("Петля", "self_cycle.json", [], "Обнаружены циклы:"),
        ("Фильтрация ветви", "filter.json", ["--filter", "BLOCK"],
         "Порядок DFS: A -> KEEP -> LEAF"),
        ("Исключение корня", "chain.json", ["--filter", "A"],
         "Начальный пакет исключён фильтром."),
        ("Без зависимостей", "chain.json", ["--package", "C"],
         "C -> (нет зависимостей)"),
    ]
    for title, filename, extra, expected in examples:
        args = ["--package", "A", "--test-mode", "--repository",
                f"tests/fixtures/{filename}", *extra]
        yield title, args, SUCCESS_EXIT_CODE, expected
    yield "Ошибка: отсутствует узел", [
        "--package", "A", "--test-mode", "--repository",
        "tests/fixtures/missing_node.json",
    ], DATA_ERROR_EXIT_CODE, "Неизвестная зависимость"


def run_case(title, args, expected_code, expected_text):
    """Запускает реальный CLI и проверяет код и содержание результата."""
    command = [sys.executable, str(ROOT / "src/main.py"), *args]
    print(f"\n{title}")
    print(subprocess.list2cmdline(command))
    result = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    print((result.stdout + result.stderr).rstrip())
    valid_code = result.returncode == expected_code
    valid_text = expected_text in result.stdout + result.stderr
    passed = valid_code and valid_text
    status = "OK" if passed else "FAIL"
    print(f"[{status}] Код {result.returncode}; ожидается {expected_code}")
    return passed


def main():
    """Показывает все сценарии и суммирует результаты проверок."""
    examples = list(cases())
    passed = sum(run_case(*case) for case in examples)
    print(f"\nИтог: пройдено {passed} из {len(examples)} проверок.")
    if passed == len(examples):
        return SUCCESS_EXIT_CODE
    return DATA_ERROR_EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
