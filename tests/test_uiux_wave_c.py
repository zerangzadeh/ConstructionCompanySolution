"""Wave C: independent read/reconcile authority and financial presentation."""

from datetime import date
from types import SimpleNamespace

from django.core.exceptions import PermissionDenied
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounting.forms import StatementRunForm
from apps.accounting.models import AccountType, FinancialStatementKind
from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.inventory.p8_services import valuation_reconciliation
from apps.organizations.models import (
    MembershipRoleAssignment,
    MembershipScopeGrant,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    OrganizationSettings,
)
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY


class ValuationReadBoundaryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="Wave C A", slug="wave-c-a")
        cls.other = Organization.objects.create(name="Wave C X", slug="wave-c-x")
        OrganizationSettings.objects.create(organization=cls.org, currency="IRR")
        cls.reader = User.objects.create_user(username="wave-c-reader")
        cls.reviewer = User.objects.create_user(username="wave-c-reviewer")
        cls.outsider = User.objects.create_user(username="wave-c-outsider")
        for user, role in ((cls.reader, "viewer"), (cls.reviewer, "project_manager")):
            member = OrganizationMembership.objects.create(
                organization=cls.org,
                user=user,
                role=role,
                status="active",
                authorization_migrated_at=timezone.now(),
            )
            MembershipRoleAssignment.objects.create(
                organization=cls.org,
                membership=member,
                role=OrganizationRole.objects.get(code=role),
                reason="Disposable Wave C existing role",
            )
            MembershipScopeGrant.objects.create(
                organization=cls.org,
                membership=member,
                scope_type="organization",
                reason="Disposable Wave C explicit scope",
            )

    def login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.org.pk)
        session.save()

    def test_reader_can_read_without_reconciliation_authority(self):
        self.login(self.reader)
        before = AuditEvent.objects.count()
        response = self.client.get(reverse("inventory:valuation_workbench"))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["reconciliation"])
        self.assertNotContains(response, "نتایج تطبیق ارزش‌گذاری")
        with self.assertRaises(PermissionDenied):
            valuation_reconciliation(organization=self.org, actor=self.reader)
        self.assertEqual(AuditEvent.objects.count(), before)

    def test_reconciliation_remains_available_to_exact_authority(self):
        self.login(self.reviewer)
        response = self.client.get(reverse("inventory:valuation_workbench"))
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.context["reconciliation"], dict)
        self.assertContains(response, "نتایج تطبیق ارزش‌گذاری")

    def test_tenant_manipulation_cannot_establish_membership(self):
        self.login(self.outsider)
        response = self.client.get(
            reverse("inventory:valuation_workbench"),
            {"organization": str(self.org.pk), "organization_id": str(self.org.pk)},
        )
        self.assertEqual(response.status_code, 403)
        with self.assertRaises(PermissionDenied):
            valuation_reconciliation(organization=self.org, actor=self.outsider)

    def test_cross_tenant_reconciliation_denies_and_post_is_not_a_write_path(self):
        self.login(self.reviewer)
        before = AuditEvent.objects.count()
        with self.assertRaises(PermissionDenied):
            valuation_reconciliation(organization=self.other, actor=self.reviewer)
        response = self.client.post(reverse("inventory:valuation_workbench"))
        self.assertEqual(response.status_code, 405)
        self.assertEqual(AuditEvent.objects.count(), before)

    def test_revoked_authority_and_project_scope_do_not_become_organization_reads(self):
        from apps.projects.models import Project

        self.login(self.reader)
        member = self.org.memberships.get(user=self.reader)
        grant = member.scope_grants.get()
        project = Project.objects.create(organization=self.org, code="A", name="A")
        grant.scope_type = "project"
        grant.project = project
        grant.save()
        self.assertEqual(
            self.client.get(reverse("inventory:valuation_workbench")).status_code,
            403,
        )
        member.role_assignments.update(revoked_at=timezone.now())
        self.assertEqual(
            self.client.get(reverse("inventory:valuation_workbench")).status_code,
            403,
        )


class WaveCPresentationTests(SimpleTestCase):
    def test_statement_kinds_and_account_types_use_canonical_labels(self):
        for kind, label in FinancialStatementKind.choices:
            for account_type, account_label in AccountType.choices:
                with self.subTest(kind=kind, account_type=account_type):
                    preview = SimpleNamespace(
                        kind=kind,
                        ends_on=date(2026, 10, 22),
                        starts_on=date(2026, 10, 1),
                        lines=[SimpleNamespace(account_type=account_type)],
                    )
                    form = StatementRunForm(
                        {
                            "kind": kind,
                            "starts_on": "1405/07/09",
                            "ends_on": "1405/07/30",
                        }
                    )
                    self.assertTrue(form.is_valid(), form.errors)
                    html = render_to_string(
                        "accounting/statement_list.html",
                        {
                            "form": form,
                            "preview": preview,
                            "account_type_choices": AccountType.choices,
                        },
                    )
                    self.assertIn("پیش‌نمایش " + label, html)
                    self.assertIn(
                        '<td class="px-4 py-3">' + account_label + "</td>", html
                    )
                    self.assertNotIn("پیش‌نمایش " + kind, html)

    def test_statement_hashes_are_preserved_in_closed_audit_details(self):
        run = SimpleNamespace(
            scope_hash="SCOPE_SENTINEL",
            input_hash="INPUT_SENTINEL",
            result_hash="RESULT_SENTINEL",
        )
        html = render_to_string("accounting/statement_detail.html", {"run": run})
        details = html[html.index("<details") : html.index("</details>")]
        self.assertIn("ردیابی و ممیزی", details)
        for marker in (run.scope_hash, run.input_hash, run.result_hash):
            self.assertIn(marker, details)
            self.assertEqual(html.count(marker), 1)
        self.assertNotIn(" open", details[: details.index(">")])

    def test_portal_acceptance_has_one_application_main_landmark(self):
        html = render_to_string("procurement/portal_accept.html")
        self.assertEqual(html.count("<main"), 1)
        self.assertIn('aria-labelledby="portal-title"', html)

    def test_nonempty_valuation_preserves_source_lineage_behind_details(self):
        event = SimpleNamespace(
            stock_transaction=SimpleNamespace(
                transaction_number="MOV-1", reference="Business reference"
            ),
            source_reference="SOURCE_REF_SENTINEL",
            source_version="SOURCE_VERSION_SENTINEL",
        )
        envelope = SimpleNamespace(
            consumer="CONSUMER_SENTINEL", valuation_event_id="EVENT_SENTINEL"
        )
        html = render_to_string(
            "inventory/valuation_workbench.html",
            {"events": [event], "envelopes": [envelope], "reconciliation": None},
        )
        from html.parser import HTMLParser

        class DisclosureParser(HTMLParser):
            depth = 0
            normal = ""
            technical = ""

            def handle_starttag(self, tag, attrs):
                if tag == "details":
                    self.depth += 1
                    self.assert_closed = "open" not in dict(attrs)

            def handle_endtag(self, tag):
                if tag == "details":
                    self.depth -= 1

            def handle_data(self, data):
                if self.depth:
                    self.technical += data
                else:
                    self.normal += data

        parser = DisclosureParser()
        parser.feed(html)
        self.assertIn("Business reference", parser.normal)
        for marker in (
            event.source_reference,
            event.source_version,
            envelope.consumer,
            envelope.valuation_event_id,
        ):
            self.assertIn(marker, parser.technical)
            self.assertNotIn(marker, parser.normal)
        self.assertNotIn("نتایج تطبیق ارزش‌گذاری", html)
