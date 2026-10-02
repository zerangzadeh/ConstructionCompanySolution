from django.test import TestCase

from apps.organizations.models import (
    BusinessPermission,
    BusinessPermissionCode,
    OrganizationRole,
    ProtectedOperation,
    ProtectedOperationCode,
)
from apps.organizations.permission_registry import registered_permission_codes


class P5S09OpeningControlFoundationTests(TestCase):
    def test_dedicated_open_and_confidential_view_permissions_are_catalogued(self):
        expected = {
            BusinessPermissionCode.RFQ_QUOTES_OPEN,
            BusinessPermissionCode.RFQ_QUOTES_APPROVE_OPEN,
            BusinessPermissionCode.RFQ_QUOTES_VIEW_CONFIDENTIAL,
            BusinessPermissionCode.RFQ_QUOTES_MANAGE_CONFIDENTIAL_ACCESS,
        }
        self.assertLessEqual(expected, registered_permission_codes())
        self.assertEqual(
            set(
                BusinessPermission.objects.filter(code__in=expected).values_list(
                    "code", flat=True
                )
            ),
            expected,
        )

    def test_opening_permissions_have_no_default_role_grant(self):
        self.assertFalse(
            OrganizationRole.objects.filter(
                organization__isnull=True,
                permissions__code__in={
                    BusinessPermissionCode.RFQ_QUOTES_OPEN,
                    BusinessPermissionCode.RFQ_QUOTES_APPROVE_OPEN,
                    BusinessPermissionCode.RFQ_QUOTES_VIEW_CONFIDENTIAL,
                    BusinessPermissionCode.RFQ_QUOTES_MANAGE_CONFIDENTIAL_ACCESS,
                },
            ).exists()
        )

    def test_quote_reveal_is_an_active_protected_operation(self):
        self.assertTrue(
            ProtectedOperation.objects.filter(
                code=ProtectedOperationCode.RFQ_QUOTE_REVEAL,
                effective_at__isnull=False,
                retired_at__isnull=True,
            ).exists()
        )
