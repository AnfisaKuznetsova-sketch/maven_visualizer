"""CLI третьего этапа: граф зависимостей, DFS, фильтрация и циклы."""

import sys

from config import parse_cli
from graph import build_graph, print_graph
from maven import MavenRepository
from repository import JsonRepository

SUCCESS_EXIT_CODE = 0
DATA_ERROR_EXIT_CODE = 1


def make_repository(config):
    """Выбирает источник прямых зависимостей для общего алгоритма DFS."""
    if config.test_mode:
        return JsonRepository(config.repository)
    return MavenRepository(config.repository)


def main():
    """Строит полный граф и выводит результат либо понятную ошибку."""
    config = parse_cli()
    try:
        repository = make_repository(config)
        result = build_graph(
            config.package, repository.direct_dependencies, config.filter,
        )
    except ValueError as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return DATA_ERROR_EXIT_CODE
    print_graph(config.package, result)
    return SUCCESS_EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
