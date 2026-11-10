"""Построение графа зависимостей обходом DFS без рекурсии."""

from dataclasses import dataclass, field


@dataclass
class DependencyGraph:
    """Список смежности в порядке DFS и найденные циклические пути."""

    adjacency: dict = field(default_factory=dict)
    cycles: list = field(default_factory=list)


def filtered_dependencies(package, load_dependencies, excluded):
    """Удаляет дубли и исключённые имена до помещения узлов в стек."""
    dependencies = load_dependencies(package)
    return list(dict.fromkeys(
        name for name in dependencies if not excluded or excluded not in name
    ))


def build_graph(package, load_dependencies, excluded=""):
    """Обходит каждый доступный узел один раз явным стеком входов/выходов."""
    result = DependencyGraph()
    if excluded and excluded in package:
        return result
    stack = [(package, False)]
    visited, active = set(), set()
    path = []
    while stack:
        node, exiting = stack.pop()
        if exiting:
            active.remove(node)
            path.pop()
            continue
        if node in active:
            result.cycles.append(path[path.index(node):] + [node])
            continue
        if node in visited:
            continue
        visited.add(node)
        active.add(node)
        path.append(node)
        dependencies = filtered_dependencies(node, load_dependencies, excluded)
        result.adjacency[node] = dependencies
        stack.append((node, True))
        for dependency in reversed(dependencies):
            stack.append((dependency, False))
    return result


def print_graph(package, result):
    """Печатает список смежности, порядок DFS и циклы без ASCII-дерева."""
    print(f"Граф зависимостей {package}:")
    if not result.adjacency:
        print("Начальный пакет исключён фильтром.")
        return
    for node, dependencies in result.adjacency.items():
        targets = ", ".join(dependencies) or "(нет зависимостей)"
        print(f"{node} -> {targets}")
    print("Порядок DFS: " + " -> ".join(result.adjacency))
    if result.cycles:
        print("Обнаружены циклы:")
        for cycle in result.cycles:
            print(" -> ".join(cycle))
    else:
        print("Циклов нет.")
