"""Автоматические тесты CLI-прототипа визуализатора."""

import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from config import parse_cli
import main


class TestConfig(unittest.TestCase):
    """Проверяет разбор и проверку параметров."""

    def prepare_config(self):
        """Подготавливает временную папку и корректные аргументы."""
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.output = Path(self.folder.name) / "graph.svg"
        self.base = [
            "--package", "org.example:demo:1.0",
            "--repository", "https://repo.maven.apache.org/maven2/",
            "--output", str(self.output),
        ]

    def assert_invalid(self, args, option):
        """Проверяет код ошибки и название проблемной опции."""
        errors = io.StringIO()

        with contextlib.redirect_stderr(errors):
            with self.assertRaises(SystemExit) as result:
                parse_cli(args)

        self.assertEqual(result.exception.code, 2)
        self.assertIn(option, errors.getvalue())

    def test_defaults(self):
        """Проверяет значения необязательных параметров."""
        self.prepare_config()
        config = parse_cli(self.base[:-2])

        self.assertEqual(config.package, "org.example:demo:1.0")
        self.assertEqual(config.output, "graph.svg")
        self.assertFalse(config.test_mode)
        self.assertFalse(config.ascii_tree)
        self.assertEqual(config.filter, "")

    def test_all_parameters(self):
        """Проверяет запуск со всеми шестью параметрами."""
        self.prepare_config()
        repository = Path(self.folder.name) / "test repository.json"
        repository.write_text('{"A": []}', encoding="utf-8")

        config = parse_cli([
            "--package", "A",
            "--repository", str(repository),
            "--test-mode",
            "--output", str(self.output),
            "--ascii-tree",
            "--filter", "B",
        ])

        self.assertEqual(config.package, "A")
        self.assertEqual(config.repository, str(repository))
        self.assertTrue(config.test_mode)
        self.assertEqual(config.output, str(self.output))
        self.assertTrue(config.ascii_tree)
        self.assertEqual(config.filter, "B")
        self.assertFalse(self.output.exists())

    def test_errors_for_all_parameters(self):
        """Проверяет ошибочное значение каждого параметра."""
        self.prepare_config()
        cases = [
            ("--package", ["--package", "bad"]),
            ("--repository", ["--repository", "wrong-url"]),
            ("--test-mode", ["--test-mode=false"]),
            ("--output", ["--output", "graph.png"]),
            ("--ascii-tree", ["--ascii-tree=1"]),
            ("--filter", ["--filter", ""]),
        ]

        for option, extra in cases:
            with self.subTest(option=option):
                self.assert_invalid(self.base + extra, option)

    def test_required_parameters(self):
        """Проверяет отсутствие обязательных параметров."""
        self.prepare_config()
        self.assert_invalid([], "--package")
        self.assert_invalid(self.base[2:], "--package")
        self.assert_invalid(self.base[:2], "--repository")

    def test_missing_test_file(self):
        """Проверяет отсутствие файла тестового репозитория."""
        self.prepare_config()
        missing = Path(self.folder.name) / "missing.json"
        args = [
            "--package", "A",
            "--repository", str(missing),
            "--test-mode",
        ]

        self.assert_invalid(args, "--repository")

    def test_invalid_test_package(self):
        """Проверяет запрет строчных букв в тестовом имени."""
        self.prepare_config()
        args = self.base + [
            "--test-mode",
            "--package", "abc",
        ]

        self.assert_invalid(args, "--package")

    def test_missing_output_directory(self):
        """Проверяет отсутствие папки для изображения."""
        self.prepare_config()
        output = Path(self.folder.name) / "missing" / "graph.svg"
        args = self.base + ["--output", str(output)]

        self.assert_invalid(args, "--output")

    def test_unknown_parameter(self):
        """Проверяет обработку неизвестной опции."""
        self.prepare_config()
        self.assert_invalid(self.base + ["--unknown"], "--unknown")


class TestProgram(unittest.TestCase):
    """Проверяет вывод программы при настоящем запуске."""

    def test_output(self):
        """Проверяет граф, фильтр, ASCII-дерево и передачу на экспорт."""
        args = ["main.py", "--package", "A", "--repository",
                "tests/fixtures/repository.json", "--test-mode",
                "--ascii-tree", "--filter", "B"]
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", args):
            with patch("main.export_graph") as exporter:
                exporter.return_value = (ROOT / "graph.mmd", ROOT / "graph.svg")
                with contextlib.redirect_stdout(output):
                    with contextlib.redirect_stderr(errors):
                        code = main.main()
        self.assertEqual(code, main.SUCCESS_EXIT_CODE)
        self.assertEqual(errors.getvalue(), "")
        self.assertEqual(output.getvalue().splitlines()[:8], [
            "Граф зависимостей A:", "A -> C", "C -> (нет зависимостей)",
            "Порядок DFS: A -> C", "Циклов нет.", "ASCII-дерево:",
            "A", "`-- C",
        ])
        self.assertIn("SVG сохранён:", output.getvalue())
        exporter.assert_called_once()


if __name__ == "__main__":
    unittest.main()
