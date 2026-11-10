"""Тестовый JSON-репозиторий с буквенными именами пакетов."""

import json
import re
from pathlib import Path


def validate_graph(graph):
    """Проверяет имена, списки зависимостей и наличие упомянутых узлов."""
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


def read_graph(filename):
    """Читает и проверяет JSON один раз перед обходом графа."""
    try:
        graph = json.loads(Path(filename).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError("Не удалось прочитать JSON тестового репозитория") \
            from error
    validate_graph(graph)
    return graph


class JsonRepository:
    """Предоставляет прямые зависимости из загруженного JSON-объекта."""

    def __init__(self, filename):
        """Сохраняет проверенный граф для всех последующих запросов."""
        self.graph = read_graph(filename)

    def direct_dependencies(self, package):
        """Возвращает прямых соседей или сообщает об неизвестном пакете."""
        if package not in self.graph:
            raise ValueError(f"Пакет {package} отсутствует в репозитории")
        return list(dict.fromkeys(self.graph[package]))


def test_dependencies(package, filename):
    """Сохраняет интерфейс второго этапа для запроса прямых соседей."""
    return JsonRepository(filename).direct_dependencies(package)
