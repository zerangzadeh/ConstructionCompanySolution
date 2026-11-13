"""B10 follow-up checks for supported, non-statutory Platform Admin contracts."""

from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.accounts.models import User
from apps.accounts.recovery import account_recovery_tokens
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.access_services import (
    assign_platform_admin,
    create_protected_operation_version,
)
from apps.organizations.models import PolicySourceBasis, ProtectedOperationCode
from apps.organizations.policy_services import (
    create_platform_policy,
    create_platform_policy_version,
    publish_platform_policy_version,
    record_optional_policy_review,
    retire_platform_policy_version,
    update_platform_policy_version,
)
from apps.organizations.policy_specs import PROJECT_BUDGET_RESPONSE_POLICY_CODE


@override_settings(PRODUCT_SURFACE_PROFILE="MVP")
class B10ValidationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        root = User.objects.create_superuser(username="b10-root")
        cls.admin = User.objects.create_user(username="b10-platform")
        assign_platform_admin(
            actor=root,
            approver=root,
            target=cls.admin,
            reason="B10 synthetic authority",
        )

    def draft(self, version=1, supersedes=None):
        policy = create_platform_policy(
            actor=self.admin,
            code=PROJECT_BUDGET_RESPONSE_POLICY_CODE,
            reason="B10 existing non-statutory contract",
        )
        return create_platform_policy_version(
            actor=self.admin,
            policy=policy,
            version=version,
            parameters={"response": "WARNING"},
            effective_from=timezone.localdate() + timedelta(days=version),
            source_basis=PolicySourceBasis.PRODUCT_DEFINED,
            supersedes=supersedes,
            reason="Synthetic isolated lifecycle",
        )

    def test_draft_editor_preserves_product_defined_source_basis(self):
        self.draft()
        self.client.force_login(self.admin)
        response = self.client.get(reverse("organizations:platform_policy_catalog"))
        self.assertIn(
            '<option value="product_defined" selected>محصول</option>',
            response.content.decode(),
        )

    def test_stale_policy_draft_form_cannot_overwrite_a_newer_edit(self):
        draft = self.draft()
        self.client.force_login(self.admin)
        url = reverse("organizations:platform_policy_catalog")
        payload = {
            "action": "update_version",
            "policy_version_id": draft.pk,
            "expected_updated_at": draft.updated_at.isoformat(),
            "parameters": '{"response":"HARD_STOP"}',
            "effective_from": draft.effective_from.isoformat(),
            "source_basis": PolicySourceBasis.PRODUCT_DEFINED,
            "reason": "Synthetic first editor",
        }
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        draft.refresh_from_db()
        self.assertEqual(draft.parameters, {"response": "HARD_STOP"})
        before = AuditEvent.objects.count()
        payload["parameters"] = '{"response":"WARNING"}'
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        draft.refresh_from_db()
        self.assertEqual(draft.parameters, {"response": "HARD_STOP"})
        self.assertEqual(AuditEvent.objects.count(), before)
        payload["action"] = "publish"
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        draft.refresh_from_db()
        self.assertEqual(draft.status, "draft")
        self.assertEqual(AuditEvent.objects.count(), before)

    def test_protected_retirement_replay_cannot_retire_the_previous_version(self):
        operation = create_protected_operation_version(
            actor=self.admin,
            code=ProtectedOperationCode.values[0],
            name="Synthetic current version",
            description="Retirement replay target",
            reason="B10 synthetic successor",
        )
        previous = operation.supersedes
        self.assertIsNotNone(previous)
        self.client.force_login(self.admin)
        url = reverse("organizations:protected_operation_catalog")
        payload = {
            "action": "retire",
            "code": operation.code,
            "operation_id": operation.pk,
            "reason": "Synthetic confirmation",
        }
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        operation.refresh_from_db()
        self.assertIsNotNone(operation.retired_at)
        self.client.post(url, payload)
        previous.refresh_from_db()
        self.assertIsNone(previous.retired_at)
        self.assertEqual(
            AuditEvent.objects.filter(
                action=AuditAction.PROTECTED_OPERATION_RETIRED
            ).count(),
            1,
        )

    def test_policy_history_stale_draft_and_retirement_are_audited(self):
        first = self.draft()
        record_optional_policy_review(
            actor=self.admin,
            policy_version=first,
            reviewer_identity="Synthetic independent reviewer",
            qualification_summary="Product contract test",
            independence_statement="Independent synthetic fixture",
            evidence_reference="B10 isolated non-statutory evidence",
            reviewed_on=timezone.localdate(),
            review_scope="Existing operational policy lifecycle",
            disposition="accepted",
        )
        published = publish_platform_policy_version(
            actor=self.admin, policy_version=first, reason="Synthetic publication"
        )
        before = AuditEvent.objects.count()
        with self.assertRaises(ValidationError) as error:
            update_platform_policy_version(
                actor=self.admin,
                policy_version=first,
                parameters={"response": "HARD_STOP"},
                effective_from=first.effective_from,
                source_basis=PolicySourceBasis.PRODUCT_DEFINED,
                reason="Stale draft replay",
            )
        self.assertIn("پیش‌نویس", error.exception.messages[0])
        self.assertEqual(AuditEvent.objects.count(), before)
        first.refresh_from_db()
        self.assertEqual(first.parameters, {"response": "WARNING"})
        second = self.draft(2, published)
        publish_platform_policy_version(
            actor=self.admin, policy_version=second, reason="Synthetic successor"
        )
        retire_platform_policy_version(
            actor=self.admin, policy_version=second, reason="Synthetic retirement"
        )
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, "published")
        self.assertEqual(first.published_at, published.published_at)
        self.assertEqual(second.status, "retired")
        self.assertEqual(second.supersedes_id, first.pk)
        event = AuditEvent.objects.get(
            action=AuditAction.PLATFORM_POLICY_VERSION_RETIRED,
            entity_id=str(second.pk),
        )
        self.assertEqual(event.actor, self.admin)
        self.assertEqual(event.metadata["before"]["status"], "published")
        self.assertEqual(event.metadata["after"]["status"], "retired")

    @override_settings(PASSWORD_RESET_TIMEOUT=1)
    def test_expired_and_invalid_recovery_tokens_fail_without_credential_change(self):
        target = User.objects.create_user(username="b10-recovery-target")
        original = target.password
        now = timezone.now().replace(tzinfo=None)
        with patch.object(account_recovery_tokens, "_now", return_value=now):
            token = account_recovery_tokens.make_token(target)
        with patch.object(
            account_recovery_tokens, "_now", return_value=now + timedelta(seconds=2)
        ):
            self.assertFalse(account_recovery_tokens.check_token(target, token))
            response = self.client.get(
                reverse(
                    "accounts:password_reset_confirm",
                    args=[urlsafe_base64_encode(force_bytes(target.pk)), token],
                )
            )
            self.assertFalse(response.context["validlink"])
        response = self.client.get(
            reverse(
                "accounts:password_reset_confirm",
                args=[urlsafe_base64_encode(force_bytes(target.pk)), "invalid-token"],
            )
        )
        self.assertFalse(response.context["validlink"])
        target.refresh_from_db()
        self.assertEqual(target.password, original)
