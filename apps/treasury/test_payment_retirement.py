"""Current-operation replacement and retained-reference acceptance tests."""

import hashlib
import json
from datetime import date
from decimal import Decimal
from tempfile import TemporaryDirectory

from django.apps import apps
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.accounts.management.commands.seed_demo_data import Command
from apps.accounts.models import User
from apps.documents.models import RetiredPaymentEvidence
from apps.documents.services import (
    add_document_link,
    create_document,
    get_organization_document,
)
from apps.financials.services import get_project_financial_report
from apps.organizations.models import (
    BusinessPermission,
    BusinessPermissionCode,
    OrganizationRole,
)
from apps.organizations.services import create_organization_with_owner
from apps.parties.models import BusinessParty, PartyKind
from apps.projects.services import create_project
from apps.treasury.models import (
    PaymentRequest,
    TreasuryMovement,
    TreasuryMovementDocumentLink,
)
from apps.treasury.services import create_movement, reverse_posted_movement
from tests.retirement_fixtures import CashFixture, explicit_fixture_roles


class TreasuryPaymentReplacementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="replacement-owner")
        cls.organization = create_organization_with_owner(
            owner=cls.owner, name="Replacement", slug="replacement"
        )
        cls.project = create_project(
            organization=cls.organization,
            actor=cls.owner,
            code="CASH",
            name="Cash project",
        )
        cls.party = BusinessParty.objects.create(
            organization=cls.organization,
            party_kind=PartyKind.COMPANY,
            display_name="Test supplier",
        )
        cls.cash = CashFixture(organization=cls.organization, owner=cls.owner)

    def movement(self, **overrides):
        args = {
            "organization": self.organization,
            "actor": self.owner,
            "project": self.project,
            "party": self.party,
            "kind": "receipt",
            "amount": Decimal(100),
            "movement_date": date(2026, 10, 19),
            "description": "Current receipt",
            "idempotency_key": "REPLACEMENT-CASH",
            "account": self.cash.bank,
        }
        args.update(overrides)
        return create_movement(**args)

    def login(self, client=None):
        client = client or self.client
        client.force_login(self.owner)
        session = client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        return client

    def test_ui_create_submit_post_and_reverse_preserve_treasury_history(self):
        self.login()
        self.assertEqual(
            self.client.get(reverse("treasury:movement_create")).status_code, 200
        )
        payload = {
            "kind": "receipt",
            "movement_date": "1405/07/27",
            "amount": "100",
            "account": str(self.cash.bank.pk),
            "project": str(self.project.pk),
            "party": str(self.party.pk),
            "description": "UI current receipt",
            "idempotency_key": "UI-CASH",
        }
        self.assertEqual(
            self.client.post(reverse("treasury:movement_create"), payload).status_code,
            302,
        )
        movement = TreasuryMovement.objects.get(idempotency_key="UI-CASH")
        self.assertEqual(movement.movement_date, date(2026, 10, 19))
        self.assertEqual(
            self.client.get(
                reverse("treasury:movement_detail", args=[movement.pk])
            ).status_code,
            200,
        )
        self.client.post(
            reverse("treasury:movement_submit", args=[movement.pk]),
            {"reason": "Submit receipt"},
        )
        args = {
            "accounting_preparer": str(self.cash.accountant_membership.pk),
            "period": str(self.cash.period.pk),
            "reason": "Explicit independent approval",
        }
        self.client.post(reverse("treasury:movement_post", args=[movement.pk]), args)
        movement.refresh_from_db()
        self.assertEqual(movement.status, "posted")
        self.assertIsNotNone(movement.journal_id)
        self.assertEqual(
            self.client.get(
                reverse("treasury:movement_detail", args=[movement.pk])
            ).status_code,
            200,
        )
        args["accounting_date"] = "2026-10-19"
        self.client.post(reverse("treasury:movement_reverse", args=[movement.pk]), args)
        self.assertTrue(
            TreasuryMovement.objects.filter(reverses=movement, status="posted").exists()
        )
        self.assertEqual(list(apps.get_app_config("payments").get_models()), [])

    def test_ui_csrf_and_cross_tenant_targets_fail_closed(self):
        client = self.login(Client(enforce_csrf_checks=True))
        self.assertEqual(
            client.post(reverse("treasury:movement_create"), {}).status_code, 403
        )
        other = create_organization_with_owner(
            owner=self.owner, name="Other", slug="replacement-stranger"
        )
        movement = self.movement()
        self.login()
        session = self.client.session
        session["active_organization_id"] = str(other.pk)
        session.save()
        self.assertEqual(
            self.client.get(
                reverse("treasury:movement_detail", args=[movement.pk])
            ).status_code,
            404,
        )
        response = self.client.get(reverse("treasury:movement_create"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, str(self.project.pk))
        self.assertNotContains(response, str(self.cash.bank.pk))
        self.assertEqual(self.client.get("/payments/").status_code, 404)

    def test_retired_runtime_has_no_models_or_service_module(self):
        import importlib.util

        self.assertEqual(list(apps.get_app_config("payments").get_models()), [])
        self.assertIsNone(importlib.util.find_spec("apps.payments"))

    def test_financial_projection_requires_treasury_source_permission(self):
        user = User.objects.create_user(username="projection-only")
        role = OrganizationRole.objects.create(
            organization=self.organization,
            code="projection-only",
            name="Projection only",
        )
        role.permissions.add(
            BusinessPermission.objects.get(code=BusinessPermissionCode.FINANCIALS_VIEW)
        )
        self.organization.memberships.create(
            user=user, role_definition=role, status="active"
        )
        explicit_fixture_roles(self.organization)
        with self.assertRaises(PermissionDenied):
            get_project_financial_report(
                user=user, organization=self.organization, project_id=self.project.pk
            )

    def test_projection_counts_one_cash_event_and_excludes_drafts_and_reversals(self):
        movement = self.cash.post(self.movement())
        self.movement(kind="disbursement", idempotency_key="PENDING")
        # Excluded demo data is deliberately present to prove source separation.
        snapshot = {
            "disposition": "excluded_demo_test",
            "payment": {"amount": "100.00"},
        }
        RetiredPaymentEvidence.objects.create(
            organization=self.organization,
            project=self.project,
            payment_number="EXCLUDED-DEMO",
            source_snapshot=snapshot,
            source_sha256=hashlib.sha256(
                json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            authority_reference="test-only",
        )

        def report():
            return get_project_financial_report(
                user=self.owner,
                organization=self.organization,
                project_id=self.project.pk,
            )

        self.assertEqual(report().receipt_total, Decimal(100))
        self.assertEqual(report().posted_movement_count, 1)
        self.assertEqual(
            report().cash_source_references,
            ((str(movement.pk), movement.version, str(movement.journal_id)),),
        )
        reverse_posted_movement(
            organization=self.organization,
            actor=self.owner,
            movement=movement,
            requested_by=self.cash.accountant_membership,
            accounting_date=date(2026, 10, 19),
            period=self.cash.period,
            reason="Reverse test receipt",
        )
        self.assertEqual(report().receipt_total, Decimal(0))
        self.assertEqual(report().posted_movement_count, 0)

    def test_dms_links_current_treasury_without_legacy_reference(self):
        movement = self.movement()
        with (
            TemporaryDirectory() as media,
            override_settings(MEDIA_ROOT=media, DOCUMENT_PROTECTED_ROOT=media),
        ):
            document = create_document(
                organization=self.organization,
                actor=self.owner,
                document_type="receipt",
                title="Treasury receipt",
                reference="TR-DOC",
                description="Evidence",
                upload=SimpleUploadedFile(
                    "receipt.pdf", b"%PDF-1.7\nevidence", content_type="application/pdf"
                ),
                target=movement,
            )
            link = TreasuryMovementDocumentLink.objects.get(document=document)
            self.assertEqual(link.treasury_movement_id, movement.pk)
            self.assertEqual(document.links.count(), 0)
            self.assertEqual(
                get_organization_document(
                    user=self.owner,
                    organization=self.organization,
                    document_id=str(document.pk),
                ).pk,
                document.pk,
            )
            with self.assertRaises(ValidationError):
                add_document_link(document=document, actor=self.owner, target=movement)

    def test_retained_source_snapshot_is_interpretable_and_immutable(self):
        snapshot = {"disposition": "excluded_demo_test", "payment": {"number": "OLD-1"}}
        digest = hashlib.sha256(
            json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        evidence = RetiredPaymentEvidence.objects.create(
            organization=self.organization,
            project=self.project,
            payment_number="OLD-1",
            source_snapshot=snapshot,
            source_sha256=digest,
            authority_reference="test-only",
        )
        self.assertIn("OLD-1", str(evidence))
        for action in (
            lambda: evidence.save(),
            lambda: evidence.delete(),
            lambda: RetiredPaymentEvidence.objects.filter(pk=evidence.pk).update(
                payment_number="changed"
            ),
            lambda: RetiredPaymentEvidence.objects.filter(pk=evidence.pk).delete(),
        ):
            with self.assertRaises(ValidationError):
                action()

    def test_demo_requests_are_pending_idempotent_and_do_not_fabricate_cash(self):
        command = Command()
        args = (
            1,
            1,
            self.organization,
            self.owner,
            self.project,
            [],
            [],
            [self.party] * 6,
            date(2026, 1, 1),
        )
        command._seed_treasury_requests(*args)
        command._seed_treasury_requests(*args)
        self.assertEqual(PaymentRequest.objects.count(), 4)
        self.assertEqual(PaymentRequest.objects.exclude(status="draft").count(), 0)
        self.assertEqual(TreasuryMovement.objects.count(), 0)
        self.assertEqual(list(apps.get_app_config("payments").get_models()), [])
