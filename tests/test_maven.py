"""Проверки XML, наследования и загрузки Maven без внешней сети."""

import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from maven import MavenRepository, build_pom_url, load_pom
from pom import expand_properties, parse_pom


def pom(body, namespace=True):
    """Оборачивает фрагмент в POM для изолированного теста."""
    attribute = ' xmlns="http://maven.apache.org/POM/4.0.0"'
    if not namespace:
        attribute = ""
    return f"<project{attribute}>{body}</project>".encode()


def dependency(artifact="lib", version="2", extra=""):
    """Создаёт тестовую зависимость с необязательной версией."""
    release = f"<version>{version}</version>" if version else ""
    return (
        f"<dependency><groupId>g</groupId><artifactId>{artifact}</artifactId>"
        f"{release}{extra}</dependency>"
    )


def management(body):
    """Создаёт секцию управления версиями."""
    return f"<dependencyManagement><dependencies>{body}</dependencies>" \
        "</dependencyManagement>"


def parent(artifact="parent"):
    """Создаёт ссылку на родительскую модель."""
    return f"<parent><groupId>g</groupId><artifactId>{artifact}</artifactId>" \
        "<version>1</version></parent>"


class TestPom(unittest.TestCase):
    """Проверяет свойства и зависимости, не загружая чужие пакеты."""

    def resolve(self, content, extra=None):
        """Подставляет тестовые POM вместо сетевой загрузки."""
        models = {"g:app:1": content, **(extra or {})}
        with patch("maven.load_pom", side_effect=lambda p, r: models[p]):
            return MavenRepository("https://example.org/") \
                .direct_dependencies("g:app:1")

    def test_namespace_and_all_scopes(self):
        """Учитывает прямые compile, test и optional-зависимости."""
        body = dependency() + dependency("tests", extra="<scope>test</scope>")
        body += dependency("option", extra="<optional>true</optional>")
        expected = ["g:lib:2", "g:tests:2", "g:option:2"]
        for namespace in (True, False):
            with self.subTest(namespace=namespace):
                content = pom(f"<dependencies>{body}</dependencies>", namespace)
                self.assertEqual(self.resolve(content), expected)

    def test_empty(self):
        """POM без зависимостей даёт пустой список."""
        self.assertEqual(self.resolve(pom("")), [])

    def test_management_and_plugins_are_not_dependencies(self):
        """Не принимает управление версиями и плагины за зависимости."""
        body = management(dependency())
        body += f"<build><plugins><plugin><dependencies>{dependency()}" \
            "</dependencies></plugin></plugins></build>"
        self.assertEqual(self.resolve(pom(body)), [])

    def test_nested_properties(self):
        """Раскрывает вложенные свойства версий."""
        body = "<properties><release>2</release><v>${release}</v></properties>"
        body += f"<dependencies>{dependency(version='${v}')}</dependencies>"
        self.assertEqual(self.resolve(pom(body)), ["g:lib:2"])

    def test_project_aliases(self):
        """Разрешает ссылку на версию текущего проекта."""
        body = f"<dependencies>{dependency(version='${project.version}')}" \
            "</dependencies>"
        self.assertEqual(self.resolve(pom(body)), ["g:lib:1"])

    def test_managed_version(self):
        """Берёт отсутствующую версию из dependencyManagement."""
        body = management(dependency())
        body += f"<dependencies>{dependency(version='')}</dependencies>"
        self.assertEqual(self.resolve(pom(body)), ["g:lib:2"])

    def test_explicit_version_overrides_management(self):
        """Явная версия прямой зависимости имеет приоритет."""
        body = management(dependency())
        body += f"<dependencies>{dependency(version='3')}</dependencies>"
        self.assertEqual(self.resolve(pom(body)), ["g:lib:3"])

    def test_parent_dependencies_and_child_properties(self):
        """Наследует зависимости и раскрывает свойства в контексте потомка."""
        inherited = "<properties><v>2</v></properties>"
        inherited += f"<dependencies>{dependency(version='${v}')}" \
            "</dependencies>"
        own = parent() + "<properties><v>3</v></properties>"
        self.assertEqual(self.resolve(pom(own), {
            "g:parent:1": pom(inherited),
        }), ["g:lib:3"])

    def test_parent_managed_version(self):
        """Наследует управление версиями из родительского POM."""
        own = parent() + f"<dependencies>{dependency(version='')}" \
            "</dependencies>"
        self.assertEqual(self.resolve(pom(own), {
            "g:parent:1": pom(management(dependency())),
        }), ["g:lib:2"])

    def test_child_management_overrides_parent(self):
        """Локальная управляемая версия перекрывает родительскую."""
        own = parent() + management(dependency(version="3"))
        own += f"<dependencies>{dependency(version='')}</dependencies>"
        self.assertEqual(self.resolve(pom(own), {
            "g:parent:1": pom(management(dependency())),
        }), ["g:lib:3"])

    def test_import_bom(self):
        """BOM поставляет версии, но её собственные зависимости не выводятся."""
        extra = "<type>pom</type><scope>import</scope>"
        imported = dependency("bom", "1", extra)
        own = management(imported)
        own += f"<dependencies>{dependency(version='')}</dependencies>"
        bom = management(dependency())
        bom += f"<dependencies>{dependency('not-direct')}</dependencies>"
        self.assertEqual(self.resolve(pom(own), {"g:bom:1": pom(bom)}),
                         ["g:lib:2"])

    def test_bom_uses_its_own_properties(self):
        """Свойства BOM раскрываются в её собственном контексте."""
        extra = "<type>pom</type><scope>import</scope>"
        imported = dependency("bom", "1", extra)
        own = "<properties><v>3</v></properties>" + management(imported)
        own += f"<dependencies>{dependency(version='')}</dependencies>"
        bom = "<properties><v>2</v></properties>"
        bom += management(dependency(version="${v}"))
        self.assertEqual(self.resolve(pom(own), {"g:bom:1": pom(bom)}),
                         ["g:lib:2"])

    def test_no_transitive_download(self):
        """Загружает только POM проекта, а не его зависимостей."""
        content = pom(f"<dependencies>{dependency()}</dependencies>")
        with patch("maven.load_pom", return_value=content) as loader:
            repository = MavenRepository("https://example.org/")
            self.assertEqual(repository.direct_dependencies("g:app:1"),
                             ["g:lib:2"])
            repository.direct_dependencies("g:app:1")
            loader.assert_called_once_with("g:app:1", "https://example.org/")

    def test_missing_version(self):
        """Отсутствие версии даёт понятную ошибку."""
        content = pom(f"<dependencies>{dependency(version='')}</dependencies>")
        with self.assertRaisesRegex(ValueError, "версию"):
            self.resolve(content)

    def test_parent_cycle(self):
        """Циклические родители не приводят к бесконечной загрузке."""
        with self.assertRaisesRegex(ValueError, "Цикл"):
            self.resolve(pom(parent("app")))

    def test_unknown_property(self):
        """Неизвестное свойство не маскируется под номер версии."""
        with self.assertRaisesRegex(ValueError, "Неизвестное свойство"):
            expand_properties("${missing}", {})

    def test_property_cycle(self):
        """Цикл свойств прерывается с ошибкой."""
        with self.assertRaisesRegex(ValueError, "Циклическое"):
            expand_properties("${a}", {"a": "${b}", "b": "${a}"})

    def test_invalid_xml(self):
        """Повреждённый XML и HTML-страница не считаются POM."""
        for content in (b"<broken", b"<html/>"):
            with self.subTest(content=content):
                with self.assertRaises(ValueError):
                    parse_pom(content)


