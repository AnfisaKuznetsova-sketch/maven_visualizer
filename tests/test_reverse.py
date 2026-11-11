"""Проверки обратных зависимостей, областей поиска, фильтра и CLI."""

import contextlib
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import main
from config import parse_cli
from reverse import (
    find_reverse_dependencies, print_reverse_dependencies, reverse_adjacency,
)

EXTRA_CHAIN_DEPTH = 100


class TestReverseGraph(unittest.TestCase):
    """Проверяет обратный граф независимо от файлов и сети."""

    def test_reverse_edges_and_isolated_nodes(self):
        """Разворачивает рёбра и сохраняет вершины без потребителей."""
        source = {"A": ["B", "B"], "B": [], "Z": []}
        self.assertEqual(reverse_adjacency(source),
                         {"A": [], "B": ["A"], "Z": []})

    def test_chain(self):
        """Находит прямого и транзитивного потребителей."""
        source = {"A": ["B"], "B": ["C"], "C": []}
        result = find_reverse_dependencies("C", source)
        self.assertEqual(result.adjacency["C"], ["B"])
        self.assertEqual(list(result.adjacency), ["C", "B", "A"])
        self.assertEqual(result.cycles, [])

    def test_shared_dependency_and_separate_root(self):
        """Учитывает потребителей из разных несвязанных корней."""
        source = {"A": ["B", "C"], "B": ["D"], "C": ["D"],
                  "D": [], "E": ["D"], "Z": []}
        result = find_reverse_dependencies("D", source)
        self.assertEqual(result.adjacency["D"], ["B", "C", "E"])
        self.assertEqual(list(result.adjacency), ["D", "B", "A", "C", "E"])
        self.assertEqual(result.cycles, [])

    def test_cycle(self):
        """Останавливается на цикле, сохраняя обратные рёбра."""
        source = {"A": ["B"], "B": ["C"], "C": ["A"]}
        result = find_reverse_dependencies("C", source)
        self.assertEqual(result.cycles, [["C", "B", "A", "C"]])

    def test_self_cycle_output(self):
        """Сам узел не выдаётся за стороннего потребителя в петле."""
        result = find_reverse_dependencies("A", {"A": ["A"]})
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            print_reverse_dependencies("A", result, "тест")
        self.assertEqual(result.cycles, [["A", "A"]])
        self.assertIn("Прямые обратные зависимости: нет", output.getvalue())
        self.assertIn("Все обратные зависимости (DFS): нет", output.getvalue())
        self.assertIn("A -> A", output.getvalue())

    def test_no_consumers(self):
        """Существующий узел без потребителей даёт пустой ответ."""
        result = find_reverse_dependencies("A", {"A": ["B"], "B": []})
        self.assertEqual(result.adjacency, {"A": []})

    def test_excluded_intermediate_node(self):
        """Отсечение посредника исключает путь к его потребителям."""
        source = {"ROOT": ["BLOCK"], "BLOCK": ["TARGET"],
                  "KEEP": ["TARGET"], "TARGET": []}
        result = find_reverse_dependencies("TARGET", source, "BLOCK")
        self.assertEqual(list(result.adjacency), ["TARGET", "KEEP"])

    def test_filtered_target(self):
        """Исключённая цель даёт объяснимый пустой граф."""
        result = find_reverse_dependencies("A", {"A": []}, "A")
        self.assertEqual(result.adjacency, {})

    def test_unknown_target(self):
        """Неизвестная цель не считается существующей вершиной без рёбер."""
        with self.assertRaisesRegex(ValueError, "области анализа"):
            find_reverse_dependencies("Z", {"A": []})

    def test_deep_reverse_chain(self):
        """Обратный поиск использует нерекурсивный DFS для длинной цепи."""
        length = sys.getrecursionlimit() + EXTRA_CHAIN_DEPTH
        source = {str(index): [str(index + 1)] for index in range(length)}
        source[str(length)] = []
        result = find_reverse_dependencies(str(length), source)
        self.assertEqual(len(result.adjacency), length + 1)
        self.assertEqual(list(result.adjacency)[-1], "0")


