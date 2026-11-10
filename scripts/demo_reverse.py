"""Демонстрация прямых и транзитивных обратных зависимостей без сети."""

import os
from pathlib import Path
import subprocess
import sys

SUCCESS_EXIT_CODE = 0
DATA_ERROR_EXIT_CODE = 1
ROOT = Path(__file__).resolve().parents[1]


def cases():
    """Задаёт сценарии и ожидаемые признаки корректного обратного поиска."""
    examples = [
        ("Цепочка", "chain.json", "C", [], "(DFS): B, A"),
        ("Общие и отдельные потребители", "reverse_shared.json", "D", [],
         "(DFS): B, A, C, E"),
        ("Ограничение корнем", "reverse_shared.json", "D", ["--root", "A"],
         "(DFS): B, A, C"),
        ("Цикл", "cycle.json", "C", [], "C -> B -> A -> C"),
        ("Петля", "self_cycle.json", "A", [], "Циклы в обратном графе:"),
        ("Нет потребителей", "reverse_shared.json", "Z", [], "(DFS): нет"),
        ("Фильтрация", "reverse_filter.json", "TARGET", ["--filter", "BLOCK"],
         "(DFS): KEEP"),
        ("Исключённая цель", "chain.json", "C", ["--filter", "C"],
         "Пакет исключён фильтром."),
    ]
    for title, filename, package, extra, expected in examples:
        args = ["--package", package, "--test-mode", "--reverse",
                "--repository", f"tests/fixtures/{filename}", *extra]
        yield title, args, SUCCESS_EXIT_CODE, expected
    yield "Ошибка: нет целевого пакета", [
        "--package", "Z", "--test-mode", "--reverse", "--repository",
        "tests/fixtures/chain.json",
    ], DATA_ERROR_EXIT_CODE, "отсутствует в области анализа"


def run_case(title, args, expected_code, expected_text):
    """Проверяет реальный CLI по коду завершения и содержимому вывода."""
    command = [sys.executable, str(ROOT / "src/main.py"), *args]
    print(f"\n{title}")
    print(subprocess.list2cmdline(command))
    result = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    output = result.stdout + result.stderr
    print(output.rstrip())
    passed = result.returncode == expected_code and expected_text in output
    status = "OK" if passed else "FAIL"
    print(f"[{status}] Код {result.returncode}; ожидается {expected_code}")
    return passed


def main():
    """Выполняет все примеры и выводит общий итог."""
    examples = list(cases())
    passed = sum(run_case(*case) for case in examples)
    print(f"\nИтог: пройдено {passed} из {len(examples)} проверок.")
    if passed == len(examples):
        return SUCCESS_EXIT_CODE
    return DATA_ERROR_EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
