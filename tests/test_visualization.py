"""Проверки Mermaid, SVG, ASCII-дерева и ошибок рендеринга без браузера."""

from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from graph import build_graph
from visualization import (
    ascii_tree, escape_label, export_graph, graph_mermaid, renderer_command,
)

EXTRA_CHAIN_DEPTH = 100
RENDER_ERROR_CODE = 1


class TestMermaid(unittest.TestCase):
    """Проверяет сохранение структуры и корректность подписей."""

    def test_diamond(self):
        """Общая зависимость представлена одним узлом и двумя рёбрами."""
        adjacency = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
        text = graph_mermaid(build_graph("A", adjacency.__getitem__))
        self.assertIn('n2["D"]', text)
        self.assertIn("n1 --> n2", text)
        self.assertIn("n3 --> n2", text)
        self.assertEqual(text.count('["D"]'), 1)

    def test_cycle_and_leaf(self):
        """Исходник содержит петлю и объявления всех листовых вершин."""
        adjacency = {"A": ["A", "B"], "B": []}
        text = graph_mermaid(build_graph("A", adjacency.__getitem__))
        self.assertIn("n0 --> n0", text)
        self.assertIn('n1["B"]', text)

    def test_safe_labels_and_identifiers(self):
        """Спецсимволы подписи не позволяют добавить Mermaid-инструкции."""
        self.assertEqual(escape_label('a"<&#'), "a#34;#60;#38;#35;")
        adjacency = {"end": ["n0"], "n0": []}
        text = graph_mermaid(build_graph("end", adjacency.__getitem__))
        self.assertIn('n0["end"]', text)
        self.assertIn('n1["n0"]', text)

    def test_empty_graph(self):
        """Пустой результат визуализируется поясняющей подписью."""
        text = graph_mermaid(build_graph("A", lambda name: [], "A"))
        self.assertIn("Нет узлов после фильтрации", text)
        self.assertNotIn("-->", text)


class TestAscii(unittest.TestCase):
    """Проверяет ASCII-вывод, повторные узлы и циклы."""

    def test_diamond(self):
        """Общая зависимость второй раз отмечается как seen."""
        adjacency = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
        result = build_graph("A", adjacency.__getitem__)
        self.assertEqual(ascii_tree("A", result),
                         "A\n|-- B\n|   `-- D\n`-- C\n    `-- D [seen]")

    def test_cycle(self):
        """Циклическая ветвь завершается меткой cycle."""
        result = build_graph("A", {"A": ["B"], "B": ["A"]}.__getitem__)
        self.assertEqual(ascii_tree("A", result),
                         "A\n`-- B\n    `-- A [cycle]")

    def test_leaf_and_filtered_root(self):
        """Лист и исключённый корень выводятся без неверных ветвей."""
        result = build_graph("A", lambda name: [])
        self.assertEqual(ascii_tree("A", result), "A")
        result = build_graph("A", lambda name: [], "A")
        self.assertIn("исключён фильтром", ascii_tree("A", result))

    def test_deep_tree(self):
        """Построение дерева не зависит от лимита рекурсии Python."""
        length = sys.getrecursionlimit() + EXTRA_CHAIN_DEPTH
        adjacency = {str(i): [str(i + 1)] for i in range(length)}
        adjacency[str(length)] = []
        text = ascii_tree("0", build_graph("0", adjacency.__getitem__))
        self.assertEqual(len(text.splitlines()), length + 1)


class TestSvgExport(unittest.TestCase):
    """Проверяет файловый контракт и обработку ошибок Mermaid CLI."""

    def export_with(self, output, process):
        """Подменяет только внешний рендерер, сохраняя настоящие файлы."""
        result = build_graph("A", {"A": ["B"], "B": []}.__getitem__)
        with patch("visualization.renderer_command",
                   side_effect=lambda source, target: ["render", str(target)]):
            with patch("visualization.subprocess.run", side_effect=process):
                return export_graph(result, output)

    def success_renderer(self, command, **kwargs):
        """Имитирует корректный SVG от внешнего инструмента."""
        Path(command[-1]).write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"><text>A</text></svg>',
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    def test_files_are_created(self):
        """Создаёт непустые Mermaid и SVG по пути с пробелами."""
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "my graph.svg"
            source, image = self.export_with(output, self.success_renderer)
            self.assertEqual(source, output.with_suffix(".mmd"))
            self.assertIn("flowchart LR", source.read_text(encoding="utf-8"))
            self.assertIn("<svg", image.read_text(encoding="utf-8"))

    def test_failure_preserves_old_svg(self):
        """Ошибка рендерера не уничтожает старое изображение."""
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "graph.svg"
            output.write_text("old image", encoding="utf-8")
            failure = SimpleNamespace(returncode=RENDER_ERROR_CODE,
                                      stdout="", stderr="bad syntax")
            with self.assertRaisesRegex(ValueError, "bad syntax"):
                self.export_with(output, lambda *args, **kwargs: failure)
            self.assertEqual(output.read_text(encoding="utf-8"), "old image")

    def test_timeout(self):
        """Тайм-аут превращается в понятную ошибку."""
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "время"):
                self.export_with(Path(folder) / "graph.svg",
                                 subprocess.TimeoutExpired("render", 90))

    def test_invalid_renderer_output(self):
        """Выход с кодом 0 без SVG не считается успешным рендерингом."""
        def invalid(command, **kwargs):
            """Записывает неправильный корневой XML-элемент."""
            Path(command[-1]).write_text("<html/>", encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "не создал SVG"):
                self.export_with(Path(folder) / "graph.svg", invalid)

    def test_missing_node(self):
        """Отсутствие Node сопровождается инструкцией установки."""
        with patch("visualization.shutil.which", return_value=None):
            with self.assertRaisesRegex(ValueError, "npm install"):
                renderer_command(Path("graph.mmd"), Path("graph.svg"))


if __name__ == "__main__":
    unittest.main()
