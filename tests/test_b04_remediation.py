"""B04 regressions using migrated tenant grants and real Django boundaries."""

from datetime import UTC, datetime

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.equipment.forms import DowntimeForm, FuelForm, MeterReadingForm, UsageForm
from apps.equipment.models import Equipment
from apps.equipment.p8_models import EquipmentUsageLog
from apps.quality.forms import QualityIssueForm
from apps.safety.forms import SafetyIncidentForm
from tests.test_b02_remediation import B02Fixture


@override_settings(PRODUCT_SURFACE_PROFILE="MVP")
class B04RemediationTests(B02Fixture, TestCase):
    def setUp(self):
        self.make_fixture()
        self.login(self.owner)
        self.equipment = Equipment.objects.create(
            organization=self.organization,
            code="B04-TEST",
            name="تجهیز آزمون",
            category="عملیاتی",
        )

    def test_cost_policy_create_accepts_server_owned_organization(self):
        url = reverse("equipment:cost_policy_create")
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(
            url,
            {
                "code": "B04-POLICY",
                "version": "1",
                "effective_from": "1405/08/01",
                "monetary_policy_code": "synthetic-test",
                "monetary_policy_version": "1",
                "decimal_places": "2",
            },
        )
        self.assertRedirects(response, reverse("equipment:cost_workbench"))

    def test_invalid_usage_displays_domain_error_and_retains_safe_fields(self):
        response = self.client.post(
            reverse("equipment:usage_create"),
            {
                "equipment": self.equipment.pk,
                "started_at": "1405/08/10 12:00",
                "ended_at": "1405/08/10 10:00",
                "runtime_hours": "2.000",
                "source_key": "B04-invalid",
                "evidence_reference": "preserve-this-reference",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())
        self.assertContains(response, "preserve-this-reference")
        self.assertFalse(
            EquipmentUsageLog.objects.filter(source_key="B04-invalid").exists()
        )

    def test_equipment_datetime_families_use_tenant_zone_and_round_trip(self):
        for form_class, field_name in (
            (MeterReadingForm, "observed_at"),
            (UsageForm, "started_at"),
            (UsageForm, "ended_at"),
            (FuelForm, "occurred_at"),
            (DowntimeForm, "started_at"),
        ):
            with self.subTest(form=form_class.__name__, field=field_name):
                form = form_class(organization=self.organization)
                field = form.fields[field_name]
                value = field.clean("2026-11-01 08:15")
                self.assertEqual(
                    value.astimezone(UTC), datetime(2026, 11, 1, 4, 45, tzinfo=UTC)
                )
                self.assertEqual(field.prepare_value(value).hour, 8)

    def test_hse_model_forms_bind_occurrence_time_before_model_validation(self):
        for form_class, field_name in (
            (SafetyIncidentForm, "occurred_at"),
            (QualityIssueForm, "identified_at"),
        ):
            with self.subTest(form=form_class.__name__):
                form = form_class(organization=self.organization)
                value = form.fields[field_name].clean("2026-11-01 09:30")
                self.assertEqual(
                    value.astimezone(UTC), datetime(2026, 11, 1, 6, 0, tzinfo=UTC)
                )

    def test_timezone_missing_fails_closed(self):
        form = UsageForm(organization=None)
        with self.assertRaisesMessage(Exception, "منطقه زمانی"):
            form.fields["started_at"].clean("2026-11-01 08:00")

    def test_expense_coding_choices_show_business_identity(self):
        from apps.expenses.forms import ExpenseAllocationForm
        from apps.expenses.test_p4_s26_s30 import ExpenseControlTests
        from apps.organizations.authorization import get_active_membership

        fixture = ExpenseControlTests()
        fixture.setUp()
        form = ExpenseAllocationForm(
            organization=fixture.organization,
            membership=get_active_membership(
                user=fixture.maker, organization=fixture.organization
            ),
        )
        rendered = str(form["cbs_node"]) + str(form["cost_center"])
        self.assertIn("Direct · C1", rendered)
        self.assertIn("Responsibility · CC1", rendered)
        self.assertNotIn("CBSNode object", rendered)
        self.assertNotIn("CostCenter object", rendered)

    def test_scoped_and_foreign_equipment_mutation_boundaries_remain_denied(self):
        reader, _, _ = self.member("b04-denied", ["equipment.view"], site=self.sibling)
        self.login(reader)
        self.assertEqual(
            self.client.get(reverse("equipment:usage_create")).status_code, 403
        )

    def test_hse_create_persists_tenant_wall_time(self):
        for app, number, field, kind, severity in (
            ("safety", "incident_number", "occurred_at", "near_miss", "low"),
            ("quality", "issue_number", "identified_at", "defect", "minor"),
        ):
            with self.subTest(app=app):
                response = self.client.post(
                    reverse(f"{app}:create"),
                    {
                        "project": self.project.pk,
                        "site": self.site.pk,
                        number: f"B04-{app}",
                        field: "1405/08/10 09:30",
                        "incident_type" if app == "safety" else "issue_type": kind,
                        "severity": severity,
                        "description": "شرح آزمون",
                    },
                )
                self.assertEqual(response.status_code, 302)
                from django.apps import apps

                record = apps.get_model(
                    app, "SafetyIncident" if app == "safety" else "QualityIssue"
                ).objects.get(organization=self.organization)
                self.assertEqual(
                    getattr(record, field), datetime(2026, 11, 1, 6, 0, tzinfo=UTC)
                )