class TestReverseOptions(unittest.TestCase):
    """Проверяет дополнительные параметры четвёртого этапа."""

    def test_requires_root_for_maven(self):
        """Область поиска для настоящего репозитория обязательна."""
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            with self.assertRaises(SystemExit):
                parse_cli(["--package", "g:lib:1", "--reverse",
                           "--repository", "https://example.org"])
        self.assertIn("--root", errors.getvalue())

    def test_reject_root_without_reverse(self):
        """Не допускает параметр области, который иначе игнорировался бы."""
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            with self.assertRaises(SystemExit):
                parse_cli(["--package", "g:lib:1", "--root", "g:app:1",
                           "--repository", "https://example.org"])
        self.assertIn("--reverse", errors.getvalue())

    def test_invalid_reverse_options(self):
        """Отклоняет значение у флага и неправильное имя корня."""
        base = ["--package", "g:lib:1", "--repository", "https://example.org"]
        for extra in (["--reverse=false"], ["--reverse", "--root", "bad"]):
            with self.subTest(extra=extra):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        parse_cli(base + extra)


class TestReverseMain(unittest.TestCase):
    """Проверяет пользовательский режим и явное ограничение области."""

    def invoke(self, args):
        """Запускает точку входа с перехватом вывода."""
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", ["main.py", *args]):
            with patch("main.export_graph") as exporter:
                exporter.return_value = (ROOT / "graph.mmd", ROOT / "graph.svg")
                with contextlib.redirect_stdout(output):
                    with contextlib.redirect_stderr(errors):
                        code = main.main()
        return code, output.getvalue(), errors.getvalue()

    def test_whole_json_repository(self):
        """Без корня анализирует весь тестовый файл, включая отдельный E."""
        path = ROOT / "tests/fixtures/reverse_shared.json"
        code, output, errors = self.invoke([
            "--package", "D", "--test-mode", "--reverse",
            "--repository", str(path),
        ])
        self.assertEqual(code, main.SUCCESS_EXIT_CODE)
        self.assertEqual(errors, "")
        self.assertIn("весь тестовый репозиторий", output)
        self.assertIn("Все обратные зависимости (DFS): B, A, C, E", output)

    def test_scoped_json_repository(self):
        """С корнем не включает внешнего потребителя из другой компоненты."""
        path = ROOT / "tests/fixtures/reverse_shared.json"
        code, output, errors = self.invoke([
            "--package", "D", "--test-mode", "--reverse", "--root", "A",
            "--repository", str(path),
        ])
        self.assertEqual(code, main.SUCCESS_EXIT_CODE)
        self.assertEqual(errors, "")
        self.assertIn("Область анализа: граф зависимостей A.", output)
        self.assertIn("Все обратные зависимости (DFS): B, A, C\n", output)

    def test_scoped_maven_repository(self):
        """Использует прошлый DFS для прямого и обратного графов Maven."""
        source = {"g:app:1": ["g:lib:1"], "g:lib:1": []}
        with patch("main.MavenRepository") as repository:
            loader = repository.return_value.direct_dependencies
            loader.side_effect = source.__getitem__
            code, output, errors = self.invoke([
                "--package", "g:lib:1", "--root", "g:app:1", "--reverse",
                "--repository", "https://example.org",
            ])
        self.assertEqual(code, main.SUCCESS_EXIT_CODE)
        self.assertEqual(errors, "")
        self.assertIn("Все обратные зависимости (DFS): g:app:1", output)
        self.assertEqual(loader.call_count, len(source))

    def test_missing_target_in_scope(self):
        """Отсутствующая в области цель даёт явную ошибку."""
        path = ROOT / "tests/fixtures/reverse_shared.json"
        code, output, errors = self.invoke([
            "--package", "E", "--root", "A", "--test-mode", "--reverse",
            "--repository", str(path),
        ])
        self.assertEqual(code, main.DATA_ERROR_EXIT_CODE)
        self.assertEqual(output, "")
        self.assertIn("отсутствует в области анализа", errors)


if __name__ == "__main__":
    unittest.main()
