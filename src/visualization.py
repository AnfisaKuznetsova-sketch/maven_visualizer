"""Представление графа на Mermaid, рендеринг SVG и ASCII-дерево."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
RENDER_TIMEOUT = 90
LABEL_CHARACTERS = " .:_-+"


def escape_label(text):
    """Экранирует специальные символы числовыми сущностями Mermaid."""
    return "".join(char if char.isalnum() or char in LABEL_CHARACTERS
                   else f"#{ord(char)};" for char in text)


def graph_mermaid(result):
    """Сохраняет все узлы и рёбра, включая общие зависимости и циклы."""
    lines = ["flowchart LR"]
    identifiers = {name: f"n{index}"
                   for index, name in enumerate(result.adjacency)}
    if not identifiers:
        lines.append('    empty["Нет узлов после фильтрации"]')
    for name, identifier in identifiers.items():
        lines.append(f'    {identifier}["{escape_label(name)}"]')
    for source, dependencies in result.adjacency.items():
        for target in dict.fromkeys(dependencies):
            lines.append(f"    {identifiers[source]} --> {identifiers[target]}")
    return "\n".join(lines) + "\n"


def renderer_command(source, target):
    """Запускает локальный Mermaid CLI через Node без командной оболочки."""
    node = shutil.which("node")
    cli = ROOT / "node_modules/@mermaid-js/mermaid-cli/src/cli.js"
    if not node or not cli.is_file():
        raise ValueError("Для SVG установите Node.js и выполните npm install")
    return [node, str(cli), "-i", str(source), "-o", str(target),
            "-c", str(ROOT / "mermaid-config.json"), "-b", "white"]


def render_svg(source, target):
    """Проверяет настоящий SVG перед заменой итогового файла."""
    try:
        with tempfile.TemporaryDirectory(dir=target.parent) as folder:
            temporary = Path(folder) / "rendered.svg"
            command = renderer_command(source, temporary)
            process = subprocess.run(command, capture_output=True, text=True,
                                     encoding="utf-8", errors="replace",
                                     timeout=RENDER_TIMEOUT, check=False)
            if process.returncode:
                details = process.stderr.strip() or process.stdout.strip()
                raise ValueError(f"Ошибка Mermaid CLI: {details}")
            root = ET.parse(temporary).getroot()
            if root.tag.rsplit("}", 1)[-1] != "svg":
                raise ValueError("Mermaid CLI не создал SVG")
            temporary.replace(target)
    except subprocess.TimeoutExpired as error:
        raise ValueError("Превышено время создания SVG") from error
    except (OSError, ET.ParseError) as error:
        raise ValueError(f"Не удалось сохранить SVG: {error}") from error


def export_graph(result, output):
    """Сохраняет исходник .mmd рядом с изображением .svg."""
    target = Path(output)
    source = target.with_suffix(".mmd")
    try:
        source.write_text(graph_mermaid(result), encoding="utf-8")
    except OSError as error:
        raise ValueError(f"Не удалось сохранить Mermaid: {error}") from error
    render_svg(source, target)
    return source, target


def tree_frames(children, prefix, ancestors):
    """Готовит события дочерних ветвей в обратном порядке для стека."""
    return [(name, prefix, index == len(children) - 1, ancestors)
            for index, name in reversed(list(enumerate(children)))]


def tree_marker(node, ancestors, visited):
    """Различает цикл текущего пути и уже показанную общую зависимость."""
    if node in ancestors:
        return " [cycle]"
    if node in visited:
        return " [seen]"
    return ""


def ascii_tree(package, result):
    """Формирует дерево без рекурсии; отмечает циклы и повторные узлы."""
    if package not in result.adjacency:
        return "Дерево пусто: пакет исключён фильтром."
    lines, visited = [package], {package}
    stack = tree_frames(result.adjacency[package], "", (package,))
    while stack:
        node, prefix, last, ancestors = stack.pop()
        connector = "`-- " if last else "|-- "
        marker = tree_marker(node, ancestors, visited)
        lines.append(prefix + connector + node + marker)
        if marker:
            continue
        visited.add(node)
        next_prefix = prefix + ("    " if last else "|   ")
        stack.extend(tree_frames(result.adjacency[node], next_prefix,
                                 ancestors + (node,)))
    return "\n".join(lines)
