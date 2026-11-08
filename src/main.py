"""CLI второго этапа: получение и вывод прямых зависимостей Maven."""

import sys

from config import parse_cli
from maven import MavenRepository
from repository import test_dependencies

SUCCESS_EXIT_CODE = 0
DATA_ERROR_EXIT_CODE = 1


def main():
    """Читает параметры и выводит зависимости; ошибки направляет в stderr."""
    config = parse_cli()
    try:
        if config.test_mode:
            dependencies = test_dependencies(config.package, config.repository)
        else:
            repository = MavenRepository(config.repository)
            dependencies = repository.direct_dependencies(config.package)
    except ValueError as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return DATA_ERROR_EXIT_CODE
    print(f"Прямые зависимости {config.package}:")
    if dependencies:
        for dependency in dependencies:
            print(dependency)
    else:
        print("Прямых зависимостей нет.")
    return SUCCESS_EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
