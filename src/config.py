"""Разбор и проверка параметров прототипа визуализатора Maven."""

import argparse
import os
import re
import stat
from pathlib import Path
from urllib.parse import urlsplit


def nonempty(value):
    """Проверяет, что значение не пустое и не окружено пробелами."""
    if not value.strip():
        raise argparse.ArgumentTypeError("значение не должно быть пустым")
    if value != value.strip():
        raise argparse.ArgumentTypeError("уберите пробелы по краям значения")
    return value


def build_parser():
    """Создаёт парсер шести пользовательских параметров."""
    parser = argparse.ArgumentParser(
        description="Визуализатор зависимостей Maven: этап 1",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--package", required=True, type=nonempty,
        help="координаты groupId:artifactId:version; в тестовом режиме A, B…",
    )
    parser.add_argument(
        "--repository", required=True, type=nonempty,
        help="HTTP(S)-адрес репозитория или путь к тестовому файлу",
    )
    parser.add_argument(
        "--test-mode", action="store_true",
        help="использовать локальный тестовый репозиторий",
    )
    parser.add_argument(
        "--output", default="graph.svg", type=nonempty,
        help="путь к будущему SVG-файлу (по умолчанию graph.svg)",
    )
    parser.add_argument(
        "--ascii-tree", action="store_true",
        help="включить вывод зависимостей в виде ASCII-дерева",
    )
    parser.add_argument(
        "--filter", default=None, type=nonempty,
        help="исключать пакеты, содержащие эту подстроку",
    )
    return parser


def validate_package(value, test_mode):
    """Проверяет формат имени пакета для выбранного режима."""
    if test_mode:
        if not re.fullmatch(r"[A-Z]+", value):
            raise ValueError("--package: ожидаются заглавные буквы A–Z")
        return
    part = r"[A-Za-z0-9_][A-Za-z0-9_.+\-]*"
    if not re.fullmatch(rf"{part}:{part}:{part}", value):
        raise ValueError(
            "--package: используйте groupId:artifactId:version, "
            "например org.junit.jupiter:junit-jupiter:5.10.2"
        )


def validate_url(value):
    """Проверяет синтаксис HTTP(S)-адреса без сетевых запросов."""
    message = "--repository: нужен корректный HTTP(S)-адрес репозитория"
    try:
        url = urlsplit(value)
        port = url.port
        valid = url.scheme in ("http", "https") and bool(url.hostname)
    except ValueError as error:
        raise ValueError(message) from error
    if not valid or any(char.isspace() for char in value):
        raise ValueError(message)
    if url.username is not None:
        raise ValueError("--repository: адрес не должен содержать пароль/логин")
    if port == 0 or url.query or url.fragment:
        raise ValueError(message)


def validate_test_file(value):
    """Проверяет наличие и доступность файла тестового репозитория."""
    path = Path(value)
    if not path.is_file():
        raise ValueError("--repository: тестовый файл не найден или это папка")
    try:
        with path.open("rb") as stream:
            stream.read(1)
    except OSError as error:
        raise ValueError("--repository: тестовый файл недоступен для чтения") \
            from error


def validate_output(value):
    """Проверяет путь SVG-файла, не создавая и не изменяя его."""
    path = Path(value)
    if path.suffix.lower() != ".svg":
        raise ValueError("--output: имя файла должно оканчиваться на .svg")
    if re.search(r'[<>:"|?*\x00-\x1f]', path.name):
        raise ValueError("--output: недопустимые символы в имени файла")
    reserved = r"(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])"
    if re.fullmatch(reserved, path.name.split(".")[0]):
        raise ValueError("--output: зарезервированное имя файла Windows")
    if not path.parent.is_dir():
        raise ValueError("--output: папка для результата не существует")
    if path.exists() and not path.is_file():
        raise ValueError("--output: путь указывает не на обычный файл")
    target = path if path.exists() else path.parent
    writable = target.stat().st_mode & stat.S_IWRITE
    if not writable or not os.access(target, os.W_OK):
        raise ValueError("--output: путь недоступен для записи")


def parse_cli(argv=None):
    """Возвращает проверенные параметры; при ошибке завершает с кодом 2."""
    parser = build_parser()
    config = parser.parse_args(argv)
    if config.filter is None:
        config.filter = ""
    try:
        validate_package(config.package, config.test_mode)
        if config.test_mode:
            validate_test_file(config.repository)
        else:
            validate_url(config.repository)
        validate_output(config.output)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    return config