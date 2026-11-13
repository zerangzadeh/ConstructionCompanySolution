"""B05 regressions using explicit native authority and disposable PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier

from django.apps import apps
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from apps.audit.models import AuditAction, AuditEvent
from apps.billing import commercial_services, services
from apps.billing.models import ProgressRecordStatus
from apps.billing.test_commercial_controls import CommercialControlFixture
from apps.billing.test_mvp03 import JourneyFixture
from apps.estimates.models import EstimateItem
from apps.estimates.services import create_estimate
from apps.materials.models import UnitOfMeasure
from apps.organizations.models import OrganizationSettings
from apps.projects.services import create_project
from apps.projects.test_command_center import scoped_reader
from apps.workflows.models import WorkItemStatus
from apps.workflows.runtime import claim_work_item, complete_work_item


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class EstimateInputRecoveryTests(JourneyFixture, TestCase):
    def setUp(self):
        self.make_fixture()
        OrganizationSettings.objects.get_or_create(
            organization=self.organization,
            defaults={"timezone": "Asia/Tehran", "currency": "IRR"},
        )
        self.unit = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="B05-M3",
            name="متر مکعب",
            symbol="m³",
            category="volume",
        )
        self.estimate = create_estimate(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            estimate_number="B05-RECOVERY",
            title="برآورد آزمایشی",
        )
        self.login(self.owner)
        self.url = reverse("estimates:detail", args=[self.estimate.pk])

    def data(self, **changes):
        return {
            "description": "بتن‌ریزی آزمایشی",
            "quantity": "1.2345",
            "unit_price": "123.45",
            "unit_of_measure": str(self.unit.pk),
            **changes,
        }

    def test_zero_quantity_retains_bound_inputs_and_reopens_editor(self):
        response = self.client.post(self.url, self.data(quantity="0"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "مقدار ردیف باید مثبت باشد.")
        self.assertEqual(
            response.context["item_form"]["description"].value(), "بتن‌ریزی آزمایشی"
        )
        self.assertEqual(response.context["item_form"]["quantity"].value(), "0")
        self.assertEqual(response.context["item_form"]["unit_price"].value(), "123.45")
        self.assertEqual(
            response.context["item_form"]["unit_of_measure"].value(), str(self.unit.pk)
        )
        self.assertContains(response, 'id="estimate-item-editor" open')
        self.assertFalse(EstimateItem.objects.filter(estimate=self.estimate).exists())

    def test_negative_price_retains_quantity_and_writes_nothing(self):
        response = self.client.post(self.url, self.data(unit_price="-1"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "قیمت واحد ردیف نمی‌تواند منفی باشد.")
        self.assertEqual(response.context["item_form"]["quantity"].value(), "1.2345")
        self.assertFalse(EstimateItem.objects.filter(estimate=self.estimate).exists())

    def test_corrected_input_persists_exact_decimal_line_and_total(self):
        self.client.post(self.url, self.data(quantity="0"))
        response = self.client.post(self.url, self.data())
        self.assertEqual(response.status_code, 302)
        item = EstimateItem.objects.get(estimate=self.estimate)
        self.assertEqual(item.quantity, Decimal("1.2345"))
        self.assertEqual(item.unit_price, Decimal("123.45"))
        self.assertEqual(item.line_total, Decimal("152.40"))
        self.estimate.refresh_from_db()
        self.assertEqual(self.estimate.total_amount, Decimal("152.40"))

    def test_restricted_actor_cannot_use_recovery_to_add_item(self):
        self.login(self.member)
        response = self.client.post(self.url, self.data())
        self.assertIn(response.status_code, (403, 404))
        self.assertFalse(EstimateItem.objects.filter(estimate=self.estimate).exists())


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class CommercialRevisionDetailTests(JourneyFixture, CommercialControlFixture, TestCase):
    def setUp(self):
        self.make_fixture()
        OrganizationSettings.objects.get_or_create(
            organization=self.organization,
            defaults={"timezone": "Asia/Tehran", "currency": "IRR"},
        )
        self.evidence = self.make_evidence("B05-successor")
        self.login(self.owner)

    def test_guarantee_successor_detail_renders_its_own_revision_reason(self):
        original = commercial_services.create_guarantee(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            guarantee_type="performance",
            exposure_side="received",
            instrument_reference="B05-G",
            issuer_name="مرجع مصنوعی",
            amount=Decimal(250),
            issued_on=date(2026, 1, 1),
            effective_from=date(2026, 1, 1),
            expiry_kind="dated",
            expires_on=date(2027, 12, 31),
            evidence_document_version=self.evidence,
            reason="شاهد مصنوعی",
        )
        commercial_services.submit_guarantee(
            organization=self.organization, actor=self.owner, guarantee=original
        )
        commercial_services.decide_guarantee(
            organization=self.organization,
            actor=self.manager,
            guarantee=original,
            approved=True,
            reason="بررسی مستقل",
        )
        successor = commercial_services.create_guarantee_revision(
            organization=self.organization,
            actor=self.owner,
            guarantee=original,
            revision_action="renewal",
            evidence_document_version=self.evidence,
            reason="تمدید ضمانت آزمایشی",
            expires_on=date(2028, 12, 31),
        )
        response = self.client.get(
            reverse("billing:guarantee_detail", args=[successor.pk])
        )
        self.assertContains(response, "تمدید ضمانت آزمایشی")
        original.refresh_from_db()
        self.assertEqual(original.status, "active")
        self.assertEqual(successor.predecessor_id, original.pk)

    def test_compliance_successor_detail_does_not_read_release_only_field(self):
        values = {
            "reference": "B05-E",
            "issuing_authority": "مرجع مصنوعی",
            "effective_from": date(2026, 1, 1),
            "expiry_kind": "dated",
            "expires_on": date(2027, 12, 31),
            "document_version": self.evidence,
        }
        original = commercial_services.create_compliance_evidence(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            evidence_kind="clearance",
            reason="شاهد مصنوعی",
            **values,
        )
        commercial_services.submit_compliance_evidence(
            organization=self.organization, actor=self.owner, evidence=original
        )
        commercial_services.decide_compliance_evidence(
            organization=self.organization,
            actor=self.manager,
            evidence=original,
            approved=True,
            reason="بررسی مستقل",
        )
        successor = commercial_services.create_compliance_evidence_revision(
            organization=self.organization,
            actor=self.owner,
            evidence=original,
            revision_action="renewal",
            reason="تمدید شاهد آزمایشی",
            **{**values, "reference": "B05-E2", "expires_on": date(2028, 12, 31)},
        )
        response = self.client.get(
            reverse("billing:compliance_evidence_detail", args=[successor.pk])
        )
        self.assertContains(response, "تمدید شاهد آزمایشی")
        original.refresh_from_db()
        self.assertEqual(original.status, "approved")
        self.assertEqual(successor.predecessor_id, original.pk)


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class ReceivableMeasurementSeparationTests(JourneyFixture, TestCase):
    def setUp(self):
        self.make_fixture()
        self.measurement = self._record()

    def submit(self, actor):
        return services.request_progress_verification(
            organization=self.organization, actor=actor, record=self.measurement
        )

    def verify(self, actor):
        return services.verify_progress_record(
            organization=self.organization,
            actor=actor,
            record=self.measurement,
            reason="Checked against the signed source",
        )

    def test_creator_and_distinct_submitter_are_denied_with_no_decision(self):
        instance = self.submit(self.manager)
        for actor in (self.owner, self.manager):
            with (
                self.subTest(actor=actor.username),
                self.assertRaisesMessage(PermissionDenied, "ایجادکننده یا ارسال‌کننده"),
            ):
                self.verify(actor)
        self.measurement.refresh_from_db()
        self.assertEqual(self.measurement.status, ProgressRecordStatus.SUBMITTED)
        self.assertIsNone(self.measurement.verified_by_id)
        self.assertEqual(instance.work_items.get().status, WorkItemStatus.OPEN)
        self.assertFalse(
            AuditEvent.objects.filter(
                action=AuditAction.PROGRESS_VERIFIED, entity_id=str(self.measurement.pk)
            ).exists()
        )

    def test_direct_domain_command_and_workbench_cannot_bypass_separation(self):
        instance = self.submit(self.owner)
        item = instance.work_items.get()
        claim_work_item(
            actor=self.owner,
            organization=self.organization,
            work_item_id=item.pk,
            idempotency_key="b05-maker-claim",
        )
        for verify in (
            lambda: services._verify_progress_record_domain(
                organization=self.organization,
                actor=self.owner,
                record=self.measurement,
                reason="Direct attempt",
            ),
            lambda: complete_work_item(
                actor=self.owner,
                organization=self.organization,
                work_item_id=item.pk,
                outcome="verified",
                idempotency_key="b05-maker-verify",
                command_context={"reason": "Workbench attempt"},
            ),
        ):
            with self.assertRaisesMessage(PermissionDenied, "ایجادکننده یا ارسال‌کننده"):
                verify()
        self.measurement.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(self.measurement.status, ProgressRecordStatus.SUBMITTED)
        self.assertEqual(item.status, WorkItemStatus.CLAIMED)
        self.assertFalse(
            item.assignment_history.filter(idempotency_key="b05-maker-verify").exists()
        )

    def test_missing_legacy_actor_fails_closed(self):
        self.submit(self.owner)
        type(self.measurement).objects.filter(pk=self.measurement.pk).update(
            created_by=None
        )
        with self.assertRaisesMessage(PermissionDenied, "هویت ایجادکننده و ارسال‌کننده"):
            self.verify(self.manager)

    def test_only_independent_verifier_in_scope_can_decide_and_replay_is_denied(self):
        permissions = [
            "progress.view",
            "progress.verify",
            "work_items.view",
            "work_items.claim",
            "work_items.act",
        ]
        other_project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="B05-OTHER",
            name="Other project",
        )
        wrong_project, _, _ = scoped_reader(
            self.organization,
            other_project,
            permissions,
            username="b05-wrong-project",
        )
        reviewer, _, _ = scoped_reader(
            self.organization,
            self.project,
            permissions,
            username="b05-scoped-reviewer",
        )
        instance = self.submit(self.owner)
        for actor in (self.member, wrong_project):
            with (
                self.subTest(actor=actor.username),
                self.assertRaises(PermissionDenied),
            ):
                self.verify(actor)
        self.login(reviewer)
        detail_url = reverse("billing:progress_detail", args=[self.measurement.pk])
        self.assertContains(self.client.get(detail_url), "progress-verify-reason")
        response = self.client.post(
            reverse("billing:progress_verify", args=[self.measurement.pk]),
            {"reason": "Scoped independent decision"},
            follow=True,
        )
        self.assertContains(response, "پیشرفت راستی‌آزمایی شد.")
        self.measurement.refresh_from_db()
        self.assertEqual(self.measurement.verified_by, reviewer)
        self.assertEqual(self.measurement.cumulative_quantity, Decimal("0.5000"))
        self.assertEqual(instance.work_items.get().status, WorkItemStatus.COMPLETED)
        with self.assertRaises(ValidationError):
            self.verify(reviewer)
        self.assertEqual(
            AuditEvent.objects.filter(
                action=AuditAction.PROGRESS_VERIFIED,
                entity_id=str(self.measurement.pk),
                organization=self.organization,
                actor=reviewer,
            ).count(),
            1,
        )

    @override_settings(PRODUCT_SURFACE_PROFILE="FULL_ERP")
    def test_full_erp_compatibility_starter_preserves_prior_behavior(self):
        self.submit(self.owner)
        self.assertEqual(self.verify(self.owner).verified_by, self.owner)


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class ReceivableMeasurementConcurrencyTests(JourneyFixture, TransactionTestCase):
    # Include retained legacy tables in Django's test-only cascading flush.
    available_apps = [config.name for config in apps.get_app_configs()]  # noqa: RUF012

    def test_concurrent_verification_commits_one_decision(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL row-lock verification")
        self.make_fixture()
        measurement = self._record()
        instance = services.request_progress_verification(
            organization=self.organization, actor=self.owner, record=measurement
        )
        ready = Barrier(2, timeout=15)

        def verify():
            try:
                ready.wait()
                services.verify_progress_record(
                    organization=self.organization,
                    actor=self.manager,
                    record=measurement,
                    reason="Concurrent independent verification",
                )
                return "verified"
            except ValidationError:
                return "rejected"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            attempts = [pool.submit(verify) for _ in range(2)]
            self.assertCountEqual(
                [attempt.result() for attempt in attempts], ["verified", "rejected"]
            )
        measurement.refresh_from_db()
        self.assertEqual(measurement.verified_by, self.manager)
        self.assertEqual(instance.work_items.get().status, WorkItemStatus.COMPLETED)
        self.assertEqual(
            AuditEvent.objects.filter(
                action=AuditAction.PROGRESS_VERIFIED,
                entity_id=str(measurement.pk),
                organization=self.organization,
            ).count(),
            1,
        )