class TestDownload(unittest.TestCase):
    """Проверяет адреса файлов и ошибки HTTP без внешней сети."""

    def test_url(self):
        """Адрес соответствует структуре репозитория Maven."""
        expected = "https://example.org/repo/org/example/demo/1.0/demo-1.0.pom"
        self.assertEqual(build_pom_url("org.example:demo:1.0",
                                      "https://example.org/repo/"), expected)

    def test_bad_coordinates(self):
        """Неверные координаты отклоняются до сетевого запроса."""
        with self.assertRaises(ValueError):
            build_pom_url("bad", "https://example.org/")

    def test_download(self):
        """Содержимое ответа возвращается без изменений."""
        with patch("maven.urlopen", return_value=io.BytesIO(b"<project/>")):
            self.assertEqual(load_pom("g:app:1", "https://example.org/"),
                             b"<project/>")

    def test_http_and_connection_errors(self):
        """HTTP, DNS и тайм-аут преобразуются в ошибки данных."""
        errors = [HTTPError("https://example.org", 404, "missing", {}, None),
                  URLError("no connection"), TimeoutError("timeout")]
        for error in errors:
            with self.subTest(error=error):
                with patch("maven.urlopen", side_effect=error):
                    with self.assertRaises(ValueError):
                        load_pom("g:app:1", "https://example.org/")


if __name__ == "__main__":
    unittest.main()
