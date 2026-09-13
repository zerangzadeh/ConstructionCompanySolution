import ast
import importlib.util
from collections import Counter
from pathlib import Path

from django.apps import apps
from django.test import SimpleTestCase, TestCase

from apps.organizations.models import (
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRole,
)
from apps.organizations.permission_registry import (
    GLOBAL_PERMISSION_MODEL_EXCLUSIONS,
    PERMISSION_MANAGED_APPS,
    PERMISSION_RESOURCES,
    registered_model_labels,
    registered_permission_codes,
)
from apps.organizations.role_defaults import DEFAULT_ROLE_PERMISSIONS


def _permission_members_referenced_by(modules: tuple[str, ...]) -> set[str]:
    referenced: set[str] = set()
    for module_name in modules:
        spec = importlib.util.find_spec(module_name)
        if spec is None or spec.origin is None:
            raise AssertionError(f"Enforcement module does not exist: {module_name}")
        source_path = Path(spec.origin)
        tree = ast.parse(
            source_path.read_text(encoding="utf-8"), filename=str(source_path)
        )
        referenced.update(
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "BusinessPermissionCode"
        )
    return referenced


class PermissionRegistryArchitectureTests(SimpleTestCase):
    def test_every_permission_code_is_registered_exactly_once(self) -> None:
        registered = [
            permission.value
            for resource in PERMISSION_RESOURCES
            for permission in resource.permissions
        ]
        duplicates = sorted(
            code for code, count in Counter(registered).items() if count > 1
        )

        self.assertEqual(duplicates, [])
        self.assertEqual(set(registered), set(BusinessPermissionCode.values))

    def test_resource_keys_are_unique_and_match_permission_namespaces(self) -> None:
        keys = [resource.key for resource in PERMISSION_RESOURCES]
        duplicate_keys = sorted(
            key for key, count in Counter(keys).items() if count > 1
        )
        namespace_mismatches = sorted(
            permission.value
            for resource in PERMISSION_RESOURCES
            for permission in resource.permissions
            if permission.value.partition(".")[0] != resource.key
        )

        self.assertEqual(duplicate_keys, [])
        self.assertEqual(namespace_mismatches, [])

    def test_every_managed_business_model_is_registered_exactly_once(self) -> None:
        registered = [
            model_label
            for resource in PERMISSION_RESOURCES
            for model_label in resource.model_labels
        ]
        duplicates = sorted(
            label for label, count in Counter(registered).items() if count > 1
        )
        managed_models = {
            model._meta.label
            for model in apps.get_models()
            if model._meta.app_label in PERMISSION_MANAGED_APPS
        } - GLOBAL_PERMISSION_MODEL_EXCLUSIONS

        self.assertEqual(duplicates, [])
        self.assertEqual(set(registered), managed_models)

    def test_every_registered_permission_is_referenced_by_its_enforcement_module(
        self,
    ) -> None:
        missing: dict[str, list[str]] = {}
        for resource in PERMISSION_RESOURCES:
            referenced = _permission_members_referenced_by(resource.enforcement_modules)
            absent = sorted(
                permission.name
                for permission in resource.permissions
                if permission.name not in referenced
            )
            if absent:
                missing[resource.key] = absent

        self.assertEqual(missing, {})

    def test_role_defaults_only_use_registered_permissions(self) -> None:
        catalog = registered_permission_codes()

        self.assertEqual(set(DEFAULT_ROLE_PERMISSIONS), set(MembershipRole.values))
        for role_code, permissions in DEFAULT_ROLE_PERMISSIONS.items():
            with self.subTest(role=role_code):
                self.assertLessEqual(permissions, catalog)

    def test_global_catalog_models_are_explicitly_excluded(self) -> None:
        self.assertEqual(
            GLOBAL_PERMISSION_MODEL_EXCLUSIONS,
            {
                "organizations.BusinessPermission",
                "organizations.OrganizationRole",
            },
        )
        self.assertNotIn("accounts", PERMISSION_MANAGED_APPS)
        self.assertTrue(registered_model_labels())


class PermissionRegistryDatabaseTests(TestCase):
    def test_database_catalog_matches_registry(self) -> None:
        self.assertEqual(
            set(BusinessPermission.objects.values_list("code", flat=True)),
            registered_permission_codes(),
        )
