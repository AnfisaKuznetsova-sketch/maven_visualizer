"""CLI пятого этапа: граф, Mermaid, SVG и необязательное ASCII-дерево."""

import sys

from config import parse_cli
from graph import build_graph, print_graph
from maven import MavenRepository
from repository import JsonRepository
from reverse import find_reverse_dependencies, print_reverse_dependencies
from visualization import ascii_tree, export_graph

SUCCESS_EXIT_CODE = 0
DATA_ERROR_EXIT_CODE = 1


def make_repository(config):
    """Выбирает источник прямых зависимостей для общего алгоритма DFS."""
    if config.test_mode:
        return JsonRepository(config.repository)
    return MavenRepository(config.repository)


def analyse_reverse(config, repository):
    """Определяет область поиска и выполняет обратный обход."""
    if config.root:
        source = build_graph(config.root, repository.direct_dependencies,
                             config.filter).adjacency
        scope = f"граф зависимостей {config.root}"
    else:
        source = repository.graph
        scope = "весь тестовый репозиторий"
    result = find_reverse_dependencies(config.package, source, config.filter)
    return result, scope


def display_result(config, result, scope, source, image):
    """Выводит граф выбранного направления и пути созданных файлов."""
    if config.reverse:
        print_reverse_dependencies(config.package, result, scope)
    else:
        print_graph(config.package, result)
    if config.ascii_tree:
        print("ASCII-дерево:")
        print(ascii_tree(config.package, result))
    print(f"Mermaid сохранён: {source.resolve()}")
    print(f"SVG сохранён: {image.resolve()}")


def main():
    """Строит граф и сохраняет изображение либо возвращает ошибку."""
    config = parse_cli()
    scope = ""
    try:
        repository = make_repository(config)
        if config.reverse:
            result, scope = analyse_reverse(config, repository)
        else:
            result = build_graph(config.package, repository.direct_dependencies,
                                 config.filter)
        source, image = export_graph(result, config.output)
    except ValueError as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return DATA_ERROR_EXIT_CODE
    display_result(config, result, scope, source, image)
    return SUCCESS_EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
