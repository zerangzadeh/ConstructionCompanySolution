"""Explicit-policy own request/source-write proofs using synthetic contacts."""

import os
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from apps.organizations.models import BusinessPermission, OrganizationMembership
from apps.organizations.models import BusinessPermissionCode as P
from apps.workflows.models import WorkflowInstance, WorkItem, WorkItemStatus
from apps.workflows.personal_workspaces import build_my_requests
from apps.workflows.runtime import claim_work_item
from apps.workflows.services import (
    create_workflow_draft,
    edit_workflow_draft,
    publish_workflow_version,
)

from . import personal_change_services as source
from . import test_cep053 as baseline
from .models import (
    Employee,
    PersonalDataDecision,
    PersonalDataEnrollment,
    PersonalDataRequest,
)


class PersonalChangeTests(baseline.ESSDashboardTests):
    def setUp(self):
        super().setUp()
        self.hr = self._member(
            "cep055-hr",
            {
                P.PERSONAL_DATA_CONFIGURE,
                P.PERSONAL_DATA_VIEW,
                P.PERSONAL_DATA_REVIEW,
                P.EMPLOYEES_VIEW,
                P.WORKFLOWS_CREATE,
                P.WORKFLOWS_CHANGE_DRAFT,
                P.WORKFLOWS_PUBLISH,
                P.WORK_ITEMS_VIEW,
                P.WORK_ITEMS_CLAIM,
                P.WORK_ITEMS_ACT,
            },
        )
        membership = OrganizationMembership.objects.get(
            user=self.requester, organization=self.organization
        )
        membership.role_definition.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=[P.PERSONAL_DATA_VIEW, P.PERSONAL_DATA_REQUEST]
            )
        )
        self.version = self._version()

    def _capture55(self, name, response):
        directory = os.environ.get("BONIRA_CEP055_CAPTURE_DIR")
        if directory:
            Path(directory, name + ".html").write_bytes(response.content)

    def _version(self):
        version = create_workflow_draft(
            actor=self.hr,
            organization=self.organization,
            workflow_type_code=source.SUBJECT,
            code="synthetic-contact",
            name="تصمیم تغییر ارتباطی",
            scope={},
        )
        config = {
            "steps": [
                {"key": "start", "step_type": "start", "is_start": True},
                {
                    "key": "decision",
                    "name": "مرحله محرمانه رسیدگی",
                    "step_type": "approval",
                    "required_permission": P.PERSONAL_DATA_REVIEW,
                    "configuration": {"decision_policy": "any"},
                    "routing": [
                        {
                            "resolver_type": "business_permission",
                            "configuration": {"permission": P.PERSONAL_DATA_REVIEW},
                        }
                    ],
                },
                {"key": "accepted", "step_type": "end", "is_terminal": True},
                {"key": "rejected", "step_type": "end", "is_terminal": True},
            ],
            "transitions": [
                {
                    "source": "start",
                    "target": "decision",
                    "outcome": "submitted",
                    "is_default": True,
                },
                {
                    "source": "decision",
                    "target": "accepted",
                    "outcome": "accepted",
                    "domain_command": source.SUBJECT + ".accept",
                    "required_permission": P.PERSONAL_DATA_REVIEW,
                },
                {
                    "source": "decision",
                    "target": "rejected",
                    "outcome": "rejected",
                    "domain_command": source.SUBJECT + ".reject",
                    "required_permission": P.PERSONAL_DATA_REVIEW,
                },
            ],
        }
        version = edit_workflow_draft(
            actor=self.hr,
            organization=self.organization,
            version_id=version.pk,
            configuration=config,
        )
        return publish_workflow_version(
            actor=self.hr, organization=self.organization, version_id=version.pk
        )

    def _policy(self, family="phone", field="phone_number", cancel=True):
        return source.configure_enrollment(
            actor=self.hr,
            organization=self.organization,
            family=family,
            source_field=field,
            workflow_version=self.version,
            cancellation_allowed=cancel,
            reason="Explicit synthetic enrollment",
        )

    def _submit55(self, policy=None, value="02112345678", key="request-1"):
        return source.submit_change(
            actor=self.requester,
            organization=self.organization,
            enrollment_id=(policy or self._policy()).pk,
            proposed_value=value,
            reason="به‌روزرسانی راه ارتباطی",
            idempotency_key=key,
        )

    def _claim55(self, item):
        task = WorkItem.objects.get(instance=source.instance_for(item))
        claim_work_item(
            actor=self.hr,
            organization=self.organization,
            work_item_id=task.pk,
            idempotency_key="claim-" + str(item.pk),
        )
        return task

    def _decide55(self, item, task, outcome="accepted", reason="تصمیم قابل نمایش"):
        return source.decide_change(
            actor=self.hr,
            organization=self.organization,
            request_id=item.pk,
            work_item_id=task.pk,
            outcome=outcome,
            reason=reason,
            idempotency_key="decision-" + str(item.pk),
        )

    def test_all_five_governed_enrollment_rows_apply_only_own_source_after_acceptance(
        self,
    ):
        for index, (family, field, value) in enumerate(
            [
                ("phone", "phone_number", "02110000001"),
                ("email", "email", "synthetic@example.invalid"),
                ("address", "address", "نشانی مصنوعی آزمون"),
                ("emergency", "emergency_contact", "تماس اضطراری مصنوعی"),
                ("enrolled_contact", "phone_number", "02110000002"),
            ]
        ):
            policy = self._policy(family, field)
            before = getattr(Employee.objects.get(pk=self.requester_employee.pk), field)
            item = self._submit55(policy, value, key=f"request-{index}")
            self.assertEqual(
                getattr(Employee.objects.get(pk=self.requester_employee.pk), field),
                before,
            )
            task = self._claim55(item)
            self._decide55(item, task)
            self.assertEqual(
                getattr(Employee.objects.get(pk=self.requester_employee.pk), field),
                value,
            )
            self.assertEqual(item.previous_value, before)
            self.assertEqual(
                PersonalDataDecision.objects.get(request=item).action, "accepted"
            )
            self.assertEqual(source.instance_for(item).status, "completed")
        self.requester.refresh_from_db()
        self.assertEqual(self.requester.email, "")
        self.assertEqual(self.requester.phone_number, "")
        self.assertEqual(PersonalDataDecision.objects.count(), 5)

    def test_request_retry_source_comparison_and_audit_failure_rollback(self):
        policy = self._policy()
        item = self._submit55(policy)
        self.assertEqual(self._submit55(policy).pk, item.pk)
        with self.assertRaises(ValidationError):
            self._submit55(policy, "02199999999")
        task = self._claim55(item)
        with (
            patch(
                "apps.workflows.runtime.record_audit_event",
                side_effect=RuntimeError("audit-failure"),
            ),
            self.assertRaises(RuntimeError),
        ):
            self._decide55(item, task)
        self.assertEqual(
            Employee.objects.get(pk=self.requester_employee.pk).phone_number, ""
        )
        self.assertFalse(PersonalDataDecision.objects.exists())
        task.refresh_from_db()
        self.assertEqual(task.status, WorkItemStatus.CLAIMED)
        Employee.objects.filter(pk=self.requester_employee.pk).update(
            phone_number="source-changed"
        )
        with self.assertRaises(ValidationError):
            self._decide55(item, task)
        self.assertFalse(PersonalDataDecision.objects.exists())
        self.assertEqual(
            Employee.objects.get(pk=self.requester_employee.pk).phone_number,
            "source-changed",
        )

    def test_rejection_and_explicit_cancellation_never_change_source(self):
        item = self._submit55()
        task = self._claim55(item)
        self._decide55(item, task, outcome="rejected", reason="دلیل رد مجاز")
        self.assertEqual(
            PersonalDataDecision.objects.get(request=item).action, "rejected"
        )
        self.assertEqual(
            Employee.objects.get(pk=self.requester_employee.pk).phone_number, ""
        )
        policy = item.enrollment
        item2 = self._submit55(policy, "02122222222", key="request-2")
        source.cancel_change(
            actor=self.requester,
            organization=self.organization,
            request_id=item2.pk,
            reason="لغو قبل از تغییر",
            idempotency_key="cancel-2",
        )
        self.assertEqual(source.instance_for(item2).status, "cancelled")
        self.assertEqual(
            PersonalDataDecision.objects.get(request=item2).action, "cancelled"
        )
        self.assertEqual(
            Employee.objects.get(pk=self.requester_employee.pk).phone_number, ""
        )
        no_cancel = self._policy(cancel=False)
        item3 = self._submit55(no_cancel, "02133333333", key="request-3")
        with self.assertRaises(PermissionDenied):
            source.cancel_change(
                actor=self.requester,
                organization=self.organization,
                request_id=item3.pk,
                reason="not enrolled",
                idempotency_key="cancel-3",
            )
        self.assertFalse(PersonalDataDecision.objects.filter(request=item3).exists())

    def test_permission_tenant_assignment_and_sensitive_fields_fail_closed(self):
        for field in ("national_id", "bank_account", "user.email", "status"):
            with self.assertRaises(ValidationError):
                self._policy("enrolled_contact", field)
        item = self._submit55()
        for actor in (self.other, self.title_only):
            with self.assertRaises(PermissionDenied):
                source.get_request(
                    actor=actor, organization=self.organization, request_id=item.pk
                )
        self._login(self.other)
        denied = self.client.get(
            reverse("workforce:personal_change_detail", args=[item.pk])
        )
        missing = self.client.get(
            reverse("workforce:personal_change_detail", args=[uuid4()])
        )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.content, missing.content)
        self._capture55("unauthorized", denied)
        from apps.organizations.services import create_organization_with_owner

        foreign = create_organization_with_owner(
            owner=self.other, name="Foreign", slug="cep055-foreign"
        )
        with self.assertRaises(PermissionDenied):
            source.get_request(
                actor=self.requester, organization=foreign, request_id=item.pk
            )
        with self.assertRaises(ValidationError):
            item.reason = "overwrite"
            item.save()

    def test_unresolved_route_and_unknown_policy_roll_back_entire_request(self):
        with self.assertRaises(ValidationError):
            source.submit_change(
                actor=self.requester,
                organization=self.organization,
                enrollment_id=uuid4(),
                proposed_value="x",
                reason="test",
                idempotency_key="missing",
            )
        policy = self._policy()
        OrganizationMembership.objects.get(
            user=self.hr, organization=self.organization
        ).role_definition.permissions.remove(
            BusinessPermission.objects.get(code=P.PERSONAL_DATA_REVIEW)
        )
        with self.assertRaises(ValidationError):
            self._submit55(policy)
        self.assertEqual(PersonalDataRequest.objects.count(), 0)
        self.assertEqual(
            WorkflowInstance.objects.filter(subject_type=source.SUBJECT).count(), 0
        )

    def test_own_status_adapters_preserve_source_scope_and_hide_internal_metadata(self):
        item = self._submit55()
        self._login(self.requester)
        index = self.client.get(reverse("workforce:ess_requests"))
        self.assertEqual(index.status_code, 200)
        self.assertContains(index, "تغییر اطلاعات شخصی")
        self.assertNotContains(index, item.proposed_value)
        self._capture55("requests", index)
        self.assertEqual(
            {
                r.source_type
                for r in build_my_requests(
                    actor=self.requester, organization=self.organization
                )
            },
            {"leave", "overtime", "personal_data"},
        )
        status = self.client.get(
            reverse("workforce:ess_request_status", args=["leave", self.own_leave.pk])
        )
        self.assertContains(status, self.own_leave.state)
        self.assertNotContains(status, self.other_leave.reason)
        self._capture55("status", status)
        self.assertEqual(
            self.client.get(
                reverse(
                    "workforce:ess_request_status", args=["leave", self.other_leave.pk]
                )
            ).status_code,
            403,
        )
        # Explicitly contradictory legacy identity is not an ESS source adapter.
        from apps.timekeeping.models import LeaveMissionRequest

        Employee.objects.filter(pk=self.requester_employee.pk).update(user=None)
        Employee.objects.filter(pk=self.other_employee.pk).update(user=self.requester)
        forged = LeaveMissionRequest.objects.create(
            organization=self.organization,
            employee=self.other_employee,
            requested_by=self.requester,
            kind=self.own_leave.kind,
            category_code=self.own_leave.category_code,
            starts_at=self.own_leave.starts_at,
            ends_at=self.own_leave.ends_at,
            reason="must not leak",
        )
        self.assertNotIn(
            forged.pk,
            {
                r.source_id
                for r in build_my_requests(
                    actor=self.requester, organization=self.organization
                )
            },
        )

    def test_localized_form_handler_decision_empty_error_and_read_only_current_value(
        self,
    ):
        self._login(self.requester)
        empty = self.client.get(reverse("workforce:personal_change_inbox"))
        self.assertContains(empty, "درخواست تغییر مجازی برای نمایش موجود نیست.")
        self._capture55("empty", empty)
        self._policy()
        form = self.client.get(reverse("workforce:personal_change_create"))
        self.assertEqual(form.status_code, 200)
        self._capture55("form", form)
        item = self._submit55(PersonalDataEnrollment.objects.first())
        response = self.client.get(
            reverse("workforce:personal_change_detail", args=[item.pk])
        )
        self.assertContains(response, "مقدار پیشنهادی")
        self.assertNotContains(response, "ثبت تصمیم گردش‌کار")
        self.assertNotContains(response, "مرحله محرمانه رسیدگی")
        self._capture55("detail", response)
        with patch(
            "apps.workforce.personal_change_views.build_my_requests",
            side_effect=ValidationError("private diagnostic"),
        ):
            error = self.client.get(reverse("workforce:ess_requests"))
        self.assertEqual(error.status_code, 400)
        self.assertNotIn(b"private diagnostic", error.content)
        self._capture55("error", error)
        self._login(self.hr)
        self._claim55(item)
        handler = self.client.get(
            reverse("workforce:personal_change_detail", args=[item.pk])
        )
        self.assertContains(handler, "ثبت تصمیم گردش‌کار")
        self.assertContains(handler, "مرحله محرمانه رسیدگی")
        self._capture55("handler", handler)
        response = self.client.post(
            reverse("workforce:personal_change_detail", args=[item.pk]),
            {
                "outcome": "accepted",
                "reason": "پذیرش صریح",
                "idempotency_key": "ui-decision",
            },
        )
        self.assertEqual(response.status_code, 302)
        self._login(self.requester)
        accepted = self.client.get(
            reverse("workforce:personal_change_detail", args=[item.pk])
        )
        self.assertContains(accepted, "پذیرش صریح")
        self._capture55("accepted", accepted)

    def test_owner_admin_not_implicitly_granted_personal_profile_mutation(self):
        from apps.organizations.role_defaults import DEFAULT_ROLE_PERMISSIONS

        for codes in (
            DEFAULT_ROLE_PERMISSIONS[role] for role in ("tenant_owner", "tenant_admin")
        ):
            self.assertFalse(
                {
                    P.PERSONAL_DATA_VIEW,
                    P.PERSONAL_DATA_REQUEST,
                    P.PERSONAL_DATA_REVIEW,
                    P.PERSONAL_DATA_CONFIGURE,
                }
                & codes
            )
        self._login(self.requester)
        response = self.client.post(
            reverse("workforce:ess_profile"),
            {"phone_number": "unsafe", "email": "unsafe@example.invalid"},
        )
        self.assertEqual(response.status_code, 405)
        self.assertEqual(
            Employee.objects.get(pk=self.requester_employee.pk).phone_number, ""
        )

    def test_identity_revocation_blocks_source_acceptance_and_preserves_history(self):
        from .models import Person

        item = self._submit55()
        task = self._claim55(item)
        Person.objects.filter(pk=self.relationship.person_id).update(user=None)
        with self.assertRaises(PermissionDenied):
            self._decide55(item, task)
        self.assertFalse(PersonalDataDecision.objects.exists())
        self.assertEqual(
            Employee.objects.get(pk=self.requester_employee.pk).phone_number, ""
        )
        task.refresh_from_db()
        self.assertEqual(task.status, WorkItemStatus.CLAIMED)
