"""Independent overtime ESS proofs; Mission/financial activation stays unavailable."""

import os
import re
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.organizations.models import (
    BusinessPermission,
    MembershipScopeGrant,
    OrganizationMembership,
)
from apps.organizations.models import BusinessPermissionCode as P
from apps.timekeeping import services as source
from apps.timekeeping.models import OvertimeRequest, RequestState
from core.jalali import format_jalali

from . import ess_timekeeping as service
from . import test_cep063 as fixture
from .models import WorkRelationship


class ESSOvertimeTests(TestCase):
    client_for = fixture.ESSTimekeepingTests.client_for

    def setUp(self):
        fixture.ESSTimekeepingTests.setUp(self)
        self.role.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=[P.OVERTIME_VIEW, P.OVERTIME_REQUEST, P.OVERTIME_REVIEW]
            )
        )
        self.start = timezone.now().replace(second=0, microsecond=0) + timedelta(days=2)

    def create(self, **changes):
        return service.create_own_overtime(
            **{
                "actor": self.employee_user,
                "organization": self.organization,
                "starts_at": self.start,
                "ends_at": self.start + timedelta(hours=2),
                "reason": "درخواست آزمایشی اضافه‌کاری",
                **changes,
            }
        )

    def url(self, name, record=None, kind="overtime"):
        args = [kind] + ([record.pk] if record else [])
        return reverse("workforce:ess_timekeeping_" + name, args=args)

    def capture(self, name, response):
        directory = os.environ.get("BONIRA_CEP068_CAPTURE_DIR")
        if directory:
            body = re.sub(
                rb'name="csrfmiddlewaretoken" value="[^"]+"',
                b'name="csrfmiddlewaretoken" value="SYNTHETIC-EVIDENCE"',
                response.content,
            )
            Path(directory, name + ".html").write_bytes(body)

    def test_source_create_submit_status_and_identity_audit_remain_atomic(self):
        record = self.create()
        self.assertEqual(record.employee_id, self.employee.pk)
        self.assertEqual(record.state, RequestState.DRAFT)
        self.assertEqual(record.policy_reference, "")
        result = service.submit_own(
            actor=self.employee_user,
            organization=self.organization,
            kind="overtime",
            record_id=record.pk,
        )
        self.assertEqual(result.state, RequestState.SUBMITTED)
        events = AuditEvent.objects.filter(
            entity_id=str(record.pk), metadata__origin="ess_overtime"
        )
        self.assertEqual(events.count(), 2)
        self.assertTrue(
            all(
                event.metadata["relationship_id"] == str(self.relationship.pk)
                and event.metadata["person_id"] == str(self.relationship.person_id)
                for event in events
            )
        )
        self.assertEqual(
            service.own_record(
                actor=self.employee_user,
                organization=self.organization,
                kind="overtime",
                record_id=record.pk,
            ).pk,
            record.pk,
        )
        with self.assertRaises(PermissionDenied):
            service.submit_own(
                actor=self.employee_user,
                organization=self.organization,
                kind="overtime",
                record_id=record.pk,
            )
        self.assertEqual(OvertimeRequest.objects.count(), 1)
        with self.assertRaises(PermissionDenied):
            source.review_time_request(
                organization=self.organization,
                actor=self.employee_user,
                request=result,
                approve=True,
                reason="No self approval",
            )

    def test_audit_failure_rolls_back_source_create_and_submit(self):
        with (
            patch.object(
                service, "record_audit_event", side_effect=ValidationError("audit")
            ),
            self.assertRaises(ValidationError),
        ):
            self.create()
        self.assertEqual(OvertimeRequest.objects.count(), 0)
        record = self.create()
        with (
            patch.object(
                service, "record_audit_event", side_effect=ValidationError("audit")
            ),
            self.assertRaises(ValidationError),
        ):
            service.submit_own(
                actor=self.employee_user,
                organization=self.organization,
                kind="overtime",
                record_id=record.pk,
            )
        record.refresh_from_db()
        self.assertEqual(record.state, RequestState.DRAFT)

    def test_current_identity_episode_bounds_and_overlap_remain_source_validated(self):
        for changes in (
            {"ends_at": self.start},
            {"starts_at": self.start.replace(tzinfo=None)},
            {"starts_at": self.start.replace(year=2024)},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.create(**changes)
        self.create()
        with self.assertRaises(ValidationError):
            self.create()
        WorkRelationship.objects.filter(pk=self.relationship.pk).update(
            effective_end=timezone.localdate() + timedelta(days=1)
        )
        with self.assertRaises(ValidationError):
            self.create(
                starts_at=self.start + timedelta(days=1),
                ends_at=self.start + timedelta(days=1, hours=2),
            )

    def test_missing_explicit_identity_and_removed_membership_or_permission_deny(self):
        person = self.relationship.person
        person.user = None
        person.save()
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
            BusinessPermission.objects.get(code=P.OVERTIME_REQUEST)
        )
        with self.assertRaises(PermissionDenied):
            self.create()

    def test_own_source_filter_and_missing_or_foreign_urls_have_same_denial(self):
        record = self.create()
        peer = OvertimeRequest.objects.create(
            organization=self.organization,
            employee=self.peer,
            starts_at=self.start,
            ends_at=self.start + timedelta(hours=2),
            requested_by=self.actor,
            reason="PEER-PRIVATE-REASON",
        )
        client = self.client_for()
        allowed = client.get(self.url("detail", record))
        self.assertEqual(allowed.status_code, 200)
        denied = client.get(self.url("detail", peer))
        missing = client.get(
            reverse("workforce:ess_timekeeping_detail", args=["overtime", uuid4()])
        )
        self.assertEqual(denied.status_code, 403)

        def normalize(body):
            body = re.sub(rb'name="csrfmiddlewaretoken" value="[^"]+"', b"CSRF", body)
            # Shared navigation retains the current request path in both cases.
            return re.sub(rb"overtime/[0-9a-f-]{36}/", b"overtime/REQUEST/", body)

        self.assertEqual(normalize(denied.content), normalize(missing.content))
        self.assertNotContains(denied, "PEER-PRIVATE-REASON", status_code=403)
        self.assertEqual(client.post(self.url("submit", peer)).status_code, 403)
        self.capture("denied", denied)

    def test_project_scope_intersection_applies_to_source_reads_and_creation(self):
        record = self.create()
        membership = OrganizationMembership.objects.get(
            user=self.employee_user, organization=self.organization
        )
        MembershipScopeGrant.objects.filter(membership=membership).delete()
        with self.assertRaises(PermissionDenied):
            service.own_rows(
                actor=self.employee_user,
                organization=self.organization,
                kind="overtime",
            )
        with self.assertRaises(PermissionDenied):
            service.own_record(
                actor=self.employee_user,
                organization=self.organization,
                kind="overtime",
                record_id=record.pk,
            )
        with self.assertRaises(PermissionDenied):
            self.create(
                starts_at=self.start + timedelta(days=2),
                ends_at=self.start + timedelta(days=2, hours=1),
            )

    def test_prior_episode_source_is_not_exposed_under_current_relationship(self):
        old = OvertimeRequest.objects.create(
            organization=self.organization,
            employee=self.employee,
            starts_at=self.start.replace(year=2024),
            ends_at=(self.start + timedelta(hours=1)).replace(year=2024),
            requested_by=self.employee_user,
            reason="OLD-EPISODE",
        )
        with self.assertRaises(PermissionDenied):
            service.own_record(
                actor=self.employee_user,
                organization=self.organization,
                kind="overtime",
                record_id=old.pk,
            )

    def test_jalali_form_create_detail_empty_and_error_states(self):
        client = self.client_for()
        response = client.get(reverse("workforce:ess_timekeeping"))
        self.assertContains(response, "درخواست‌های اضافه‌کاری من")
        self.capture("empty", response)
        response = client.get(self.url("create"))
        self.assertContains(response, 'data-jalali-date="datetime"')
        self.assertContains(response, 'dir="rtl"')
        for field in ["employee", "organization", "policy_reference", "rate", "amount"]:
            self.assertNotContains(response, 'name="' + field + '"')
        self.capture("form", response)
        data = {
            "starts_at": format_jalali(
                timezone.localtime(self.start), include_time=True
            ),
            "ends_at": format_jalali(
                timezone.localtime(self.start + timedelta(hours=2)), include_time=True
            ),
            "reason": "متن درخواست شخصی آزمایشی",
        }
        response = client.post(self.url("create"), data)
        self.assertEqual(response.status_code, 302)
        record = OvertimeRequest.objects.get()
        response = client.get(response.url)
        self.assertContains(response, "متن درخواست شخصی آزمایشی")
        self.assertContains(response, "پیش‌نویس")
        self.capture("draft", response)
        response = client.post(self.url("submit", record))
        self.assertEqual(response.status_code, 302)
        response = client.get(response.url)
        self.assertContains(response, "ارسال‌شده")
        self.capture("submitted", response)
        response = client.post(
            self.url("create"), {**data, "ends_at": data["starts_at"]}
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(
            response, "پایان اضافه‌کاری باید پس از شروع باشد", status_code=400
        )
        self.capture("error", response)

    def test_forged_identity_policy_financial_values_and_csrf_are_denied(self):
        client = self.client_for()
        data = {
            "starts_at": format_jalali(
                timezone.localtime(self.start), include_time=True
            ),
            "ends_at": format_jalali(
                timezone.localtime(self.start + timedelta(hours=2)), include_time=True
            ),
            "reason": "آزمایشی",
        }
        for key in [
            "employee_id",
            "organization_id",
            "relationship_id",
            "policy_reference",
            "amount",
            "state",
        ]:
            with self.subTest(key=key):
                self.assertEqual(
                    client.post(
                        self.url("create"), {**data, key: str(uuid4())}
                    ).status_code,
                    400,
                )
        self.assertEqual(OvertimeRequest.objects.count(), 0)
        self.assertEqual(
            self.client_for(csrf=True).post(self.url("create"), data).status_code, 403
        )

    def test_mission_create_read_submit_stay_unavailable(self):
        client = self.client_for()
        self.assertEqual(
            client.get(self.url("create", kind="mission")).status_code, 403
        )
        self.assertEqual(
            client.get(
                reverse("workforce:ess_timekeeping_detail", args=["mission", uuid4()])
            ).status_code,
            403,
        )
        self.assertEqual(
            client.post(
                reverse("workforce:ess_timekeeping_submit", args=["mission", uuid4()])
            ).status_code,
            403,
        )

    def test_foreign_tenant_context_and_period_scope_fail_closed(self):
        with self.assertRaises(PermissionDenied):
            service.create_own_overtime(
                actor=self.employee_user,
                organization=self.other,
                starts_at=self.start,
                ends_at=self.start + timedelta(hours=1),
                reason="Not authorized in foreign tenant",
            )
        with self.assertRaises(PermissionDenied):
            service.own_record(
                actor=self.employee_user,
                organization=self.other,
                kind="overtime",
                record_id=uuid4(),
            )
