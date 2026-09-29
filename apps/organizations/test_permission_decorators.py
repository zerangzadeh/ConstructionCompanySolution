from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode


class OrganizationPermissionDecoratorTests(SimpleTestCase):
    def setUp(self) -> None:
        self.request = RequestFactory().get("/")
        self.request.user = SimpleNamespace(is_authenticated=True)
        self.request.organization = object()

    @patch("apps.organizations.decorators.has_business_permission", return_value=False)
    def test_denies_request_when_active_role_lacks_permission(
        self, has_permission
    ) -> None:
        view = active_organization_required(
            organization_permission_required(BusinessPermissionCode.PROJECTS_VIEW)(
                lambda request: HttpResponse("ok")
            )
        )

        with self.assertRaisesMessage(PermissionDenied, "اجازه انجام این عملیات"):
            view(self.request)

        has_permission.assert_called_once_with(
            user=self.request.user,
            organization=self.request.organization,
            permission=BusinessPermissionCode.PROJECTS_VIEW,
            allow_any_scope=True,
        )

    @patch("apps.organizations.decorators.has_business_permission", return_value=True)
    def test_allows_request_when_active_role_has_permission(
        self, has_permission
    ) -> None:
        view = active_organization_required(
            organization_permission_required(BusinessPermissionCode.PROJECTS_VIEW)(
                lambda request: HttpResponse("ok")
            )
        )

        response = view(self.request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
        has_permission.assert_called_once()
