from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256
from tempfile import TemporaryDirectory
from uuid import uuid4

from django.apps import apps
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.documents.models import (
    Document,
    DocumentConfidentiality,
    DocumentType,
    DocumentVersion,
)
from apps.organizations.models import (
    BusinessPermission,
    BusinessPermissionCode,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    OrganizationSettings,
    PlatformRoleAssignment,
    PlatformRoleCode,
)
from apps.organizations.services import set_active_organization
from apps.projects.models import Project
from apps.support.forms import SupportEvidenceForm
from apps.support.models import (
    SupportAccessRequest,
    SupportCase,
    SupportCaseEvent,
    SupportEvidence,
)
from apps.support.services import (
    acknowledge_notification,
    assign_case,
    calendar_projection,
    confirm_access,
    create_case,
    create_notification,
    link_evidence,
    request_access,
    revoke_access,
    transition_case,
    validate_access,
)

SUPPORT_PERMISSION_CODES = tuple(
    code for code in BusinessPermissionCode.values if code.startswith("support.")
)


class SupportP9S16S20Tests(TestCase):
    def setUp(self) -> None:
        self.storage_directory = TemporaryDirectory()
        self.storage_override = override_settings(
            DOCUMENT_PROTECTED_ROOT=self.storage_directory.name
        )
        self.storage_override.enable()
        self.addCleanup(self.storage_override.disable)
        self.addCleanup(self.storage_directory.cleanup)

        self.operator = User.objects.create_user(username="support-operator")
        self.recipient = User.objects.create_user(username="support-recipient")
        self.assignee = User.objects.create_user(username="support-assignee")
        self.confirmer = User.objects.create_user(username="support-confirmer")
        self.approver = User.objects.create_user(username="support-approver")
        self.unprivileged = User.objects.create_user(username="support-unprivileged")
        self.platform_admin = User.objects.create_user(username="support-platform")
        self.other_actor = User.objects.create_user(username="support-other")

        self.organization = Organization.objects.create(
            name="P9 Support", slug="p9-support", created_by=self.operator
        )
        self.other_organization = Organization.objects.create(
            name="Other P9 Support",
            slug="other-p9-support",
            created_by=self.other_actor,
        )
        OrganizationSettings.objects.create(organization=self.organization)
        OrganizationSettings.objects.create(organization=self.other_organization)

        self.support_role = OrganizationRole.objects.create(
            code="p9_support_operator", name="کاربر پشتیبانی P9"
        )
        self.support_role.permissions.add(
            *BusinessPermission.objects.filter(code__in=SUPPORT_PERMISSION_CODES)
        )
        for user in (
            self.operator,
            self.recipient,
            self.assignee,
            self.confirmer,
            self.approver,
        ):
            OrganizationMembership.objects.create(
                organization=self.organization,
                user=user,
                role_definition=self.support_role,
                status=MembershipStatus.ACTIVE,
            )
        self.empty_role = OrganizationRole.objects.create(
            code="p9_support_named_only", name="Platform Admin"
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.unprivileged,
            role_definition=self.empty_role,
            status=MembershipStatus.ACTIVE,
        )
        OrganizationMembership.objects.create(
            organization=self.other_organization,
            user=self.other_actor,
            role_definition=self.support_role,
            status=MembershipStatus.ACTIVE,
        )
        PlatformRoleAssignment.objects.create(
            user=self.platform_admin,
            role=PlatformRoleCode.PLATFORM_ADMIN,
            assigned_by=self.operator,
            approved_by=self.approver,
            reason="Focused P9 isolation test",
        )
        self.project = Project.objects.create(
            organization=self.organization, code="P9-S", name="Support source project"
        )

    def _case(self, *, actor=None, organization=None, summary="درخواست آزمون"):
        return create_case(
            organization=organization or self.organization,
            requester=actor or self.operator,
            category="general",
            summary=summary,
            operation_key=uuid4(),
        )

    def _document(
        self, *, organization=None, confidentiality="internal", title="شاهد پشتیبانی"
    ):
        organization = organization or self.organization
        actor = self.operator if organization == self.organization else self.other_actor
        payload = f"support evidence {uuid4()}".encode()
        document = Document.objects.create(
            organization=organization,
            document_number=f"SUP-{uuid4().hex[:12]}",
            document_type=DocumentType.GENERAL,
            confidentiality=confidentiality,
            title=title,
            created_by=actor,
            updated_by=actor,
        )
        version = DocumentVersion.objects.create(
            organization=organization,
            document=document,
            version_number=1,
            original_file_name="evidence.txt",
            file=SimpleUploadedFile("evidence.txt", payload, content_type="text/plain"),
            content_type="text/plain",
            file_size=len(payload),
            sha256=sha256(payload).hexdigest(),
            uploaded_by=actor,
        )
        Document.objects.filter(pk=document.pk).update(current_version=version)
        return document, version

    def _login(self, user, organization=None):
        self.client.force_login(user)
        set_active_organization(self.client.session, organization or self.organization)

    def test_permission_catalog_default_deny_and_platform_role_is_not_tenant_access(
        self,
    ):
        self.assertSetEqual(
            set(
                BusinessPermission.objects.filter(
                    code__in=SUPPORT_PERMISSION_CODES
                ).values_list("code", flat=True)
            ),
            set(SUPPORT_PERMISSION_CODES),
        )
        with self.assertRaises(PermissionDenied):
            create_case(
                organization=self.organization,
                requester=self.unprivileged,
                category="general",
                summary="denied",
            )
        with self.assertRaises(PermissionDenied):
            create_case(
                organization=self.organization,
                requester=self.platform_admin,
                category="general",
                summary="platform role is not membership",
            )

    def test_notification_lineage_deduplication_recipient_ack_and_tenant_isolation(
        self,
    ):
        source_id = self._case().pk
        notification = create_notification(
            organization=self.organization,
            actor=self.operator,
            recipient=self.recipient,
            source_type="support_case",
            source_id=source_id,
            source_version="7",
            category="case_update",
            summary="وضعیت درخواست تغییر کرد",
            operation_key=uuid4(),
        )
        duplicate = create_notification(
            organization=self.organization,
            actor=self.operator,
            recipient=self.recipient,
            source_type="support_case",
            source_id=source_id,
            source_version="7",
            category="case_update",
            summary="وضعیت درخواست تغییر کرد",
            operation_key=uuid4(),
        )
        self.assertEqual(notification.pk, duplicate.pk)
        self.assertEqual(notification.source_id, source_id)
        with self.assertRaises(PermissionDenied):
            acknowledge_notification(
                organization=self.organization,
                actor=self.operator,
                notification_id=notification.pk,
            )
        with self.assertRaises(PermissionDenied):
            acknowledge_notification(
                organization=self.other_organization,
                actor=self.other_actor,
                notification_id=notification.pk,
            )
        acknowledged = acknowledge_notification(
            organization=self.organization,
            actor=self.recipient,
            notification_id=notification.pk,
        )
        read_at = acknowledged.read_at
        acknowledged = acknowledge_notification(
            organization=self.organization,
            actor=self.recipient,
            notification_id=notification.pk,
        )
        self.assertEqual(acknowledged.read_at, read_at)
        self.assertEqual(acknowledged.status, "read")
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.SUPPORT_NOTIFICATION_ACKNOWLEDGED,
                entity_id=str(notification.pk),
            ).exists()
        )

    def test_calendar_is_read_derived_tenant_filtered_and_permission_guarded(self):
        case = self._case()
        other_case = self._case(
            actor=self.other_actor,
            organization=self.other_organization,
            summary="other tenant",
        )
        rows = calendar_projection(organization=self.organization, actor=self.operator)
        self.assertEqual([row["source_id"] for row in rows], [case.pk])
        self.assertEqual(rows[0]["status"], case.status)
        self.assertNotIn("deadline", rows[0])
        self.assertNotIn(other_case.pk, {row["source_id"] for row in rows})
        self.assertFalse(
            any(
                model._meta.app_label == "support"
                and model._meta.model_name.startswith("calendar")
                for model in apps.get_models()
            )
        )
        with self.assertRaises(PermissionDenied):
            calendar_projection(organization=self.organization, actor=self.unprivileged)

    def test_case_assignment_lifecycle_stale_state_and_immutable_history(self):
        case = self._case()
        assigned = assign_case(
            organization=self.organization,
            actor=self.operator,
            case_id=case.pk,
            assignee=self.assignee,
            expected_status="open",
        )
        self.assertEqual(assigned.assignee, self.assignee)
        with self.assertRaises(ValidationError):
            assign_case(
                organization=self.organization,
                actor=self.operator,
                case_id=case.pk,
                assignee=self.other_actor,
                expected_status="open",
            )
        for expected, target in (
            ("open", "triaged"),
            ("triaged", "in_progress"),
            ("in_progress", "resolved"),
            ("resolved", "closed"),
            ("closed", "open"),
        ):
            case = transition_case(
                organization=self.organization,
                actor=self.operator,
                case_id=case.pk,
                expected_status=expected,
                to_status=target,
                comment=f"{expected} to {target}",
                operation_key=uuid4(),
            )
        self.assertEqual(case.status, "open")
        self.assertEqual(case.events.count(), 5)
        with self.assertRaises(ValidationError):
            transition_case(
                organization=self.organization,
                actor=self.operator,
                case_id=case.pk,
                expected_status="closed",
                to_status="open",
                operation_key=uuid4(),
            )
        with self.assertRaises(ValidationError):
            transition_case(
                organization=self.organization,
                actor=self.operator,
                case_id=case.pk,
                expected_status="open",
                to_status="resolved",
                operation_key=uuid4(),
            )
        event = case.events.first()
        event.comment = "silent rewrite"
        with self.assertRaises(ValidationError):
            event.save()
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.SUPPORT_CASE_ASSIGNED,
                entity_id=str(case.pk),
            ).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.SUPPORT_CASE_CREATED,
                entity_id=str(case.pk),
            ).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.SUPPORT_CASE_TRANSITIONED,
                entity_id=str(case.pk),
            ).exists()
        )

    def test_transition_operation_key_is_idempotent(self):
        case = self._case()
        operation_key = uuid4()
        case = transition_case(
            organization=self.organization,
            actor=self.operator,
            case_id=case.pk,
            expected_status="open",
            to_status="triaged",
            operation_key=operation_key,
        )
        replay = transition_case(
            organization=self.organization,
            actor=self.operator,
            case_id=case.pk,
            expected_status="open",
            to_status="triaged",
            operation_key=operation_key,
        )
        self.assertEqual(replay.pk, case.pk)
        self.assertEqual(replay.events.count(), 1)

    def test_dms_exact_pin_tenant_sensitive_permission_and_no_byte_copy(self):
        case = self._case()
        document, version = self._document()
        evidence = link_evidence(
            organization=self.organization,
            actor=self.operator,
            case_id=case.pk,
            document_version=version,
        )
        self.assertEqual(evidence.document_id, document.pk)
        self.assertEqual(evidence.document_version_id, version.pk)
        self.assertEqual(evidence.sha256, version.sha256)
        self.assertFalse(
            any(
                field.__class__.__name__ == "FileField"
                for field in SupportEvidence._meta.fields
            )
        )
        _, other_version = self._document(organization=self.other_organization)
        with self.assertRaises(PermissionDenied):
            link_evidence(
                organization=self.organization,
                actor=self.operator,
                case_id=case.pk,
                document_version=other_version,
            )

        second_document, second_version = self._document(title="شاهد دوم")
        mismatched_form = SupportEvidenceForm(
            {"document": document.pk, "document_version": second_version.pk},
            organization=self.organization,
            can_view_sensitive=True,
        )
        self.assertFalse(mismatched_form.is_valid())
        self.assertEqual(second_version.document_id, second_document.pk)

        limited_role = OrganizationRole.objects.create(
            code="p9_support_evidence_limited", name="پیوند شاهد عادی"
        )
        limited_role.permissions.add(
            BusinessPermission.objects.get(
                code=BusinessPermissionCode.SUPPORT_EVIDENCE_LINK
            ),
            BusinessPermission.objects.get(
                code=BusinessPermissionCode.SUPPORT_CASE_VIEW
            ),
        )
        limited = User.objects.create_user(username="support-evidence-limited")
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=limited,
            role_definition=limited_role,
            status=MembershipStatus.ACTIVE,
        )
        _, sensitive_version = self._document(
            confidentiality=DocumentConfidentiality.RESTRICTED,
            title="شاهد بسیار محدود",
        )
        with self.assertRaises(PermissionDenied):
            link_evidence(
                organization=self.organization,
                actor=limited,
                case_id=case.pk,
                document_version=sensitive_version,
            )
        sensitive_evidence = link_evidence(
            organization=self.organization,
            actor=self.operator,
            case_id=case.pk,
            document_version=sensitive_version,
        )
        self._login(limited)
        response = self.client.get(reverse("support:case_detail", args=[case.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, sensitive_version.sha256)
        evidence.sha256 = "0" * 64
        with self.assertRaises(ValidationError):
            evidence.save()
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.SUPPORT_EVIDENCE_LINKED,
                entity_id=str(sensitive_evidence.pk),
            ).exists()
        )

    def test_support_access_sod_scope_expiry_revocation_and_audit(self):
        access = request_access(
            organization=self.organization,
            actor=self.operator,
            purpose="diagnose-case",
            scope="case:read",
            expires_at=timezone.now() + timedelta(hours=1),
            operation_key=uuid4(),
        )
        with self.assertRaises(PermissionDenied):
            confirm_access(
                organization=self.organization,
                actor=self.operator,
                request_id=access.pk,
            )
        with self.assertRaises(ValidationError):
            confirm_access(
                organization=self.organization,
                actor=self.approver,
                request_id=access.pk,
                platform=True,
            )
        access = confirm_access(
            organization=self.organization,
            actor=self.confirmer,
            request_id=access.pk,
        )
        with self.assertRaises(PermissionDenied):
            confirm_access(
                organization=self.organization,
                actor=self.confirmer,
                request_id=access.pk,
                platform=True,
            )
        access = confirm_access(
            organization=self.organization,
            actor=self.approver,
            request_id=access.pk,
            platform=True,
        )
        self.assertEqual(access.status, "active")
        with self.assertRaises(PermissionDenied):
            validate_access(
                organization=self.organization,
                actor=self.operator,
                request_id=access.pk,
                purpose="wrong-purpose",
                scope="case:read",
            )
        with self.assertRaises(PermissionDenied):
            validate_access(
                organization=self.organization,
                actor=self.operator,
                request_id=access.pk,
                purpose="diagnose-case",
                scope="case:write",
            )
        with self.assertRaises(PermissionDenied):
            validate_access(
                organization=self.organization,
                actor=self.recipient,
                request_id=access.pk,
                purpose="diagnose-case",
                scope="case:read",
            )
        validate_access(
            organization=self.organization,
            actor=self.operator,
            request_id=access.pk,
            purpose="diagnose-case",
            scope="case:read",
        )
        access = revoke_access(
            organization=self.organization,
            actor=self.confirmer,
            request_id=access.pk,
        )
        self.assertEqual(access.status, "revoked")
        self.assertEqual(
            revoke_access(
                organization=self.organization,
                actor=self.confirmer,
                request_id=access.pk,
            ).status,
            "revoked",
        )
        with self.assertRaises(PermissionDenied):
            validate_access(
                organization=self.organization,
                actor=self.operator,
                request_id=access.pk,
                purpose="diagnose-case",
                scope="case:read",
            )
        actions = set(
            AuditEvent.objects.filter(entity_id=str(access.pk)).values_list(
                "action", flat=True
            )
        )
        self.assertTrue(
            {
                AuditAction.SUPPORT_ACCESS_REQUESTED,
                AuditAction.SUPPORT_ACCESS_CONFIRMED,
                AuditAction.SUPPORT_ACCESS_APPROVED,
                AuditAction.SUPPORT_ACCESS_USED,
                AuditAction.SUPPORT_ACCESS_REVOKED,
            }.issubset(actions)
        )

    def test_expired_access_and_stale_approval_fail_closed(self):
        access = request_access(
            organization=self.organization,
            actor=self.operator,
            purpose="diagnose",
            scope="case:read",
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        confirm_access(
            organization=self.organization,
            actor=self.confirmer,
            request_id=access.pk,
        )
        with self.assertRaises(ValidationError):
            confirm_access(
                organization=self.organization,
                actor=self.approver,
                request_id=access.pk,
            )
        confirm_access(
            organization=self.organization,
            actor=self.approver,
            request_id=access.pk,
            platform=True,
        )
        SupportAccessRequest.objects.filter(pk=access.pk).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        with self.assertRaises(PermissionDenied):
            validate_access(
                organization=self.organization,
                actor=self.operator,
                request_id=access.pk,
                purpose="diagnose",
                scope="case:read",
            )

    def test_request_routes_rtl_jalali_permissions_and_safe_cross_tenant_detail(self):
        case = self._case()
        notification = create_notification(
            organization=self.organization,
            actor=self.operator,
            recipient=self.operator,
            source_type="support_case",
            source_id=case.pk,
            source_version="1",
            category="case",
            summary="اعلان آزمون",
        )
        self._login(self.operator)
        for name in ("notifications", "calendar", "cases", "access"):
            response = self.client.get(reverse(f"support:{name}"))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'dir="rtl"')
        detail = self.client.get(reverse("support:case_detail", args=[case.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "زمان ثبت")
        self.assertContains(detail, "درخواست‌های پشتیبانی")
        other_case = self._case(
            actor=self.other_actor, organization=self.other_organization
        )
        self.assertEqual(
            self.client.get(
                reverse("support:case_detail", args=[other_case.pk])
            ).status_code,
            404,
        )
        mutation_urls = (
            reverse("support:acknowledge", args=[notification.pk]),
            reverse("support:case_create"),
            reverse("support:case_assign", args=[case.pk]),
            reverse("support:case_transition", args=[case.pk]),
            reverse("support:case_evidence", args=[case.pk]),
            reverse("support:access_request"),
            reverse("support:access_confirm", args=[uuid4()]),
            reverse("support:access_approve", args=[uuid4()]),
            reverse("support:access_revoke", args=[uuid4()]),
        )
        for url in mutation_urls:
            self.assertEqual(self.client.get(url).status_code, 405)

        self.assertEqual(
            self.client.post(
                reverse("support:acknowledge", args=[notification.pk])
            ).status_code,
            302,
        )
        case_count = SupportCase.objects.count()
        self.assertEqual(
            self.client.post(
                reverse("support:case_create"),
                {"category": "route", "summary": "درخواست مسیر"},
            ).status_code,
            302,
        )
        self.assertEqual(SupportCase.objects.count(), case_count + 1)
        route_case = SupportCase.objects.get(summary="درخواست مسیر")
        self.assertEqual(
            self.client.post(
                reverse("support:case_assign", args=[route_case.pk]),
                {"assignee": self.assignee.pk, "expected_status": "open"},
            ).status_code,
            302,
        )
        self.assertEqual(
            self.client.post(
                reverse("support:case_transition", args=[route_case.pk]),
                {
                    "to_status": "triaged",
                    "comment": "بررسی مسیر",
                    "expected_status": "open",
                },
            ).status_code,
            302,
        )
        document, version = self._document(title="شاهد مسیر")
        self.assertEqual(
            self.client.post(
                reverse("support:case_evidence", args=[route_case.pk]),
                {"document": document.pk, "document_version": version.pk},
            ).status_code,
            302,
        )
        self.assertEqual(
            self.client.post(
                reverse("support:access_request"),
                {
                    "purpose": "route-check",
                    "scope": "case:read",
                    "expires_at": (timezone.now() + timedelta(hours=1)).isoformat(),
                },
            ).status_code,
            302,
        )
        access = SupportAccessRequest.objects.get(purpose="route-check")
        self._login(self.confirmer)
        self.assertEqual(
            self.client.post(
                reverse("support:access_confirm", args=[access.pk])
            ).status_code,
            302,
        )
        self._login(self.approver)
        self.assertEqual(
            self.client.post(
                reverse("support:access_approve", args=[access.pk])
            ).status_code,
            302,
        )
        self._login(self.confirmer)
        self.assertEqual(
            self.client.post(
                reverse("support:access_revoke", args=[access.pk])
            ).status_code,
            302,
        )

        self._login(self.unprivileged)
        for name in ("notifications", "calendar", "cases", "access"):
            self.assertEqual(
                self.client.get(reverse(f"support:{name}")).status_code, 403
            )
        self.assertEqual(
            self.client.post(
                reverse("support:case_create"),
                {"category": "denied", "summary": "denied"},
            ).status_code,
            403,
        )

    def test_support_workflows_have_no_downstream_effects(self):
        downstream_labels = {
            "accounting",
            "billing",
            "contracts",
            "equipment",
            "expenses",
            "fixed_assets",
            "inventory",
            "payments",
            "payroll",
            "procurement",
            "subledgers",
            "treasury",
        }

        def counts():
            return {
                model._meta.label_lower: model.objects.count()
                for model in apps.get_models()
                if model._meta.app_label in downstream_labels
                and model._meta.managed
                and not model._meta.proxy
            }

        before = counts()
        project_name = self.project.name
        case = self._case()
        transition_case(
            organization=self.organization,
            actor=self.operator,
            case_id=case.pk,
            expected_status="open",
            to_status="triaged",
            operation_key=uuid4(),
        )
        access = request_access(
            organization=self.organization,
            actor=self.operator,
            purpose="read-only diagnostic",
            scope="case:read",
            expires_at=timezone.now() + timedelta(hours=1),
        )
        confirm_access(
            organization=self.organization,
            actor=self.confirmer,
            request_id=access.pk,
        )
        confirm_access(
            organization=self.organization,
            actor=self.approver,
            request_id=access.pk,
            platform=True,
        )
        self.project.refresh_from_db()
        self.assertEqual(self.project.name, project_name)
        self.assertDictEqual(counts(), before)


class SupportP9ConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self) -> None:
        self.actor = User.objects.create_user(username="support-race-actor")
        self.organization = Organization.objects.create(
            name="P9 Support Race", slug="p9-support-race", created_by=self.actor
        )
        OrganizationSettings.objects.create(organization=self.organization)
        role = OrganizationRole.objects.create(
            code="p9_support_race", name="کاربر رقابت پشتیبانی"
        )
        role.permissions.add(
            BusinessPermission.objects.get(
                code=BusinessPermissionCode.SUPPORT_CASE_CREATE
            ),
            BusinessPermission.objects.get(
                code=BusinessPermissionCode.SUPPORT_CASE_UPDATE
            ),
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.actor,
            role_definition=role,
            status=MembershipStatus.ACTIVE,
        )
        self.case = create_case(
            organization=self.organization,
            requester=self.actor,
            category="race",
            summary="concurrent transition",
        )

    def test_concurrent_transition_has_one_winner_and_one_stale_rejection(self):
        def transition(operation_key):
            close_old_connections()
            try:
                transition_case(
                    organization=Organization.objects.get(pk=self.organization.pk),
                    actor=User.objects.get(pk=self.actor.pk),
                    case_id=self.case.pk,
                    expected_status="open",
                    to_status="triaged",
                    operation_key=operation_key,
                )
            except ValidationError:
                return "stale"
            finally:
                close_old_connections()
            return "success"

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(transition, (uuid4(), uuid4())))
        self.assertCountEqual(results, ["success", "stale"])
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, "triaged")
        self.assertEqual(SupportCaseEvent.objects.filter(case=self.case).count(), 1)
