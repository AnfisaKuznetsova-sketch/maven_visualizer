"""Разбор XML POM, свойств и описаний прямых зависимостей Maven."""

import re
import xml.etree.ElementTree as ET

MAX_PROPERTY_PASSES = 32
PROPERTY_PATTERN = re.compile(r"\$\{([^}]+)\}")
DEPENDENCY_FIELDS = (
    "groupId", "artifactId", "version", "type", "classifier", "scope",
    "optional",
)


def parse_pom(content):
    """Читает XML и убирает пространства имён для поиска элементов."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError as error:
        raise ValueError("POM содержит некорректный XML") from error
    for element in root.iter():
        element.tag = element.tag.rsplit("}", 1)[-1]
    if root.tag != "project":
        raise ValueError("Корневой элемент POM должен называться project")
    return root


def element_text(node, path, default=""):
    """Возвращает текст дочернего элемента или значение по умолчанию."""
    element = node.find(path)
    if element is None or element.text is None:
        return default
    return element.text.strip()


def expand_properties(value, properties):
    """Раскрывает вложенные свойства; сообщает о неизвестных и циклах."""
    seen = set()
    for _ in range(MAX_PROPERTY_PASSES):
        matches = list(PROPERTY_PATTERN.finditer(value))
        if not matches:
            return value
        if value in seen:
            raise ValueError(f"Циклическое свойство POM: {value}")
        seen.add(value)
        for match in matches:
            key = match.group(1)
            if key not in properties:
                raise ValueError(f"Неизвестное свойство POM: {key}")
            value = value.replace(match.group(), properties[key])
    raise ValueError("Слишком глубокая вложенность свойств POM")


def project_properties(root, package, inherited):
    """Объединяет свойства родителя, проекта и алиасы координат."""
    properties = dict(inherited)
    own = root.find("properties")
    if own is not None:
        properties.update({n.tag: (n.text or "").strip() for n in own})
    group_id, artifact_id, version = package.split(":")
    coordinates = dict(groupId=group_id, artifactId=artifact_id,
                       version=version)
    for key, value in coordinates.items():
        for prefix in ("", "project.", "pom."):
            properties[prefix + key] = value
    for key in coordinates:
        value = element_text(root, f"parent/{key}")
        if value:
            properties[f"project.parent.{key}"] = value
            properties[f"parent.{key}"] = value
    return properties


def dependency_fields(node):
    """Читает только поля зависимости, имеющие непустое значение."""
    fields = {key: element_text(node, key) for key in DEPENDENCY_FIELDS}
    return {key: value for key, value in fields.items() if value}


def dependency_key(fields, properties):
    """Создаёт ключ зависимости с учётом типа и classifier."""
    values = [fields.get("groupId", ""), fields.get("artifactId", ""),
              fields.get("type", "jar"), fields.get("classifier", "")]
    result = tuple(expand_properties(value, properties) for value in values)
    group_id, artifact_id, _, _ = result
    if not group_id or not artifact_id:
        raise ValueError("В зависимости POM отсутствует groupId/ artifactId")
    return result


def resolve_dependency(fields, properties, managed):
    """Применяет dependencyManagement и раскрывает свойства полей."""
    key = dependency_key(fields, properties)
    values = dict(managed.get(key, {}))
    values.update(fields)
    result = {key: expand_properties(value, properties)
              for key, value in values.items()}
    if not result.get("version"):
        name = ":".join(key[:2])
        raise ValueError(f"Не удалось определить версию зависимости {name}")
    return result


def dependency_coordinates(fields):
    """Формирует координаты groupId:artifactId:version для вывода."""
    return ":".join(fields[key] for key in ("groupId", "artifactId", "version"))
