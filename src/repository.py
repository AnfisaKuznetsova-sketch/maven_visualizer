"""Чтение прямых зависимостей из локального тестового JSON-репозитория."""

import json
import re
from pathlib import Path


def validate_graph(graph):
    """Проверяет имена узлов, списки зависимостей и наличие всех узлов."""
    if not isinstance(graph, dict):
        raise ValueError("Тестовый репозиторий должен быть JSON-объектом")
    for name, dependencies in graph.items():
        if not re.fullmatch(r"[A-Z]+", name):
            raise ValueError("Имена тестовых пакетов должны содержать A–Z")
        if not isinstance(dependencies, list):
            raise ValueError(f"Зависимости {name} должны быть списком")
        for dependency in dependencies:
            if not isinstance(dependency, str) or dependency not in graph:
                message = f"Неизвестная зависимость {name}: {dependency}"
                raise ValueError(message)


def test_dependencies(package, filename):
    """Читает JSON и возвращает только непосредственных соседей пакета."""
    try:
        graph = json.loads(Path(filename).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError("Не удалось прочитать JSON тестового репозитория") \
            from error
    validate_graph(graph)
    if package not in graph:
        raise ValueError(f"Пакет {package} отсутствует в тестовом репозитории")
    return list(dict.fromkeys(graph[package]))
