"""Own Mission HTTP/source/identity proofs and synthetic governed routing linkage."""

import json
import os
import re
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import JournalEntry
from apps.audit.models import AuditEvent
from apps.expenses.models import Expense, PlatformExpenseGroup
from apps.organizations.models import (
    BusinessPermission,
    MembershipScopeGrant,
    OrganizationMembership,
)
from apps.organizations.models import BusinessPermissionCode as P
from apps.projects.models import Project
from apps.timekeeping import mission_routing as routing
from apps.timekeeping import services as source
from apps.timekeeping.mission_models import MissionEffect
from apps.timekeeping.models import LeaveMissionRequest
from apps.treasury.models import PaymentRequest, TreasuryMovement
from core.jalali import format_jalali

from . import ess_timekeeping as service
from . import test_cep063 as fixture
from .models import WorkRelationship


class ESSMissionTests(TestCase):
    client_for = fixture.ESSTimekeepingTests.client_for

    def setUp(self):
        fixture.ESSTimekeepingTests.setUp(self)
        self.organization.settings.timezone = "Asia/Tehran"
        self.organization.settings.save(update_fields=["timezone", "updated_at"])
        self.role.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=(P.LEAVE_MISSION_VIEW, P.LEAVE_MISSION_REQUEST)
            )
        )
        self.start = timezone.now().replace(second=0, microsecond=0) + timedelta(days=2)

    def create(self, **kwargs):
        values = {
            "actor": self.employee_user,
            "organization": self.organization,
            "category_code": "آزمایشی",
            "starts_at": self.start,
            "ends_at": self.start + timedelta(hours=4),
            "reason": "شرح مأموریت شخصی آزمایشی",
        }
        values.update(kwargs)
        return service.create_own_mission(**values)

    def url(self, action, record=None):
        return reverse(
            "workforce:ess_timekeeping_" + action,
            args=["mission"] + ([record.pk] if record else []),
        )

    def data(self):
        zone = ZoneInfo(self.organization.settings.timezone)
        return {
            "category_code": "آزمایشی",
            "starts_at": format_jalali(
                timezone.localtime(self.start, zone), include_time=True
            ),
            "ends_at": format_jalali(
                timezone.localtime(self.start + timedelta(hours=4), zone),
                include_time=True,
            ),
            "reason": "شرح مأموریت شخصی آزمایشی",
        }

    def capture(self, name, response):
        directory = os.environ.get("BONIRA_CEP068_MISSION_CAPTURE_DIR")
        if directory:
            body = re.sub(
                rb'name="csrfmiddlewaretoken" value="[^"]+"',
                b'name="csrfmiddlewaretoken" value="SYNTHETIC-EVIDENCE"',
                response.content,
            )
            Path(directory, name + ".html").write_bytes(body)

    def submit(self, record):
        return service.submit_own(
            actor=self.employee_user,
            organization=self.organization,
            kind="mission",
            record_id=record.pk,
        )

    def approve(self, record):
        self.submit(record)
        record.refresh_from_db()
        record.policy_reference = "PRIVATE-SYNTHETIC-POLICY"
        record.save()
        return source.review_time_request(
            organization=self.organization,
            actor=self.actor,
            request=record,
            approve=True,
            reason="PRIVATE-REVIEWER-DETAIL",
        )

    def test_native_source_create_submit_and_identity_audit_are_atomic(self):
        record = self.create()
        self.submit(record)
        record.refresh_from_db()
        self.assertEqual(record.kind, "mission")
        self.assertEqual(record.employee_id, self.employee.pk)
        self.assertEqual(record.state, "submitted")
        self.assertEqual(record.policy_reference, "")
        events = AuditEvent.objects.filter(
            entity_id=str(record.pk), metadata__origin="ess_mission"
        )
        self.assertEqual(events.count(), 2)
        self.assertTrue(
            all(
                x.metadata["relationship_id"] == str(self.relationship.pk)
                for x in events
            )
        )
        self.assertFalse(MissionEffect.objects.exists())
        with self.assertRaises(PermissionDenied):
            self.submit(record)
        with self.assertRaises(PermissionDenied):
            source.review_time_request(
                organization=self.organization,
                actor=self.employee_user,
                request=record,
                approve=True,
                reason="Self approval forbidden",
            )

    def test_persian_jalali_http_empty_form_error_draft_and_submit(self):
        client = self.client_for()
        empty = client.get(reverse("workforce:ess_timekeeping"))
        self.assertContains(empty, "درخواست‌های مأموریت من")
        self.capture("empty", empty)
        form = client.get(self.url("create"))
        self.assertContains(form, "درخواست مأموریت")
        self.assertContains(form, 'data-jalali-date="datetime"')
        self.assertContains(form, 'dir="rtl"')
        for field in (
            "employee",
            "organization",
            "policy_reference",
            "rate",
            "amount",
            "route",
        ):
            self.assertNotContains(form, 'name="' + field + '"')
        self.capture("form", form)
        result = client.post(self.url("create"), self.data())
        self.assertEqual(result.status_code, 302)
        record = LeaveMissionRequest.objects.get(kind="mission")
        draft = client.get(result.url)
        self.assertContains(draft, "پیش‌نویس")
        self.assertContains(draft, "ارجاع مالی ثبت نشده است")
        self.capture("draft", draft)
        submitted = client.post(self.url("submit", record))
        self.assertEqual(submitted.status_code, 302)
        detail = client.get(submitted.url)
        self.assertContains(detail, "ارسال‌شده")
        self.capture("submitted", detail)
        listed = client.get(reverse("workforce:ess_timekeeping"))
        self.assertContains(listed, "ارسال‌شده")
        self.capture("list", listed)
        invalid = client.post(
            self.url("create"), {**self.data(), "ends_at": self.data()["starts_at"]}
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertContains(
            invalid, "پایان مأموریت باید پس از شروع باشد", status_code=400
        )
        self.capture("error", invalid)

    def test_peer_missing_foreign_and_wrong_source_kind_have_identical_denial(self):
        own = self.create()
        peer = LeaveMissionRequest.objects.create(
            organization=self.organization,
            employee=self.peer,
            kind="mission",
            category_code="private",
            starts_at=self.start,
            ends_at=self.start + timedelta(hours=1),
            requested_by=self.actor,
            reason="PEER-PRIVATE",
        )
        client = self.client_for()
        denied = client.get(self.url("detail", peer))
        missing = client.get(
            reverse("workforce:ess_timekeeping_detail", args=["mission", uuid4()])
        )

        def normalize(content):
            content = re.sub(
                rb'name="csrfmiddlewaretoken" value="[^"]+"', b"CSRF", content
            )
            return re.sub(rb"mission/[0-9a-f-]{36}/", b"mission/REQUEST/", content)

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(normalize(denied.content), normalize(missing.content))
        self.assertNotContains(denied, "PEER-PRIVATE", status_code=403)
        self.assertEqual(client.post(self.url("submit", peer)).status_code, 403)
        self.assertEqual(client.get(self.url("detail", own)).status_code, 200)
        self.capture("denied", denied)
        LeaveMissionRequest.objects.filter(pk=own.pk).update(kind="leave")
        self.assertEqual(client.get(self.url("detail", own)).status_code, 403)
        with self.assertRaises(PermissionDenied):
            service.own_record(
                actor=self.employee_user,
                organization=self.other,
                kind="mission",
                record_id=own.pk,
            )

    def test_forged_identity_financial_policy_and_csrf_never_create_source(self):
        client = self.client_for()
        for key in (
            "employee_id",
            "organization_id",
            "person_id",
            "relationship_id",
            "policy_reference",
            "route",
            "effect_id",
            "mission_version",
            "amount",
            "rate",
            "cap",
            "multiplier",
            "state",
            "approved_by",
        ):
            with self.subTest(key=key):
                self.assertEqual(
                    client.post(
                        self.url("create"), {**self.data(), key: str(uuid4())}
                    ).status_code,
                    400,
                )
        self.assertFalse(LeaveMissionRequest.objects.filter(kind="mission").exists())
        self.assertEqual(
            self.client_for(csrf=True)
            .post(self.url("create"), self.data())
            .status_code,
            403,
        )

    def test_attachments_remain_unavailable_without_approved_source_policy(self):
        result = self.client_for().post(
            self.url("create"),
            {**self.data(), "evidence": SimpleUploadedFile("synthetic.txt", b"test")},
        )
        self.assertEqual(result.status_code, 400)
        self.assertFalse(LeaveMissionRequest.objects.filter(kind="mission").exists())

    def test_identity_link_and_membership_or_permission_removal_fail_closed(self):
        person = self.relationship.person
        person.user = None
        person.save()
        self.employee.user = self.employee_user
        self.employee.save()
        with self.assertRaises(PermissionDenied):
            self.create()
        person.user = self.employee_user
        person.save()
        membership = OrganizationMembership.objects.get(
            user=self.employee_user, organization=self.organization
        )
        membership.status = "suspended"
        membership.save(update_fields=["status"])
        with self.assertRaises(PermissionDenied):
            self.create()
        membership.status = "active"
        membership.save(update_fields=["status"])
        self.role.permissions.remove(
            BusinessPermission.objects.get(code=P.LEAVE_MISSION_REQUEST)
        )
        self.assertEqual(self.client_for().get(self.url("create")).status_code, 403)

    def test_episode_bounds_and_overlap_are_source_owned(self):
        for changes in (
            {"ends_at": self.start},
            {"starts_at": self.start.replace(tzinfo=None)},
            {"starts_at": self.start.replace(year=2024)},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.create(**changes)
        record = self.create()
        with self.assertRaises(ValidationError):
            self.create()
        WorkRelationship.objects.filter(pk=self.relationship.pk).update(
            effective_start=self.start.date() + timedelta(days=1)
        )
        with self.assertRaises(PermissionDenied):
            service.own_record(
                actor=self.employee_user,
                organization=self.organization,
                kind="mission",
                record_id=record.pk,
            )

    def test_project_scope_is_intersected_on_forms_service_and_reads(self):
        membership = OrganizationMembership.objects.get(
            user=self.employee_user, organization=self.organization
        )
        MembershipScopeGrant.objects.filter(membership=membership).delete()
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type="project",
            project=self.project,
            reason="Explicit test source scope",
        )
        other = Project.objects.create(
            organization=self.organization,
            code="OUTSIDE",
            name="PRIVATE-OUTSIDE-PROJECT",
            created_by=self.actor,
        )
        form = self.client_for().get(self.url("create"))
        self.assertEqual(form.status_code, 200)
        self.assertNotContains(form, "PRIVATE-OUTSIDE-PROJECT")
        with self.assertRaises(PermissionDenied):
            self.create(project=other)
        record = self.create(project=self.project)
        self.assertEqual(
            service.own_record(
                actor=self.employee_user,
                organization=self.organization,
                kind="mission",
                record_id=record.pk,
            ).pk,
            record.pk,
        )
        self.assertEqual(
            self.client_for()
            .post(self.url("create"), {**self.data(), "project": str(other.pk)})
            .status_code,
            400,
        )

    def test_audit_failure_rolls_back_native_source_and_submission(self):
        with (
            patch.object(
                service, "record_audit_event", side_effect=ValidationError("audit")
            ),
            self.assertRaises(ValidationError),
        ):
            self.create()
        self.assertFalse(LeaveMissionRequest.objects.filter(kind="mission").exists())
        record = self.create()
        with (
            patch.object(
                service, "record_audit_event", side_effect=ValidationError("audit")
            ),
            self.assertRaises(ValidationError),
        ):
            self.submit(record)
        record.refresh_from_db()
        self.assertEqual(record.state, "draft")

    def test_identity_switch_before_audit_rolls_back_the_qualified_source(self):
        from .models import Person
        from .person_services import create_person, create_work_relationship

        peer_person = create_person(
            organization=self.organization,
            actor=self.actor,
            first_name="Peer",
            last_name="Identity",
        )
        create_work_relationship(
            organization=self.organization,
            actor=self.actor,
            person=peer_person,
            employee_number="PEER",
            effective_start=self.relationship.effective_start,
            legacy_employee=self.peer,
        )
        native_create = source.create_leave_mission_request

        def switch(**kwargs):
            record = native_create(**kwargs)
            Person.objects.filter(pk=self.relationship.person_id).update(user=None)
            Person.objects.filter(pk=peer_person.pk).update(user=self.employee_user)
            return record

        with (
            patch.object(source, "create_leave_mission_request", side_effect=switch),
            self.assertRaises(PermissionDenied),
        ):
            self.create()
        self.assertFalse(LeaveMissionRequest.objects.filter(kind="mission").exists())
        self.assertEqual(
            Person.objects.get(pk=self.relationship.person_id).user_id,
            self.employee_user.pk,
        )

    def test_approved_request_does_not_activate_unapproved_monetary_policy(self):
        record = self.approve(self.create())
        self.assertEqual(record.state, "approved")
        with self.assertRaisesMessage(
            ValidationError, "APPROVED_MISSION_POLICY_REQUIRED"
        ):
            routing.route_mission_effect(
                organization=self.organization,
                actor=self.actor,
                mission_id=record.pk,
                effect_id=uuid4(),
                effect_type="unknown",
                reason="No monetary policy",
            )
        self.assertFalse(MissionEffect.objects.exists())
        page = self.client_for().get(self.url("detail", record))
        self.assertNotContains(page, "PRIVATE-SYNTHETIC-POLICY")
        self.assertNotContains(page, "PRIVATE-REVIEWER-DETAIL")
        self.assertContains(page, "ارجاع مالی ثبت نشده است")
        self.capture("approved", page)

    def test_own_routing_link_is_projection_only_and_hides_financial_reviewer_data(
        self,
    ):
        record = self.approve(self.create(project=self.project))
        owner = self.organization.memberships.get(user=self.actor)
        for assignment in owner.role_assignments.all():
            assignment.role.permissions.add(
                BusinessPermission.objects.get(code=P.EXPENSES_CREATE)
            )
        PlatformExpenseGroup.objects.get_or_create(
            code="other", defaults={"name": "Other synthetic fixture"}
        )
        effect_id = uuid4()
        plan = routing.MissionPlan(
            "synthetic-approved-v1",
            "Synthetic approved integration only",
            (
                routing.EffectSpec(
                    effect_id,
                    "synthetic-direct",
                    "expense",
                    Decimal("12.00"),
                    "IRR",
                    routing.ExpenseTarget(
                        "other", record.starts_at.date(), "PRIVATE-TARGET-METADATA"
                    ),
                ),
            ),
        )
        with patch.object(
            routing,
            "POLICIES",
            {
                (
                    str(self.organization.pk),
                    record.policy_reference,
                ): routing.MissionPolicyBinding(lambda **kw: plan)
            },
        ):
            effect = routing.route_mission_effect(
                organization=self.organization,
                actor=self.actor,
                mission_id=record.pk,
                effect_id=effect_id,
                effect_type="synthetic-direct",
                reason="Synthetic governed source routing",
            )
        models = (
            Expense,
            PaymentRequest,
            TreasuryMovement,
            JournalEntry,
            MissionEffect,
        )
        before = [m.objects.count() for m in models]
        response = self.client_for().get(self.url("detail", record))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "بازپرداخت هزینه")
        for private in (
            "PRIVATE-TARGET-METADATA",
            "PRIVATE-REVIEWER-DETAIL",
            effect.identity_hash,
            str(effect.expense_target_id),
        ):
            self.assertNotContains(response, private)
        self.assertEqual(before, [m.objects.count() for m in models])
        self.capture("routed", response)
        Path("docs/governance/cep/evidence/CEP-068_MISSION_LINK_TRACE.json").write_text(
            json.dumps(
                {
                    "synthetic_policy_only": True,
                    "mission": str(record.pk),
                    "effect": str(effect.pk),
                    "native_target_type": "Expense draft",
                    "native_target": str(effect.expense_target_id),
                    "own_status": service.own_mission_routing_status(
                        actor=self.employee_user,
                        organization=self.organization,
                        record_id=record.pk,
                    ),
                    "GET_projection_counts_before": before,
                    "GET_projection_counts_after": [m.objects.count() for m in models],
                    "ESS_called_financial_routing": False,
                    "monetary_activation": False,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
