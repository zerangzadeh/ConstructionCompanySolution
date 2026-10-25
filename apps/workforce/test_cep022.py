"""Employment history, source privacy and assigned shared clearance tests."""

import os
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.documents import test_cep011 as baseline
from apps.documents.services import add_document_version
from apps.organizations.models import (
    BusinessPermission,
    Organization,
    OrganizationMembership,
)
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.services import set_active_organization
from apps.workflows.models import WorkflowInstance, WorkItem
from apps.workflows.runtime import claim_work_item, complete_work_item
from apps.workflows.services import (
    create_workflow_draft,
    edit_workflow_draft,
    publish_workflow_version,
)

from . import employment_services as service
from .models import (
    EmploymentRecord,
    OffboardingCase,
    OffboardingReview,
    WorkRelationshipRevision,
)
from .person_services import end_work_relationship


class EmploymentTests(TestCase):
    def _relationship(self, person, number, *, start=None, end=None, legacy=None):
        # PD-WC-04 own history now requires the explicit Employee.user link too.
        from .models import Employee

        if legacy is None:
            previous = Employee.objects.filter(
                organization=self.organization, user=person.user
            ).first()
            if previous is not None and previous.employee_number != number:
                previous.user = None
                previous.save(update_fields=["user"])
            legacy, _ = Employee.objects.get_or_create(
                organization=self.organization,
                user=person.user,
                defaults={
                    "employee_number": number,
                    "first_name": person.first_name,
                    "last_name": person.last_name,
                },
            )
        return baseline.EmployeeDocumentAccessTests._relationship(
            self, person, number, start=start, end=end, legacy=legacy
        )

    _upload = staticmethod(baseline.EmployeeDocumentAccessTests._upload)
    _document = baseline.EmployeeDocumentAccessTests._document
    _allow = baseline.EmployeeDocumentAccessTests._allow
    _scan_clean = baseline.EmployeeDocumentAccessTests._scan_clean

    def setUp(self):
        baseline.EmployeeDocumentAccessTests.setUp(self)
        self.operator = OrganizationMembership.objects.get(
            organization=self.organization, user=self.owner
        )
        self.operator.role_definition.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=[
                    P.EMPLOYMENT_RECORDS_MANAGE,
                    P.EMPLOYMENT_RECORDS_VIEW_OWN,
                    P.OFFBOARDING_START,
                    P.OFFBOARDING_VIEW,
                    P.OFFBOARDING_REVIEW,
                    P.WORKFLOWS_CREATE,
                    P.WORKFLOWS_CHANGE_DRAFT,
                    P.WORKFLOWS_PUBLISH,
                    P.WORK_ITEMS_VIEW,
                    P.WORK_ITEMS_CLAIM,
                    P.WORK_ITEMS_ACT,
                ]
            )
        )
        self.role.permissions.add(
            BusinessPermission.objects.get(code=P.EMPLOYMENT_RECORDS_VIEW_OWN)
        )
        self._allow(current=True, history=True, download=True)
        self.document = self._document()
        self._scan_clean(self.document.current_version)

    def _record(self, **changes):
        data = {
            "actor": self.owner,
            "organization": self.organization,
            "relationship": self.relationship,
            "record_key": "contract-1",
            "kind": "contract",
            "effective_from": self.relationship.effective_start,
            "effective_to": None,
            "document_version": self.document.current_version,
            "reason": "PRIVATE-SOURCE-REASON",
        }
        return service.record_employment_version(**(data | changes))

    def _own(self, **changes):
        return service.own_employment_history(
            **(
                {"actor": self.employee_user, "organization": self.organization}
                | changes
            )
        )

    def _client(self, user=None):
        user = user or self.employee_user
        self.client.force_login(user)
        session = self.client.session
        set_active_organization(session=session, organization=self.organization)
        session.save()

    def _capture(self, name, response):
        directory = os.environ.get("CEP022_CAPTURE_DIR")
        if directory:
            Path(directory).mkdir(parents=True, exist_ok=True)
            (Path(directory) / (name + ".html")).write_bytes(response.content)

    def _workflow(self):
        draft = create_workflow_draft(
            actor=self.owner,
            organization=self.organization,
            workflow_type_code=service.SUBJECT,
            code="offboarding-test",
            name="بررسی پایان همکاری",
            scope={},
        )
        config = {
            "steps": [
                {"key": "start", "step_type": "start", "is_start": True},
                {
                    "key": "review",
                    "step_type": "approval",
                    "required_permission": P.OFFBOARDING_REVIEW,
                    "configuration": {"decision_policy": "any"},
                    "routing": [
                        {
                            "resolver_type": "business_permission",
                            "configuration": {"permission": P.OFFBOARDING_REVIEW},
                        }
                    ],
                },
                {"key": "end", "step_type": "end", "is_terminal": True},
            ],
            "transitions": [
                {
                    "source": "start",
                    "target": "review",
                    "outcome": "submitted",
                    "is_default": True,
                },
                {
                    "source": "review",
                    "target": "end",
                    "outcome": "complete",
                    "domain_command": service.SUBJECT + ".complete",
                    "required_permission": P.OFFBOARDING_REVIEW,
                },
            ],
        }
        edit_workflow_draft(
            actor=self.owner,
            organization=self.organization,
            version_id=draft.pk,
            configuration=config,
        )
        return publish_workflow_version(
            actor=self.owner, organization=self.organization, version_id=draft.pk
        )

    def _end(self):
        end_work_relationship(
            actor=self.owner,
            organization=self.organization,
            relationship=self.relationship,
            effective_end=self.today - timedelta(days=1),
        )
        return WorkRelationshipRevision.objects.filter(
            relationship=self.relationship
        ).latest("version")

    def _case(self):
        return service.start_offboarding(
            actor=self.owner,
            organization=self.organization,
            end_revision=self._end(),
            workflow_version=self._workflow(),
            reason="PRIVATE-CASE-REASON",
        )

    def _claim(self, case):
        task = WorkItem.objects.get(instance__subject_id=case.pk)
        claim_work_item(
            actor=self.owner,
            organization=self.organization,
            work_item_id=task.pk,
            idempotency_key="claim",
        )
        task.refresh_from_db()
        return task

    def _complete(self, task, **changes):
        values = {
            "actor": self.owner,
            "organization": self.organization,
            "work_item_id": task.pk,
            "outcome": "complete",
            "idempotency_key": "complete",
            "command_context": {
                "workforce_evidence": "PRIVATE-WORKFORCE-CHECK",
                "access_assessment": "PRIVATE-ACCESS-ASSESSMENT no automatic action",
            },
        }
        return complete_work_item(**(values | changes))

    def test_source_history_is_versioned_and_read_only_in_own_ui(self):
        record = self._record()
        rows = self._own().rows
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].document_version_id, record.document_version_id)
        self.assertEqual(record.document_sha256, self.document.current_version.sha256)
        self.assertEqual(record.relationship_revision.version, 1)
        self._client()
        response = self.client.get(reverse("workforce:employment_history"))
        self.assertContains(response, "قرارداد و احکام استخدام من")
        self.assertContains(response, "دریافت سند")
        self.assertNotContains(response, "PRIVATE-SOURCE-REASON")
        self.assertNotContains(response, 'name="record_key"')
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(
            self.client.post(reverse("workforce:employment_history")).status_code, 405
        )
        self._capture("current", response)

    def test_replacement_pins_previous_identity_and_exact_dms_versions(self):
        first = self._record()
        second_version = add_document_version(
            document=self.document, actor=self.owner, upload=self._upload("second.pdf")
        )
        self._scan_clean(second_version)
        second = self._record(
            document_version=second_version, supersedes=first, reason="Replacement"
        )
        self.assertEqual(second.version, 2)
        self.assertEqual(second.supersedes_id, first.pk)
        self.assertEqual(len(self._own().rows), 2)
        first.refresh_from_db()
        self.assertNotEqual(first.document_version_id, second.document_version_id)
        self._client()
        response = self.client.get(reverse("workforce:employment_history"))
        self.assertContains(response, "تاریخی")
        self._capture("history", response)

    def test_missing_permission_or_dms_policy_fails_closed(self):
        self._record()
        self.role.permissions.remove(
            BusinessPermission.objects.get(code=P.EMPLOYMENT_RECORDS_VIEW_OWN)
        )
        with self.assertRaises(PermissionDenied):
            self._own()
        self._client()
        denied = self.client.get(reverse("workforce:employment_history"))
        self.assertEqual(denied.status_code, 403)
        self._capture("denied", denied)
        self.role.permissions.add(
            BusinessPermission.objects.get(code=P.EMPLOYMENT_RECORDS_VIEW_OWN)
        )
        self._allow(current=False, history=False, download=False)
        self.assertEqual(self._own().rows, ())

    def test_cross_person_records_and_unlinked_documents_never_appear(self):
        other = self._document(self.other_relationship)
        self._scan_clean(other.current_version)
        with self.assertRaises(ValidationError):
            self._record(document_version=other.current_version)
        self._record(
            relationship=self.other_relationship, document_version=other.current_version
        )
        self.assertEqual(self._own().rows, ())

    def test_cross_tenant_inputs_fail_closed(self):
        other = Organization.objects.create(name="Other", slug="other-022")
        with self.assertRaises(PermissionDenied):
            self._record(organization=other)
        self.assertEqual(EmploymentRecord.objects.count(), 0)

    def test_future_source_is_not_exposed(self):
        self._record(effective_from=self.today + timedelta(days=1))
        self.assertEqual(self._own().rows, ())

    def test_model_and_services_reject_rewrites_duplicate_and_invalid_sources(self):
        first = self._record()
        for action in (
            first.save,
            first.delete,
            lambda: EmploymentRecord.objects.filter(pk=first.pk).update(
                reason="rewrite"
            ),
        ):
            with self.assertRaises(ValidationError):
                action()
        with self.assertRaises(ValidationError):
            self._record()
        with self.assertRaises(ValidationError):
            self._record(
                supersedes=first, effective_to=first.effective_from - timedelta(days=1)
            )
        self.assertEqual(EmploymentRecord.objects.count(), 1)

    def test_document_scan_and_download_policy_are_preserved(self):
        unscanned = self._document()
        with self.assertRaises(ValidationError):
            self._record(document_version=unscanned.current_version)
        self._record()
        self._allow(current=True, history=True, download=False)
        self._client()
        response = self.client.get(reverse("workforce:employment_history"))
        self.assertContains(response, "دریافت این نسخه سند در دسترس نیست.")
        self.assertNotContains(response, "دریافت سند")
        self._capture("download_unavailable", response)
        self._allow(current=True, history=True, download=True)
        self.role.permissions.remove(
            BusinessPermission.objects.get(code=P.DOCUMENTS_DOWNLOAD)
        )
        response = self.client.get(reverse("workforce:employment_history"))
        self.assertNotContains(response, "دریافت سند")
        self.assertEqual(len(self._own().rows), 1)

    def test_empty_and_unavailable_document_states(self):
        self._client()
        response = self.client.get(reverse("workforce:employment_history"))
        self.assertContains(response, "سابقه استخدام مجازی برای نمایش موجود نیست.")
        self._capture("empty", response)
        self.role.permissions.remove(
            BusinessPermission.objects.get(code=P.DOCUMENTS_VIEW)
        )
        response = self.client.get(reverse("workforce:employment_history"))
        self.assertContains(response, "منبع اسناد برای حساب شما در دسترس نیست.")
        self._capture("unavailable", response)

    def test_offboarding_requires_existing_end_event_and_assigned_published_workflow(
        self,
    ):
        version = self._workflow()
        initial = self.relationship.revisions.get(version=1)
        with self.assertRaises(ValidationError):
            service.start_offboarding(
                actor=self.owner,
                organization=self.organization,
                end_revision=initial,
                workflow_version=version,
                reason="Invalid",
            )
        self.assertEqual(OffboardingCase.objects.count(), 0)
        self.relationship.refresh_from_db()
        self.assertIsNone(self.relationship.effective_end)

    def test_end_is_preserved_before_and_after_clearance(self):
        case = self._case()
        self.assertEqual(case.status, "pending")
        self.relationship.refresh_from_db()
        end = self.relationship.effective_end
        task = self._claim(case)
        self._complete(task)
        self.assertEqual(case.status, "complete")
        self.relationship.refresh_from_db()
        self.assertEqual(self.relationship.effective_end, end)
        self.assertTrue(
            self.person.__class__.objects.filter(pk=self.person.pk).exists()
        )
        self.employee_user.refresh_from_db()
        self.assertTrue(self.employee_user.is_active)
        review = OffboardingReview.objects.get(case=case)
        self.assertEqual(review.actor_id, self.owner.pk)
        self.assertEqual(review.work_item_id, task.pk)
        self.assertEqual(
            review.source_snapshot["revision_id"], str(case.end_revision_id)
        )

    def test_required_outcomes_cannot_be_skipped_and_invalid_action_rolls_back(self):
        case = self._case()
        task = self._claim(case)
        for context in (
            {},
            {"workforce_evidence": "checked"},
            {
                "workforce_evidence": "checked",
                "access_assessment": "checked",
                "blocking_payroll": True,
            },
        ):
            with self.subTest(context=context), self.assertRaises(ValidationError):
                self._complete(task, command_context=context)
        self.assertFalse(OffboardingReview.objects.exists())
        task.refresh_from_db()
        self.assertEqual(task.status, "claimed")
        self.assertEqual(case.status, "pending")
        for outcome in ("reject", "cancel", "correct"):
            with self.subTest(outcome=outcome), self.assertRaises(ValidationError):
                self._complete(task, outcome=outcome)
        self.assertFalse(OffboardingReview.objects.exists())

    def test_permission_and_actual_assignment_required_for_clearance(self):
        case = self._case()
        task = WorkItem.objects.get(instance__subject_id=case.pk)
        with self.assertRaises((PermissionDenied, ValidationError)):
            self._complete(task)
        task = self._claim(case)
        with self.assertRaises(PermissionDenied):
            self._complete(task, actor=self.employee_user)
        self.assertFalse(OffboardingReview.objects.exists())

    def test_requester_status_omits_confidential_review_and_access_details(self):
        case = self._case()
        self._complete(self._claim(case))
        status = service.requester_status(
            actor=self.owner, organization=self.organization, case_id=case.pk
        )
        self.assertEqual(set(status), {"case_id", "status", "employment_end"})
        self.assertNotIn("PRIVATE", str(status))
        with self.assertRaises(PermissionDenied):
            service.requester_status(
                actor=self.other_user, organization=self.organization, case_id=case.pk
            )

    def test_clearance_and_shared_completion_rollback_together(self):
        case = self._case()
        task = self._claim(case)
        original = OffboardingReview.save

        def fail(record, *args, **kwargs):
            original(record, *args, **kwargs)
            raise ValidationError("Synthetic post-insert failure")

        with (
            patch.object(OffboardingReview, "save", fail),
            self.assertRaises(ValidationError),
        ):
            self._complete(task)
        self.assertFalse(OffboardingReview.objects.exists())
        task.refresh_from_db()
        self.assertEqual(task.status, "claimed")
        self.assertEqual(
            WorkflowInstance.objects.get(subject_id=case.pk).status, "active"
        )

    def test_reconciled_capabilities_are_not_implicit_owner_admin_grants(self):
        from apps.organizations.role_defaults import DEFAULT_ROLE_PERMISSIONS

        new = {
            P.EMPLOYMENT_RECORDS_MANAGE,
            P.EMPLOYMENT_RECORDS_VIEW_OWN,
            P.OFFBOARDING_START,
            P.OFFBOARDING_VIEW,
            P.OFFBOARDING_REVIEW,
            P.ROSTERS_MANAGE,
            P.ROSTERS_VIEW,
        }
        for role in ("tenant_owner", "tenant_admin"):
            codes = DEFAULT_ROLE_PERMISSIONS[role]
            self.assertFalse(new & set(codes))

    def test_rehire_keeps_prior_episode_employment_evidence(self):
        record = self._record()
        self._end()
        new = self._relationship(self.person, "REHIRE022", start=self.today)
        history = self._own()
        self.assertEqual(len(history.rows), 1)
        self.assertEqual(history.rows[0].status_label, "تاریخی")
        record.refresh_from_db()
        self.assertNotEqual(record.relationship_id, new.pk)
        self.assertEqual(record.relationship_revision.version, 1)

    def test_category_history_policy_hides_superseded_metadata_even_current_file(self):
        first = self._record()
        self._record(supersedes=first, reason="Metadata correction")
        self._allow(current=True, history=False, download=True)
        self.assertEqual([r.version for r in self._own().rows], [2])

    def test_error_ui_is_private_and_contains_no_source_details(self):
        self._client()
        with patch(
            "apps.workforce.employment_views.own_employment_history",
            side_effect=ValidationError("PRIVATE-INTERNAL-DETAIL"),
        ):
            response = self.client.get(reverse("workforce:employment_history"))
        self.assertContains(response, "دریافت سوابق استخدام ممکن نشد", status_code=400)
        self.assertNotContains(response, "PRIVATE-INTERNAL-DETAIL", status_code=400)
        self.assertIn("no-store", response["Cache-Control"])
        self._capture("error", response)
