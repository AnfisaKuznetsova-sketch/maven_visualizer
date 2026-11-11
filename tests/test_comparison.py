"""Проверки нормализации штатного DOT Maven для отчёта сравнения."""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from compare_maven import dot_edges, normalize_coordinate


class TestComparison(unittest.TestCase):
    """Проверяет явно описанную потерю type/classifier при сравнении G:A:V."""

    def test_scope_and_classifier(self):
        """Версия не путается с classifier или scope."""
        self.assertEqual(normalize_coordinate("g:a:jar:1.0:compile"), "g:a:1.0")
        self.assertEqual(normalize_coordinate("g:a:test-jar:tests:1.0:test"),
                         "g:a:1.0")
        self.assertEqual(normalize_coordinate("g:a:jar:1.0"), "g:a:1.0")

    def test_variant_edges_are_normalized(self):
        """Два ребра к разным вариантам артефакта сводятся к одному G:A:V."""
        text = '''digraph "g:app:jar:1" {
            "g:app:jar:1" -> "g:lib:jar:2:compile";
            "g:app:jar:1" -> "g:lib:test-jar:tests:2:test";
        }'''
        self.assertEqual(dot_edges(text), {("g:app:1", "g:lib:2")})


if __name__ == "__main__":
    unittest.main()
