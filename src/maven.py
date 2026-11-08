"""Загрузка POM и получение прямых зависимостей без менеджера Maven."""

from dataclasses import dataclass, field
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from config import validate_package, validate_url
from pom import (
    dependency_coordinates, dependency_fields, dependency_key,
    expand_properties, parse_pom, project_properties, resolve_dependency,
)

REQUEST_TIMEOUT = 15
MAX_MODEL_DEPTH = 32


def build_pom_url(package, repository):
    """Строит адрес POM-файла по координатам пакета."""
    validate_package(package, False)
    validate_url(repository)
    group_id, artifact_id, version = package.split(":")
    group_path = "/".join(
        quote(part, safe="") for part in group_id.split(".")
    )
    artifact = quote(artifact_id, safe="")
    release = quote(version, safe="")
    filename = f"{artifact}-{release}.pom"
    path = f"{group_path}/{artifact}/{release}/{filename}"
    return f"{repository.rstrip('/')}/{path}"


def load_pom(package, repository):
    """Загружает POM-файл и возвращает его содержимое в байтах."""
    url = build_pom_url(package, repository)
    request = Request(url, headers={"User-Agent": "MavenVisualizer/0.2"})
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            return response.read()
    except HTTPError as error:
        raise ValueError(
            f"Не удалось загрузить POM {package}: HTTP {error.code}"
        ) from error
    except (URLError, OSError) as error:
        raise ValueError(
            f"Ошибка соединения при загрузке POM {package}: {error}"
        ) from error


@dataclass
class PomModel:
    """Свойства, управляемые версии и объявления зависимостей POM."""

    properties: dict = field(default_factory=dict)
    managed: dict = field(default_factory=dict)
    dependencies: dict = field(default_factory=dict)


class MavenRepository:
    """Читает POM, родителей и BOM; не обходит зависимости пакетов."""

    def __init__(self, repository):
        """Запоминает адрес репозитория и создаёт кеш моделей."""
        self.repository = repository
        self.cache = {}
        self.active = set()

    def model(self, package):
        """Собирает модель POM с защитой от циклов родителей и BOM."""
        if package in self.cache:
            return self.cache[package]
        if package in self.active:
            raise ValueError(f"Цикл родительских POM или BOM: {package}")
        if len(self.active) >= MAX_MODEL_DEPTH:
            raise ValueError("Слишком глубокая цепочка родителей или BOM")
        self.active.add(package)
        try:
            root = parse_pom(load_pom(package, self.repository))
            parent = self.parent_model(root, package)
            properties = project_properties(root, package, parent.properties)
            managed = self.management(root, properties, parent.managed)
            dependencies = dict(parent.dependencies)
            for node in root.findall("dependencies/dependency"):
                fields = dependency_fields(node)
                key = dependency_key(fields, properties)
                merged = dict(dependencies.get(key, {}))
                merged.update(fields)
                dependencies[key] = merged
            result = PomModel(properties, managed, dependencies)
            self.cache[package] = result
            return result
        finally:
            self.active.remove(package)

    def parent_model(self, root, package):
        """Загружает родительский POM из того же репозитория."""
        node = root.find("parent")
        if node is None:
            return PomModel()
        properties = project_properties(root, package, {})
        fields = resolve_dependency(dependency_fields(node), properties, {})
        return self.model(dependency_coordinates(fields))

    def management(self, root, properties, inherited):
        """Объединяет BOM, наследуемые и локальные управляемые версии."""
        imported = {}
        local = {}
        path = "dependencyManagement/dependencies/dependency"
        for node in root.findall(path):
            fields = dependency_fields(node)
            key = dependency_key(fields, properties)
            scope = expand_properties(fields.get("scope", ""), properties)
            if scope == "import":
                self.import_bom(fields, properties, inherited, imported)
            else:
                merged = dict(inherited.get(key, {}))
                merged.update(fields)
                local[key] = merged
        result = dict(imported)
        result.update(inherited)
        result.update(local)
        return result

    def import_bom(self, fields, properties, inherited, imported):
        """Импортирует только управляемые зависимости, а не зависимости BOM."""
        resolved = resolve_dependency(fields, properties, inherited)
        if resolved.get("type") != "pom":
            raise ValueError("Для импорта BOM требуется type=pom")
        bom = self.model(dependency_coordinates(resolved))
        for key, values in bom.managed.items():
            resolved = resolve_dependency(values, bom.properties, {})
            imported.setdefault(key, resolved)

    def direct_dependencies(self, package):
        """Возвращает прямые зависимости проекта с учётом родителя."""
        model = self.model(package)
        result = []
        for fields in model.dependencies.values():
            resolved = resolve_dependency(
                fields, model.properties, model.managed,
            )
            result.append(dependency_coordinates(resolved))
        return list(dict.fromkeys(result))
