"""Проверки тестового JSON и CLI третьего этапа без внешней сети."""

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import main
from repository import test_dependencies, validate_graph


class TestGraph(unittest.TestCase):
    """Проверяет формат графа и получение прямых соседей."""

    def test_direct_only_and_cycles(self):
        """Не обходит транзитивные и циклические связи."""
        graph = {"A": ["B", "B"], "B": ["A", "C"], "C": []}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "repo.json"
            path.write_text(json.dumps(graph), encoding="utf-8")
            self.assertEqual(test_dependencies("A", path), ["B"])
            self.assertEqual(test_dependencies("C", path), [])

    def test_bad_graphs(self):
        """Отклоняет неправильные типы, имена и отсутствующие узлы."""
        for graph in ([], {"a": []}, {"A": "B"}, {"A": ["B"]},
                      {"A": [1]}):
            with self.subTest(graph=graph):
                with self.assertRaises(ValueError):
                    validate_graph(graph)

    def test_bad_json_and_missing_package(self):
        """Обрабатывает повреждённый файл и неизвестный пакет."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "repo.json"
            path.write_text("not json", encoding="utf-8")
            with self.assertRaises(ValueError):
                test_dependencies("A", path)
            path.write_text('{"A": []}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "отсутствует"):
                test_dependencies("B", path)


class TestMain(unittest.TestCase):
    """Проверяет пользовательский вывод и сообщения об ошибках."""

    def invoke(self, args):
        """Запускает точку входа с перехватом потоков."""
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", ["main.py", *args]):
            with patch("main.export_graph") as exporter:
                exporter.return_value = (ROOT / "graph.mmd", ROOT / "graph.svg")
                with contextlib.redirect_stdout(output):
                    with contextlib.redirect_stderr(errors):
                        code = main.main()
        return code, output.getvalue(), errors.getvalue()

    def test_real_mode_calls_maven(self):
        """Обычный режим вызывает собственный анализатор Maven."""
        with patch("main.MavenRepository") as repository:
            instance = repository.return_value
            graph = {"g:app:1": ["g:lib:2"], "g:lib:2": []}
            instance.direct_dependencies.side_effect = graph.__getitem__
            code, output, errors = self.invoke([
                "--package", "g:app:1", "--repository", "https://example.org",
            ])
        self.assertEqual(code, main.SUCCESS_EXIT_CODE)
        self.assertIn("g:lib:2", output)
        self.assertEqual(errors, "")
        self.assertEqual(instance.direct_dependencies.call_count, len(graph))

    def test_data_error(self):
        """Ошибка загрузки возвращает код 1 без traceback."""
        with patch("main.MavenRepository") as repository:
            instance = repository.return_value
            instance.direct_dependencies.side_effect = ValueError("HTTP 404")
            code, output, errors = self.invoke([
                "--package", "g:app:1", "--repository", "https://example.org",
            ])
        self.assertEqual(code, main.DATA_ERROR_EXIT_CODE)
        self.assertEqual(output, "")
        self.assertIn("HTTP 404", errors)
        self.assertNotIn("Traceback", errors)

    def test_empty_result(self):
        """Для пустого списка зависимостей выводится понятное сообщение."""
        with patch("main.JsonRepository") as repository:
            repository.return_value.direct_dependencies.return_value = []
            code, output, errors = self.invoke([
                "--package", "C", "--test-mode", "--repository",
                str(ROOT / "tests" / "fixtures" / "repository.json"),
            ])
        self.assertEqual(code, main.SUCCESS_EXIT_CODE)
        self.assertIn("(нет зависимостей)", output)
        self.assertEqual(errors, "")


if __name__ == "__main__":
    unittest.main()
