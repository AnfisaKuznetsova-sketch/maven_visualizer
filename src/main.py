"""Точка входа минимального CLI-прототипа: только вывод конфигурации."""

from config import parse_cli


def main():
    """Выводит все шесть проверенных параметров в формате ключ=значение."""
    config = parse_cli()
    for key, value in vars(config).items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()