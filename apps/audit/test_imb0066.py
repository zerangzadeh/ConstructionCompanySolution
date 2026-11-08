"""List filters and pagination operate only on authorized audit events."""

from datetime import UTC, date, datetime
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit import tests as audit_tests
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    BusinessPermissionCode,
    MembershipStatus,
    OrganizationMembership,
    OrganizationRole,
    OrganizationSettings,
)
from core.jalali import format_jalali


class AuditListBoundingTests(TestCase):
    setUp = audit_tests.AuditServiceTests.setUp

    def _activate(self, user=None) -> None:
        self.client.force_login(user or self.user)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()

    def _events(self, count: int, *, action=AuditAction.ORGANIZATION_CREATED):
        timestamp = timezone.now()
        with patch("django.utils.timezone.now", return_value=timestamp):
            return [
                AuditEvent.objects.create(
                    organization=self.organization,
                    actor=self.user,
                    action=action,
                    entity_type="bounded",
                    entity_id=f"source-{i}",
                    created_at=timestamp,
                )
                for i in range(count)
            ]

    def _auditor(self, codes):
        user = User.objects.create_user(username="bounded-auditor")
        role = OrganizationRole.objects.create(
            organization=self.organization,
            code="bounded-auditor",
            name="Bounded auditor",
        )
        role.permissions.add(*BusinessPermission.objects.filter(code__in=codes))
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=user,
            role_definition=role,
            status=MembershipStatus.ACTIVE,
        )
        membership.role_assignments.create(
            organization=self.organization, role=role, reason="Explicit test permission"
        )
        membership.scope_grants.create(
            organization=self.organization,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="Explicit test scope",
        )
        return user, role, membership

    def test_pages_are_bounded_stable_disjoint_and_complete(self) -> None:
        events = self._events(61)
        self._activate()
        expected = [
            event.pk for event in sorted(events, key=lambda e: e.pk, reverse=True)
        ]
        seen = []
        for number, size in ((1, 25), (2, 25), (3, 11)):
            response = self.client.get(
                reverse("audit:log"), {"page": number, "per_page": 100000}
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.context["events"]), size)
            self.assertEqual(response.context["page_obj"].paginator.count, 61)
            seen.extend(e.pk for e in response.context["events"])
            self.assertContains(response, 'aria-label="صفحه‌بندی"')
        self.assertEqual(seen, expected)

    def test_one_bounded_source_read_includes_actor_and_no_writes(self) -> None:
        self._events(61)
        self._activate()
        before = list(AuditEvent.objects.values())
        with CaptureQueriesContext(connection) as captured:
            response = self.client.get(reverse("audit:log"), {"page": 2})
        self.assertEqual(len(response.context["events"]), 25)
        selects = [q["sql"] for q in captured if 'FROM "audit_auditevent"' in q["sql"]]
        self.assertEqual(len(selects), 2)
        self.assertTrue(any("LIMIT 25 OFFSET 25" in sql for sql in selects))
        self.assertTrue(any('JOIN "accounts_user"' in sql for sql in selects))
        self.assertFalse(
            any(
                q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
                for q in captured
            )
        )
        self.assertEqual(before, list(AuditEvent.objects.values()))
        self.assertContains(response, "source-")

    def test_payroll_filters_apply_before_counts_and_page_boundaries(self) -> None:
        self._events(26)
        self._events(30, action=AuditAction.PAYROLL_CONFIGURATION_RECORDED)
        self._events(30, action=AuditAction.PAYROLL_STATUTORY_CALCULATED)
        user, role, _ = self._auditor([BusinessPermissionCode.AUDIT_VIEW])
        for extra, expected_count, hidden in (
            (
                None,
                26,
                {
                    AuditAction.PAYROLL_CONFIGURATION_RECORDED,
                    AuditAction.PAYROLL_STATUTORY_CALCULATED,
                },
            ),
            (
                BusinessPermissionCode.PAYROLL_AUDIT_VIEW,
                56,
                {AuditAction.PAYROLL_STATUTORY_CALCULATED},
            ),
            (
                BusinessPermissionCode.PAYROLL_STATUTORY_AUDIT_VIEW,
                56,
                {AuditAction.PAYROLL_CONFIGURATION_RECORDED},
            ),
        ):
            role.permissions.set(
                BusinessPermission.objects.filter(
                    code__in=[
                        BusinessPermissionCode.AUDIT_VIEW,
                        *([extra] if extra else []),
                    ]
                )
            )
            self._activate(user)
            response = self.client.get(reverse("audit:log"), {"page": 2})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.context["page_obj"].paginator.count, expected_count
            )
            self.assertTrue(
                all(e.action not in hidden for e in response.context["events"])
            )

    def test_cross_tenant_and_platform_events_do_not_affect_count(self) -> None:
        self._events(26)
        for organization in (self.other_organization, None):
            AuditEvent.objects.create(
                organization=organization,
                action=AuditAction.ORGANIZATION_CREATED,
                entity_type="foreign-secret",
            )
        self._activate()
        response = self.client.get(
            reverse("audit:log"),
            {"page": 2, "organization": str(self.other_organization.pk)},
        )
        self.assertEqual(response.context["page_obj"].paginator.count, 26)
        self.assertEqual(len(response.context["events"]), 1)
        self.assertNotContains(response, "foreign-secret")

    def test_invalid_pages_and_empty_results_remain_bounded(self) -> None:
        self._activate()
        response = self.client.get(reverse("audit:log"))
        self.assertEqual(response.context["events"], [])
        self._events(26)
        for value, expected in (("bad", 1), ("0", 2), ("-1", 2), ("999999999999", 2)):
            response = self.client.get(reverse("audit:log"), {"page": value})
            self.assertEqual(response.context["page_obj"].number, expected)
            self.assertLessEqual(len(response.context["events"]), 25)

    def test_combined_filters_use_the_company_date_and_authorized_events(self) -> None:
        OrganizationSettings.objects.update_or_create(
            organization=self.organization, defaults={"timezone": "Asia/Tehran"}
        )
        inside = datetime(2026, 11, 6, 20, 30, tzinfo=UTC)
        outside = datetime(2026, 11, 6, 20, 29, tzinfo=UTC)
        for organization, actor, action, timestamp, reference in (
            (
                self.organization,
                self.user,
                AuditAction.PROJECT_CREATED,
                inside,
                "match",
            ),
            (
                self.organization,
                self.user,
                AuditAction.PROJECT_CREATED,
                outside,
                "earlier",
            ),
            (
                self.organization,
                self.other_user,
                AuditAction.PROJECT_CREATED,
                inside,
                "other-actor",
            ),
            (
                self.other_organization,
                self.user,
                AuditAction.PROJECT_CREATED,
                inside,
                "other-company",
            ),
            (
                self.organization,
                self.user,
                AuditAction.ORGANIZATION_CREATED,
                inside,
                "other-action",
            ),
        ):
            with patch("django.utils.timezone.now", return_value=timestamp):
                AuditEvent.objects.create(
                    organization=organization,
                    actor=actor,
                    action=action,
                    entity_type="projects.Project",
                    entity_id=reference,
                )

        self._activate()
        day = format_jalali(date(2026, 11, 7))
        response = self.client.get(
            reverse("audit:log"),
            {
                "q": AuditAction.PROJECT_CREATED.label,
                "actor": "AUDIT-USER",
                "action": AuditAction.PROJECT_CREATED,
                "date_from": day,
                "date_to": day,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [event.entity_id for event in response.context["events"]], ["match"]
        )
        self.assertContains(response, 'data-filter-chip="date_from"')
        self.assertContains(response, "۰۰:۰۰")

    def test_page_size_sort_and_filters_are_retained_in_navigation(self) -> None:
        events = self._events(22)
        self._activate()
        response = self.client.get(
            reverse("audit:log"),
            {"q": "audit-user", "sort": "date", "per_page": 10, "page": 2},
        )
        page = response.context["page_obj"]
        expected = sorted(event.pk for event in events)
        self.assertEqual([event.pk for event in page.object_list], expected[10:20])
        self.assertEqual(page.paginator.count, 22)
        self.assertContains(
            response, "q=audit-user&amp;sort=date&amp;per_page=10&amp;page=3"
        )
        self.assertContains(response, 'href="/audit/?sort=date&amp;per_page=10"')

    def test_permission_scope_membership_tenant_and_login_fail_closed(self) -> None:
        user, role, membership = self._auditor([])
        self._activate(user)
        self.assertEqual(self.client.get(reverse("audit:log")).status_code, 403)
        role.permissions.add(
            BusinessPermission.objects.get(code=BusinessPermissionCode.AUDIT_VIEW)
        )
        membership.scope_grants.all().delete()
        self.assertEqual(self.client.get(reverse("audit:log")).status_code, 403)
        membership.status = MembershipStatus.REVOKED
        membership.save(update_fields=["status"])
        self.assertEqual(self.client.get(reverse("audit:log")).status_code, 403)
        self._activate()
        self.organization.status = "suspended"
        self.organization.save(update_fields=["status", "updated_at"])
        self.assertEqual(self.client.get(reverse("audit:log")).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("audit:log")).status_code, 302)
