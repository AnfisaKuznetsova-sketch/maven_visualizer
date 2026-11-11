"""Отдельное сравнение с Maven dependency:tree; основной код Maven не зовёт."""

import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from graph import build_graph
from maven import MavenRepository, load_pom
from visualization import export_graph, graph_mermaid

REPOSITORY = "https://repo.maven.apache.org/maven2/"
PLUGIN_GOAL = "org.apache.maven.plugins:maven-dependency-plugin:3.8.1:tree"
NATIVE_TIMEOUT = 240
SCOPES = {"compile", "test", "runtime", "provided", "system", "import"}
EXAMPLES = (
    ("junit", "junit:junit:4.13.2"),
    ("hamcrest", "org.hamcrest:hamcrest-library:1.3"),
    ("slf4j", "org.slf4j:slf4j-simple:1.7.36"),
)


def normalize_coordinate(label):
    """Убирает тип, classifier и scope из подписи узла Maven DOT."""
    parts = label.split(":")
    version = parts[-2] if parts[-1].split()[0] in SCOPES else parts[-1]
    return ":".join((parts[0], parts[1], version))


def dot_edges(text):
    """Извлекает ориентированные рёбра штатного DOT-вывода Maven."""
    matches = re.findall(r'"([^"]+)"\s*->\s*"([^"]+)"', text)
    return {(normalize_coordinate(source), normalize_coordinate(target))
            for source, target in matches}


def explain_difference(package):
    """Объясняет наблюдаемые отличия выбранных демонстрационных пакетов."""
    explanations = {
        "junit:junit:4.13.2":
            "Связь hamcrest-library -> hamcrest-core повторяет уже выбранную "
            "зависимость. В обычном дереве Maven это повторное ребро опущено, "
            "а в полном графе объявленных зависимостей оно сохранено.",
        "org.slf4j:slf4j-simple:1.7.36":
            "Связи junit -> hamcrest-library и slf4j-api -> junit имеют "
            "scope=test в POM этих пакетов и не передаются транзитивно Maven. "
            "Наш анализ всех scopes сохраняет их и дополнительное ребро "
            "hamcrest-library -> hamcrest-core. Maven также различает "
            "slf4j-api.jar и test-jar с classifier=tests; наш идентификатор "
            "G:A:V объединяет эти варианты. Полные подписи видны в DOT ниже.",
    }
    return explanations.get(package, "Множества рёбер совпадают.")


def native_tree(maven, package, folder):
    """Запускает Maven только как независимый эталон для сравнения."""
    pom = folder / "project.pom"
    pom.write_bytes(load_pom(package, REPOSITORY))
    target = folder / "native.dot"
    cache = ROOT / "output/maven-cache"
    command = [maven, "-B", "-f", str(pom), PLUGIN_GOAL,
               "-DoutputType=dot", f"-DoutputFile={target}",
               "-DoutputEncoding=UTF-8", f"-Dmaven.repo.local={cache}"]
    process = subprocess.run(command, capture_output=True, text=True,
                             encoding="utf-8", errors="replace",
                             timeout=NATIVE_TIMEOUT, check=False)
    log = process.stdout + process.stderr
    (folder / "maven.log").write_text(log, encoding="utf-8")
    if process.returncode or not target.is_file():
        log_path = folder / "maven.log"
        raise ValueError(f"Сравнение Maven не выполнено: {log_path}")
    text = target.read_text(encoding="utf-8")
    return dot_edges(text), text


def comparison_section(package, graph, native, native_text):
    """Формирует проверяемый отчёт с диаграммой и разницей множеств рёбер."""
    own = {(source, target) for source, targets in graph.adjacency.items()
           for target in targets}
    native_text = "\n".join(line.rstrip()
                            for line in native_text.splitlines())
    raw_edges = re.findall(r'"([^"]+)"\s*->\s*"([^"]+)"', native_text)
    lines = [f"## {package}", "", "```mermaid", graph_mermaid(graph).strip(),
             "```", "", f"Наш граф: узлы — {len(graph.adjacency)}, "
             f"рёбра — {len(own)}. Maven DOT: исходные рёбра — "
             f"{len(raw_edges)}, после нормализации G:A:V — {len(native)}.", ""]
    for title, edges in (("Только в нашем графе", own - native),
                         ("Только в Maven DOT", native - own)):
        lines.append(title + ":")
        lines.extend(f"- `{source} -> {target}`"
                     for source, target in sorted(edges))
        if not edges:
            lines.append("- Нет.")
        lines.append("")
    lines.extend([explain_difference(package), "", "Штатный DOT Maven:",
                  "", "```dot", native_text.strip(), "```"])
    return "\n".join(lines)


def main():
    """Сравнивает три пакета и сохраняет отчёт с настоящими результатами."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--maven", default=shutil.which("mvn"))
    args = parser.parse_args()
    if not args.maven:
        parser.error("укажите путь к Maven через --maven")
    version = subprocess.run([args.maven, "-version"], capture_output=True,
                             text=True, encoding="utf-8", errors="replace",
                             timeout=NATIVE_TIMEOUT, check=True)
    version_line = version.stdout.splitlines()[0]
    sections = []
    for name, package in EXAMPLES:
        folder = ROOT / "output/comparison" / name
        folder.mkdir(parents=True, exist_ok=True)
        repository = MavenRepository(REPOSITORY)
        graph = build_graph(package, repository.direct_dependencies)
        export_graph(graph, folder / "ours.svg")
        native, native_text = native_tree(args.maven, package, folder)
        sections.append(comparison_section(package, graph, native, native_text))
        print(f"Сравнение завершено: {package}", flush=True)
    report = ROOT / "examples/README.md"
    report.parent.mkdir(exist_ok=True)
    heading = "# Примеры Mermaid и сравнение с Maven\n\n"
    heading += f"Эталон: {version_line}; Maven Dependency Plugin 3.8.1, "
    heading += "`dependency:tree -DoutputType=dot`.\n\n"
    heading += "Для сравнения координаты нормализованы к G:A:V. Тип, "
    heading += "classifier и scope опущены; варианты с одинаковыми G:A:V "
    heading += "объединены. Исходный DOT приведён для проверки.\n\n"
    report.write_text(heading + "\n\n".join(sections) + "\n", encoding="utf-8")
    print(f"Отчёт сохранён: {report}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        print(f"Ошибка сравнения: {error}", file=sys.stderr)
        sys.exit(1)
