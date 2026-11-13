"""MVP Equipment and HSE write boundaries with real tenant grants."""

from importlib import import_module

from django.apps import apps
from django.test import Client, TestCase
from django.urls import reverse

from apps.audit.models import AuditEvent
from apps.equipment.models import Equipment, EquipmentAssignment
from apps.equipment.p8_models import EquipmentUsageLog, OperatorEquipmentQualification
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.workforce.models import EmployeeQualification
from tests.test_b02_remediation import B02Fixture


class EquipmentUsageBoundaryTests(B02Fixture, TestCase):
    def setUp(self):
        self.make_fixture()
        self.equipment = Equipment.objects.create(
            organization=self.organization,
            code="FINAL",
            name="تجهیز آزمون",
            category="ماشین‌آلات",
        )
        self.deployment = EquipmentAssignment.objects.create(
            organization=self.organization,
            equipment=self.equipment,
            project=self.project,
            site=self.site,
            status="active",
            start_date=self.day,
        )
        self.url = reverse("equipment:usage_create")
        self.payload = {
            "equipment": self.equipment.pk,
            "started_at": "1405/08/10 08:00",
            "ended_at": "1405/08/10 10:00",
            "runtime_hours": "2.000",
            "source_key": "B04-FINAL-1",
        }
        self.login(self.owner)

    def test_interval_overlap_adjacent_replay_and_conflicting_key(self):
        response = self.client.post(self.url, {**self.payload, "runtime_hours": "20"})
        self.assertIn("runtime_hours", response.context["form"].errors)
        self.assertEqual(self.client.post(self.url, self.payload).status_code, 302)
        source = EquipmentUsageLog.objects.get(source_key=self.payload["source_key"])
        self.assertEqual(source.deployment_id, self.deployment.pk)
        self.assertEqual(source.started_at, self.moment(8))
        self.assertIsNone(source.operator_id)
        self.assertEqual(self.client.post(self.url, self.payload).status_code, 302)
        self.assertEqual(AuditEvent.objects.filter(entity_id=str(source.pk)).count(), 1)
        response = self.client.post(self.url, {**self.payload, "runtime_hours": "1"})
        self.assertIn("source_key", response.context["form"].errors)
        response = self.client.post(self.url, {**self.payload, "source_key": "overlap"})
        self.assertIn("started_at", response.context["form"].errors)
        self.assertEqual(
            self.client.post(
                self.url,
                {
                    **self.payload,
                    "started_at": "1405/08/10 10:00",
                    "ended_at": "1405/08/10 12:00",
                    "source_key": "adjacent",
                },
            ).status_code,
            302,
        )
        self.assertEqual(
            EquipmentUsageLog.objects.filter(equipment=self.equipment).count(), 2
        )

    def test_operator_validity_and_explicit_deployment(self):
        qualification = EmployeeQualification.objects.create(
            organization=self.organization,
            employee=self.employee,
            kind="certificate",
            title="صلاحیت آزمون",
            issued_on=self.day,
            valid_until=self.day,
            recorded_by=self.owner,
        )
        OperatorEquipmentQualification.objects.create(
            organization=self.organization,
            equipment=self.equipment,
            employee=self.employee,
            workforce_qualification=qualification,
            effective_from=self.day,
            created_by=self.owner,
        )
        data = {
            **self.payload,
            "operator": self.employee.pk,
            "deployment": self.deployment.pk,
        }
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        self.assertEqual(
            EquipmentUsageLog.objects.get(
                source_key=self.payload["source_key"]
            ).operator_id,
            self.employee.pk,
        )
        response = self.client.post(
            self.url,
            {
                **data,
                "started_at": "1405/08/11 08:00",
                "ended_at": "1405/08/11 10:00",
                "source_key": "expired",
            },
        )
        self.assertIn("operator", response.context["form"].errors)
        self.assertFalse(
            EquipmentUsageLog.objects.filter(source_key="expired").exists()
        )

    def test_sibling_site_cannot_forge_deployment(self):
        sibling, _, _ = self.member(
            "usage-sibling", ["equipment_usage.record"], site=self.sibling
        )
        self.login(sibling)
        response = self.client.get(self.url)
        self.assertNotContains(response, str(self.deployment.pk))
        response = self.client.post(
            self.url, {**self.payload, "deployment": self.deployment.pk}
        )
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(
            EquipmentUsageLog.objects.filter(equipment=self.equipment).exists()
        )
        recorder, _, _ = self.member(
            "usage-site", ["equipment_usage.record"], site=self.site
        )
        self.login(recorder)
        self.assertEqual(self.client.post(self.url, self.payload).status_code, 302)
        self.assertEqual(
            EquipmentUsageLog.objects.get(
                source_key=self.payload["source_key"]
            ).deployment_id,
            self.deployment.pk,
        )


class RecordDecisionBoundaryTests(B02Fixture, TestCase):
    def setUp(self):
        self.make_fixture()

    def test_decisions_preserve_operational_state_and_reject_self_stale_and_out_of_scope(
        self,
    ):
        for app, model_name, noun, prefix in (
            ("safety", "SafetyIncident", "incident", "safety_incidents"),
            ("quality", "QualityIssue", "issue", "quality_issues"),
        ):
            with self.subTest(app=app):
                service = import_module(f"apps.{app}.record_review")
                permissions = [f"{prefix}.view", f"{prefix}.record_decide"]
                reviewer, _, _ = self.member(
                    f"{app}-decision", permissions, site=self.site
                )
                sibling, _, _ = self.member(
                    f"{app}-sibling", permissions, site=self.sibling
                )
                self.login(self.owner)
                response = self.client.post(
                    reverse(f"{app}:create"),
                    {
                        "project": self.project.pk,
                        "site": self.site.pk,
                        f"{noun}_number": f"B04-FINAL-{app}",
                        "occurred_at"
                        if app == "safety"
                        else "identified_at": "1405/08/10 09:30",
                        f"{noun}_type": "near_miss" if app == "safety" else "defect",
                        "severity": "low" if app == "safety" else "minor",
                        "description": "شرح آزمون",
                    },
                )
                self.assertEqual(response.status_code, 302)
                record = apps.get_model(app, model_name).objects.get(
                    organization=self.organization
                )
                submit = getattr(service, f"submit_{app}_record")
                submission = submit(
                    organization=self.organization,
                    actor=self.owner,
                    **{f"{noun}_id": record.pk},
                    reason="ارسال آزمون",
                )
                url = reverse(f"{app}:record_decision", args=[record.pk])
                data = {
                    "submission_id": submission.pk,
                    "outcome": "approved",
                    "reason": "بررسی مستقل",
                }
                self.assertEqual(self.client.post(url, data).status_code, 403)
                self.login(sibling)
                self.assertEqual(self.client.post(url, data).status_code, 403)
                self.login(reviewer)
                csrf = Client(enforce_csrf_checks=True)
                csrf.force_login(reviewer)
                session = csrf.session
                session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
                session.save()
                self.assertEqual(csrf.post(url, data).status_code, 403)
                self.assertEqual(self.client.get(url).status_code, 200)
                self.assertEqual(
                    self.client.post(url, {**data, "reason": " "}).status_code, 400
                )
                self.assertEqual(self.client.post(url, data).status_code, 302)
                self.assertEqual(self.client.post(url, data).status_code, 302)
                self.assertEqual(
                    self.client.post(url, {**data, "outcome": "returned"}).status_code,
                    400,
                )
                record.refresh_from_db()
                self.assertEqual(record.status, "reported")
                self.assertEqual(record.review_status, "approved")
                self.assertEqual(record.review_revisions.count(), 2)
