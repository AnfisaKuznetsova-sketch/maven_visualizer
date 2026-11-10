"""Проверки итеративного DFS, транзитивности, фильтра и циклов."""

import contextlib
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from graph import build_graph, print_graph
from repository import JsonRepository

EXTRA_CHAIN_DEPTH = 100


class TestDfs(unittest.TestCase):
    """Проверяет граф независимо от сети и формата репозитория."""

    def test_dfs_order_and_shared_dependency(self):
        """Обходит общую зависимость один раз и именно в глубину."""
        graph = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
        loader = Mock(side_effect=graph.__getitem__)
        result = build_graph("A", loader)
        self.assertEqual(list(result.adjacency), ["A", "B", "D", "C"])
        self.assertEqual(result.adjacency, graph)
        self.assertEqual(result.cycles, [])
        self.assertEqual(loader.call_count, len(graph))

    def test_cycle_and_reachable_leaf(self):
        """Сохраняет циклическое ребро и продолжает обход остальных узлов."""
        graph = {"A": ["B"], "B": ["C", "D"], "C": ["A"], "D": []}
        result = build_graph("A", graph.__getitem__)
        self.assertEqual(result.adjacency, graph)
        self.assertEqual(result.cycles, [["A", "B", "C", "A"]])

    def test_self_cycle(self):
        """Обрабатывает зависимость пакета от самого себя."""
        result = build_graph("A", {"A": ["A"]}.__getitem__)
        self.assertEqual(result.cycles, [["A", "A"]])

    def test_several_cycles(self):
        """Находит обратные рёбра в разных ветвях обхода."""
        graph = {"A": ["B", "C"], "B": ["A"], "C": ["C"]}
        result = build_graph("A", graph.__getitem__)
        self.assertEqual(result.cycles, [["A", "B", "A"], ["C", "C"]])

    def test_excluded_node_is_not_loaded(self):
        """Отсекает узел и его отдельную ветвь до обращения к загрузчику."""
        graph = {"A": ["BLOCK", "B"], "B": []}
        loader = Mock(side_effect=graph.__getitem__)
        result = build_graph("A", loader, "BLOCK")
        self.assertEqual(result.adjacency, {"A": ["B"], "B": []})
        self.assertEqual([call.args[0] for call in loader.call_args_list],
                         ["A", "B"])

    def test_shared_node_survives_filter(self):
        """Сохраняет узел, доступный по другому неотфильтрованному пути."""
        graph = {"A": ["BLOCK", "B"], "B": ["C"], "C": []}
        result = build_graph("A", graph.__getitem__, "BLOCK")
        self.assertEqual(list(result.adjacency), ["A", "B", "C"])

    def test_filtered_root(self):
        """Исключение начального пакета даёт пустой граф без загрузок."""
        loader = Mock()
        result = build_graph("ROOT", loader, "ROOT")
        self.assertEqual(result.adjacency, {})
        self.assertEqual(result.cycles, [])
        loader.assert_not_called()

    def test_filter_matches_substring_and_case(self):
        """Фильтрация чувствительна к регистру и ищет подстроку."""
        graph = {"A": ["XXBLOCKYY", "B"], "B": []}
        result = build_graph("A", graph.__getitem__, "BLOCK")
        self.assertEqual(list(result.adjacency), ["A", "B"])
        graph = {"A": ["B"], "B": []}
        result = build_graph("A", graph.__getitem__, "b")
        self.assertIn("B", result.adjacency)

    def test_duplicate_edges(self):
        """Удаляет повторные рёбра до помещения узлов в стек."""
        graph = {"A": ["B", "B"], "B": []}
        result = build_graph("A", graph.__getitem__)
        self.assertEqual(result.adjacency, {"A": ["B"], "B": []})

    def test_deep_chain(self):
        """Цепь длиннее лимита рекурсии Python обходится успешно."""
        length = sys.getrecursionlimit() + EXTRA_CHAIN_DEPTH
        graph = {str(index): [str(index + 1)] for index in range(length)}
        graph[str(length)] = []
        result = build_graph("0", graph.__getitem__)
        self.assertEqual(len(result.adjacency), length + 1)
        self.assertEqual(result.cycles, [])

    def test_loader_error_is_not_hidden(self):
        """Сбой в транзитивном узле не выдаёт частичный граф за полный."""
        loader = Mock(side_effect=[["B"], ValueError("Нет POM B")])
        with self.assertRaisesRegex(ValueError, "Нет POM B"):
            build_graph("A", loader)

class TestGraphFixtures(unittest.TestCase):
    """Проверяет реальные файлы тестовых репозиториев."""

    def test_fixture_results(self):
        """Проверяет цепь, ромб, цикл, петлю и фильтрацию на JSON."""
        cases = [
            ("chain.json", "", ["A", "B", "C"], []),
            ("diamond.json", "", ["A", "B", "D", "C"], []),
            ("cycle.json", "", ["A", "B", "C"], [["A", "B", "C", "A"]]),
            ("self_cycle.json", "", ["A"], [["A", "A"]]),
            ("filter.json", "BLOCK", ["A", "KEEP", "LEAF"], []),
        ]
        for filename, excluded, order, cycles in cases:
            with self.subTest(filename=filename):
                repository = JsonRepository(ROOT / "tests/fixtures" / filename)
                result = build_graph("A", repository.direct_dependencies,
                                     excluded)
                self.assertEqual(list(result.adjacency), order)
                self.assertEqual(result.cycles, cycles)

    def test_repository_is_read_once(self):
        """Запросы транзитивных соседей не читают файл повторно."""
        path = ROOT / "tests/fixtures/chain.json"
        repository = JsonRepository(path)
        with patch("repository.read_graph", side_effect=ValueError("again")):
            result = build_graph("A", repository.direct_dependencies)
        self.assertEqual(list(result.adjacency), ["A", "B", "C"])

    def test_cycle_output(self):
        """Пользователь видит рёбра, порядок обхода и найденный цикл."""
        result = build_graph("A", {"A": ["A"]}.__getitem__)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            print_graph("A", result)
        self.assertIn("A -> A", output.getvalue())
        self.assertIn("Обнаружены циклы:", output.getvalue())

    def test_filtered_root_output(self):
        """Вывод явно объясняет пустой граф при исключении корня."""
        result = build_graph("A", Mock(), "A")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            print_graph("A", result)
        self.assertIn("исключён фильтром", output.getvalue())


if __name__ == "__main__":
    unittest.main()
