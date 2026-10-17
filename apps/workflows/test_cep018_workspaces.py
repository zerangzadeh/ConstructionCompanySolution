from datetime import timedelta
from uuid import uuid4

from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    BusinessPermissionCode,
    MembershipScopeGrant,
    MembershipStatus,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.services import (
    create_organization_with_owner,
    set_active_organization,
)
from apps.support.models import SupportCase
from apps.support.services import acknowledge_notification, create_notification
from apps.timekeeping.models import LeaveMissionRequest, OvertimeRequest, RequestKind
from apps.workforce.models import Employee, Position, WorkTeam


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class Cep018WorkspaceTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="cep018-owner")
        self.organization = create_organization_with_owner(
            owner=self.owner, name="CEP018", slug="cep018"
        )
        self.manager = self._member(
            "cep018-manager",
            {
                BusinessPermissionCode.ATTENDANCE_VIEW,
                BusinessPermissionCode.LEAVE_MISSION_REVIEW,
                BusinessPermissionCode.OVERTIME_REVIEW,
            },
        )
        self.requester = self._member(
            "cep018-requester",
            {
                BusinessPermissionCode.ATTENDANCE_VIEW,
                BusinessPermissionCode.LEAVE_MISSION_REQUEST,
                BusinessPermissionCode.OVERTIME_REQUEST,
            },
        )
        self.other = self._member(
            "cep018-other",
            {
                BusinessPermissionCode.ATTENDANCE_VIEW,
                BusinessPermissionCode.LEAVE_MISSION_REQUEST,
            },
        )
        self.title_only = self._member(
            "cep018-title-only",
            {
                BusinessPermissionCode.ATTENDANCE_VIEW,
                BusinessPermissionCode.LEAVE_MISSION_REVIEW,
            },
        )
        self.manager_employee = Employee.objects.create(
            organization=self.organization,
            user=self.manager,
            employee_number="C18-MGR",
            first_name="مدیر",
            last_name="صریح",
        )
        self.team = WorkTeam.objects.create(
            organization=self.organization,
            code="C18-TEAM",
            name="تیم صریح",
            lead=self.manager_employee,
        )
        self.requester_employee = Employee.objects.create(
            organization=self.organization,
            user=self.requester,
            employee_number="C18-REQ",
            first_name="عضو",
            last_name="تیم",
            work_team=self.team,
        )
        other_team = WorkTeam.objects.create(
            organization=self.organization,
            code="C18-OTHER",
            name="تیم دیگر",
        )
        self.other_employee = Employee.objects.create(
            organization=self.organization,
            user=self.other,
            employee_number="C18-OTHER",
            first_name="خارج",
            last_name="تیم",
            work_team=other_team,
        )
        manager_position = Position.objects.create(
            organization=self.organization,
            code="MANAGER-TITLE",
            title="مدیر",
        )
        Employee.objects.create(
            organization=self.organization,
            user=self.title_only,
            employee_number="C18-TITLE",
            first_name="عنوان",
            last_name="مدیر",
            position=manager_position,
        )
        start = timezone.now() + timedelta(days=1)
        self.own_leave = LeaveMissionRequest.objects.create(
            organization=self.organization,
            employee=self.requester_employee,
            kind=RequestKind.LEAVE,
            category_code="ANNUAL",
            starts_at=start,
            ends_at=start + timedelta(hours=8),
            reason="درخواست خودم",
            requested_by=self.requester,
        )
        self.team_overtime = OvertimeRequest.objects.create(
            organization=self.organization,
            employee=self.requester_employee,
            starts_at=start + timedelta(days=1),
            ends_at=start + timedelta(days=1, hours=2),
            reason="اضافه‌کاری تیم",
            requested_by=self.requester,
            state="submitted",
        )
        self.other_leave = LeaveMissionRequest.objects.create(
            organization=self.organization,
            employee=self.other_employee,
            kind=RequestKind.MISSION,
            category_code="FIELD",
            starts_at=start + timedelta(days=2),
            ends_at=start + timedelta(days=2, hours=4),
            reason="درخواست تیم دیگر",
            requested_by=self.other,
        )

    def _member(self, username: str, permissions: set[str]) -> User:
        user = User.objects.create_user(username=username)
        role = OrganizationRole.objects.create(
            organization=self.organization,
            code=username,
            name=username,
            created_by=self.owner,
        )
        role.permissions.add(*BusinessPermission.objects.filter(code__in=permissions))
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=user,
            role_definition=role,
            status=MembershipStatus.ACTIVE,
            joined_at=timezone.now(),
            assigned_by=self.owner,
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="CEP-018 organization-scoped fixture",
        )
        return user

    def _login(self, user: User) -> None:
        self.client.force_login(user)
        set_active_organization(self.client.session, self.organization)
        self.client.session.save()

    def test_my_requests_is_own_identity_scoped_and_source_owned(self) -> None:
        self._login(self.requester)

        response = self.client.get(reverse("workflows:my_requests"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "درخواست‌های من")
        self.assertContains(response, str(self.own_leave.pk))
        self.assertContains(response, str(self.team_overtime.pk))
        self.assertNotContains(response, str(self.other_leave.pk))
        self.assertContains(response, "وضعیت منبع")
        self.assertNotContains(response, "reviewed_by")
        navigation = response.content.decode()
        self.assertIn('data-nav-id="NAV-004"', navigation)
        self.assertIn(reverse("workflows:my_requests"), navigation)

    def test_manager_workspace_requires_explicit_team_lead_and_filters_team(
        self,
    ) -> None:
        self._login(self.manager)

        response = self.client.get(reverse("workflows:manager_workspace"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "فضای مدیر")
        self.assertContains(response, "عضو تیم")
        self.assertContains(response, str(self.own_leave.pk))
        self.assertContains(response, str(self.team_overtime.pk))
        self.assertNotContains(response, str(self.other_leave.pk))
        self.assertContains(response, reverse("timekeeping:workbench"))

        self._login(self.title_only)
        denied = self.client.get(reverse("workflows:manager_workspace"))
        self.assertEqual(denied.status_code, 403)

    def test_missing_workforce_identity_fails_closed(self) -> None:
        no_identity = self._member(
            "cep018-no-identity", {BusinessPermissionCode.LEAVE_MISSION_REQUEST}
        )
        self._login(no_identity)

        response = self.client.get(reverse("workflows:my_requests"))

        self.assertEqual(response.status_code, 403)

    def test_missing_authorization_scope_fails_closed(self) -> None:
        no_scope = self._member(
            "cep018-no-scope", {BusinessPermissionCode.LEAVE_MISSION_REQUEST}
        )
        Employee.objects.create(
            organization=self.organization,
            user=no_scope,
            employee_number="C18-NO-SCOPE",
            first_name="بدون",
            last_name="دامنه",
        )
        self.organization.memberships.get(user=no_scope).scope_grants.all().delete()
        self._login(no_scope)

        response = self.client.get(reverse("workflows:my_requests"))

        self.assertEqual(response.status_code, 403)

    def test_workspaces_are_get_only_and_rtl(self) -> None:
        self._login(self.requester)
        response = self.client.get(reverse("workflows:my_requests"))
        self.assertContains(response, 'dir="rtl"')
        self.assertEqual(
            self.client.post(reverse("workflows:my_requests")).status_code, 405
        )

        self._login(self.manager)
        response = self.client.get(reverse("workflows:manager_workspace"))
        self.assertContains(response, 'dir="rtl"')
        self.assertEqual(
            self.client.post(reverse("workflows:manager_workspace")).status_code,
            405,
        )

    def test_notification_is_deduplicated_linked_and_presentation_only(self) -> None:
        permission_codes = {
            BusinessPermissionCode.SUPPORT_NOTIFICATIONS_VIEW,
            BusinessPermissionCode.SUPPORT_NOTIFICATIONS_ACKNOWLEDGE,
            BusinessPermissionCode.SUPPORT_CASE_VIEW,
        }
        for code in permission_codes:
            BusinessPermission.objects.update_or_create(
                code=code,
                defaults={
                    "name": str(code),
                    "description": str(code),
                    "is_active": True,
                },
            )
        requester_role = self.organization.memberships.get(
            user=self.requester
        ).role_definition
        requester_role.permissions.add(
            *BusinessPermission.objects.filter(code__in=permission_codes)
        )
        case = SupportCase.objects.create(
            organization=self.organization,
            requester=self.requester,
            category="general",
            summary="منبع اعلان",
        )
        with self.assertRaises(PermissionDenied):
            create_notification(
                organization=self.organization,
                actor=self.requester,
                recipient=self.requester,
                source_type="support_case",
                source_id=uuid4(),
                source_version="1",
                category="case_update",
                summary="منبع نامعتبر",
            )
        notification = create_notification(
            organization=self.organization,
            actor=self.requester,
            recipient=self.requester,
            source_type="support_case",
            source_id=case.pk,
            source_version="1",
            category="case_update",
            summary="وضعیت درخواست تغییر کرد",
            operation_key=uuid4(),
        )
        duplicate = create_notification(
            organization=self.organization,
            actor=self.requester,
            recipient=self.requester,
            source_type="support_case",
            source_id=case.pk,
            source_version="1",
            category="case_update",
            summary="وضعیت درخواست تغییر کرد",
            operation_key=uuid4(),
        )
        self.assertEqual(notification.pk, duplicate.pk)
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=self.organization,
                actor=self.requester,
                action=AuditAction.SUPPORT_NOTIFICATION_CREATED,
                entity_id=str(notification.pk),
            ).exists()
        )
        self._login(self.requester)

        response = self.client.get(reverse("support:notifications"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("support:case_detail", args=[case.pk]))
        acknowledge_notification(
            organization=self.organization,
            actor=self.requester,
            notification_id=notification.pk,
        )
        case.refresh_from_db()
        notification.refresh_from_db()
        self.assertEqual(case.status, "open")
        self.assertIsNotNone(notification.read_at)
