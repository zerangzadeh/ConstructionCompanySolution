import os
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.organizations.models import OrganizationMembership
from apps.timekeeping.models import LeaveMissionRequest
from apps.workflows import test_cep018_workspaces as baseline
from apps.workforce.ess_dashboard import build_ess_dashboard
from apps.workforce.person_services import create_person, create_work_relationship


class ESSDashboardTests(baseline.Cep018WorkspaceTests):
    # Inherited tests retain six source-workspace authorization/workflow cases.
    def setUp(self):
        super().setUp()
        person = create_person(
            organization=self.organization,
            actor=self.owner,
            first_name="کارمند",
            last_name="نمونه",
            user=self.requester,
        )
        self.relationship = create_work_relationship(
            organization=self.organization,
            actor=self.owner,
            person=person,
            employee_number=self.requester_employee.employee_number,
            effective_start=timezone.localdate() - timedelta(days=30),
            legacy_employee=self.requester_employee,
        )

    def _capture(self, name, response):
        # Opt-in evidence from synthetic fixtures, never a live tenant session.
        directory = os.environ.get("BONIRA_CEP053_CAPTURE_DIR")
        if directory:
            Path(directory, name + ".html").write_bytes(response.content)

    def test_dashboard_retains_own_raw_source_status_and_links(self):
        self._login(self.requester)
        response = self.client.get(reverse("workforce:ess_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "داشبورد خدمات من")
        self.assertContains(response, str(self.own_leave.pk))
        self.assertContains(response, str(self.team_overtime.pk))
        self.assertContains(response, self.own_leave.state)
        self.assertNotContains(response, str(self.other_leave.pk))
        self.assertContains(response, reverse("workforce:ess_profile"))
        self.assertContains(response, 'dir="rtl"')
        self.assertContains(response, "وضعیت منبع")
        self.assertNotContains(response, 'name="first_name"')
        dashboard = response.context["dashboard"]
        self.assertTrue(all(row.source_url for row in dashboard.requests))
        for row in dashboard.requests:
            self.assertEqual(self.client.get(row.source_url).status_code, 200)
        self._capture("ready", response)

    def test_authorized_empty_source_has_no_fabricated_balance_or_score(self):
        LeaveMissionRequest.objects.filter(pk=self.own_leave.pk).delete()
        self.team_overtime.delete()
        self._login(self.requester)
        response = self.client.get(reverse("workforce:ess_dashboard"))
        self.assertContains(response, "درخواست مجازی برای نمایش ثبت نشده است.")
        self.assertEqual(response.context["dashboard"].requests_state, "empty")
        self.assertNotContains(response, "مانده مرخصی: ۰")
        self.assertNotContains(response, "امتیاز")
        self._capture("empty", response)

    def test_independent_profile_survives_source_error(self):
        self._login(self.requester)
        with patch(
            "apps.workforce.ess_dashboard.build_my_requests",
            side_effect=ValidationError("Sensitive internal detail"),
        ):
            response = self.client.get(reverse("workforce:ess_dashboard"))
        self.assertContains(response, "دریافت وضعیت درخواست‌ها ممکن نشد.")
        self.assertContains(response, self.relationship.employee_number)
        self.assertNotContains(response, "Sensitive internal detail")
        self.assertEqual(response.context["dashboard"].requests, ())
        self._capture("error", response)

    def test_no_identity_or_foreign_tenant_never_reveals_source_existence(self):
        self._login(self.other)
        response = self.client.get(reverse("workforce:ess_dashboard"))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "خدمات من در دسترس نیست", status_code=403)
        self.assertNotContains(response, str(self.own_leave.pk), status_code=403)
        self._capture("unauthorized", response)
        self._login(self.requester)
        session = self.client.session
        session["active_organization_id"] = "00000000-0000-0000-0000-000000000001"
        session.save()
        response = self.client.get(reverse("workforce:ess_dashboard"))
        self.assertNotEqual(response.status_code, 200)
        self.assertNotIn(str(self.own_leave.pk).encode(), response.content)

    def test_missing_source_permission_is_unavailable_without_requests(self):
        membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.requester
        )
        membership.role_definition.permissions.clear()
        self._login(self.requester)
        response = self.client.get(reverse("workforce:ess_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["dashboard"].requests_state, "unavailable")
        self.assertNotContains(response, str(self.own_leave.pk))

    def test_only_read_methods_and_authoritative_profile_remains_unchanged(self):
        self._login(self.requester)
        url = reverse("workforce:ess_dashboard")
        response = self.client.post(url, {"first_name": "Changed"})
        self.assertEqual(response.status_code, 405)
        profile = self.client.get(reverse("workforce:ess_profile"))
        self.assertContains(profile, "داشبورد من")
        self.assertContains(profile, "کارمند")
        self.assertNotContains(profile, 'name="first_name"')

    def test_current_person_relationship_bridge_filters_legacy_source_rows(self):
        # A source adapter returning another explicit legacy identity must still
        # pass the stricter ESS Person/WorkRelationship boundary.
        data = build_ess_dashboard(user=self.requester, organization=self.organization)
        foreign = LeaveMissionRequest.objects.get(pk=self.other_leave.pk)
        row = data.requests[0]
        from dataclasses import replace

        forged = replace(row, source_type="leave", source_id=foreign.pk)
        with patch(
            "apps.workforce.ess_dashboard.build_my_requests", return_value=(forged,)
        ):
            result = build_ess_dashboard(
                user=self.requester, organization=self.organization
            )
        self.assertEqual(result.requests, ())
        self.assertEqual(result.requests_state, "empty")
