"""PD-WC: governed Employment UI, explicit own identity and dependent inputs."""

from uuid import uuid4

from django.core.exceptions import PermissionDenied
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.organizations.models import Organization
from apps.payroll.forms import EmploymentConfigurationForm, RunForm
from apps.projects.models import Project, ProjectSite
from apps.workforce import test_cep022 as employment_fixture
from apps.workforce.employment_services import own_employment_history
from apps.workforce.models import EmploymentRecord


class EmploymentManagementTests(employment_fixture.EmploymentTests):
    def test_authorized_management_creates_immutable_record_and_redisplays_invalid(
        self,
    ):
        self._client(self.owner)
        url = reverse("workforce:employment_manage")
        response = self.client.get(url, {"relationship": self.relationship.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertContains(response, self.document.title)
        data = {
            "relationship": self.relationship.pk,
            "record_key": "ui-contract",
            "kind": "contract",
            "effective_from": "1405/01/01",
            "document_version": self.document.current_version_id,
            "reason": "Synthetic management control",
        }
        # Use a valid effective date in the existing relationship interval.
        from core.jalali import format_jalali

        data["effective_from"] = format_jalali(self.relationship.effective_start)
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        record = EmploymentRecord.objects.get(record_key="ui-contract")
        self.assertEqual(record.actor, self.owner)
        self.assertEqual(self.client.post(url, data).status_code, 400)
        self.assertEqual(
            EmploymentRecord.objects.filter(record_key="ui-contract").count(), 1
        )

    def test_management_permission_and_tenant_and_manipulated_ids_fail_closed(self):
        url = reverse("workforce:employment_manage")
        self._client(self.employee_user)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(
            self.client.post(url, {"relationship": self.relationship.pk}).status_code,
            403,
        )
        self._client(self.owner)
        response = self.client.post(
            url,
            {
                "relationship": str(uuid4()),
                "document_version": str(uuid4()),
                "reason": "invalid",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertNotContains(response, "PRIVATE-SOURCE-REASON", status_code=400)
        self.assertEqual(EmploymentRecord.objects.count(), 0)
        self.assertEqual(
            self.client.get(url, {"relationship": "bad-uuid"}).status_code, 200
        )

    def test_person_link_alone_is_not_employee_own_authority(self):
        employee = self.relationship.legacy_employee
        employee.user = None
        employee.save(update_fields=["user"])
        with self.assertRaises(PermissionDenied):
            own_employment_history(
                actor=self.employee_user, organization=self.organization
            )
        other_employee = self.other_relationship.legacy_employee
        other_employee.user = None
        other_employee.save(update_fields=["user"])
        employee.user = self.other_user
        employee.save(update_fields=["user"])
        with self.assertRaises(PermissionDenied):
            own_employment_history(
                actor=self.employee_user, organization=self.organization
            )


class PayrollSiteChoicesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="Site tests", slug="reentry-sites")
        cls.other = Organization.objects.create(name="Other", slug="reentry-other")
        cls.a = Project.objects.create(organization=cls.org, code="A", name="A")
        cls.b = Project.objects.create(organization=cls.org, code="B", name="B")
        cls.x = Project.objects.create(organization=cls.other, code="X", name="X")
        cls.site = ProjectSite.objects.create(
            organization=cls.org, project=cls.a, code="A", name="A"
        )
        cls.wrong = ProjectSite.objects.create(
            organization=cls.org, project=cls.b, code="B", name="B"
        )

    def test_sites_require_selected_same_tenant_parent_and_reject_manipulation(self):
        form = EmploymentConfigurationForm(organization=self.org)
        self.assertFalse(form.fields["site"].queryset.exists())
        form = EmploymentConfigurationForm(
            {"project": self.a.pk, "site": self.wrong.pk}, organization=self.org
        )
        self.assertQuerySetEqual(
            form.fields["site"].queryset, [self.site], transform=lambda x: x
        )
        self.assertFalse(form.is_valid())
        self.assertIn("site", form.errors)
        form = EmploymentConfigurationForm(
            {"project": self.x.pk}, organization=self.org
        )
        self.assertFalse(form.fields["site"].queryset.exists())

    def test_generated_retry_key_survives_invalid_redisplay(self):
        form = RunForm(organization=self.org)
        key = form.initial["idempotency_key"]
        self.assertTrue(form.fields["idempotency_key"].widget.is_hidden)
        redisplay = RunForm({"idempotency_key": key}, organization=self.org)
        self.assertFalse(redisplay.is_valid())
        self.assertEqual(redisplay["idempotency_key"].value(), key)


class PresentationSafetyTests(SimpleTestCase):
    def test_employee_detail_has_one_main_landmark(self):
        from types import SimpleNamespace

        employee = SimpleNamespace(
            id=uuid4(),
            pk=uuid4(),
            first_name="Synthetic",
            last_name="Employee",
            profile_image=None,
            user=None,
            status="active",
            employee_number="SYN-1",
        )
        html = render_to_string(
            "workforce/employee_detail.html", {"employee": employee}
        )
        self.assertEqual(html.count("<main"), 1)

    def test_timekeeping_separates_daily_work_and_closed_setup(self):
        html = render_to_string(
            "timekeeping/workbench.html",
            {
                "business_permission_codes": [
                    "time_calendars.manage",
                    "attendance.capture",
                ]
            },
        )
        self.assertIn('id="daily-work"', html)
        self.assertIn("<details", html)
        self.assertNotIn("<details open", html)
        self.assertIn("ثبت حضور", html)
