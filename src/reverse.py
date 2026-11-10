"""Поиск обратных зависимостей с помощью DFS из третьего этапа."""

from graph import build_graph


def reverse_adjacency(adjacency, excluded=""):
    """Разворачивает разрешённые рёбра, сохраняя изолированные узлы."""
    incoming = {name: [] for name in adjacency
                if not excluded or excluded not in name}
    for source, dependencies in adjacency.items():
        if source not in incoming:
            continue
        for target in dict.fromkeys(dependencies):
            if target in incoming:
                incoming[target].append(source)
    return incoming


def find_reverse_dependencies(package, adjacency, excluded=""):
    """Находит прямых и транзитивных потребителей итеративным DFS."""
    incoming = reverse_adjacency(adjacency, excluded)
    if excluded and excluded in package:
        return build_graph(package, incoming.__getitem__, excluded)
    if package not in incoming:
        raise ValueError(f"Пакет {package} отсутствует в области анализа")
    return build_graph(package, incoming.__getitem__, excluded)


def print_reverse_dependencies(package, result, scope):
    """Выводит область анализа, прямых потребителей и весь обратный обход."""
    print(f"Обратные зависимости {package}:")
    print(f"Область анализа: {scope}.")
    if not result.adjacency:
        print("Пакет исключён фильтром.")
        return
    direct = [name for name in result.adjacency[package] if name != package]
    all_dependencies = [name for name in result.adjacency if name != package]
    print("Прямые обратные зависимости: " + (", ".join(direct) or "нет"))
    print("Все обратные зависимости (DFS): "
          + (", ".join(all_dependencies) or "нет"))
    print("Порядок DFS: " + " -> ".join(result.adjacency))
    if result.cycles:
        print("Циклы в обратном графе:")
        for cycle in result.cycles:
            print(" -> ".join(cycle))
    else:
        print("Циклов нет.")
