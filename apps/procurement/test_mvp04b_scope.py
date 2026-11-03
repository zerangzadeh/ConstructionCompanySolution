"""Explicit producer, issue boundary, lineage, addenda and authority tests."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditAction, AuditEvent
from apps.materials.models import Material
from apps.organizations.models import MembershipScopeGrant
from apps.projects.models import Project

from .commercial_scope_services import define_rfq_commercial_scope
from .models import (
    RequestForQuotationVersion,
    RFQCommercialScope,
    RFQCommercialScopeDefinition,
)
from .rfq_services import (
    add_rfq_line,
    create_rfq,
    issue_rfq,
    issue_rfq_addendum,
    submit_rfq_for_issue,
)
from .services import (
    add_purchase_request_item,
    approve_purchase_request,
    submit_purchase_request,
)
from .test_mvp04a import RequestJourneyFixture


class CommercialScopeFixture(RequestJourneyFixture):
    def draft_rfq(self, *, items=1, selected=None):
        pr = self.draft("PR-SCOPE")
        source = []
        for index in range(items):
            material = (
                self.material
                if index == 0
                else Material.objects.create(
                    organization=self.organization,
                    code=f"SCOPE-{index}",
                    name=f"مصالح دوم {index}",
                    unit_of_measure=self.unit,
                )
            )
            source.append(
                add_purchase_request_item(
                    organization=self.organization,
                    actor=self.member,
                    purchase_request=pr,
                    material=material,
                    quantity=Decimal(10),
                )
            )
        submit_purchase_request(
            organization=self.organization, actor=self.member, purchase_request=pr
        )
        approve_purchase_request(
            organization=self.organization,
            actor=self.owner,
            purchase_request=pr,
            reason="approved source",
        )
        now = timezone.now()
        rfq = create_rfq(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            purchase_request=pr,
            rfq_number="RFQ-SCOPE",
            title="استعلام مصالح پروژه",
            closing_at=now + timedelta(days=2),
            earliest_opening_at=now + timedelta(days=2),
        )
        for item in source[: selected if selected is not None else items]:
            add_rfq_line(
                organization=self.organization,
                actor=self.owner,
                rfq=rfq,
                purchase_request_item=item,
                quantity=Decimal(10),
            )
        self.source = source
        return rfq

    def entry(self, *, code="سیمان فونداسیون", quantity="5.0000", item=None, **options):
        return {
            "scope_type": "line",
            "scope_code": code,
            "required_quantity": quantity,
            "lines": [
                {
                    "purchase_request_item_id": str((item or self.source[0]).pk),
                    "quantity": quantity,
                }
            ],
            "independently_awardable": True,
            "allows_split_award": False,
            "allows_alternates": False,
            **options,
        }

    def define(self, rfq, entries=None, *, key="scope-1", expected=0, actor=None):
        rfq.refresh_from_db()
        return define_rfq_commercial_scope(
            organization=self.organization,
            actor=actor or self.owner,
            rfq=rfq,
            version_number=rfq.current_version_number + 1,
            scopes=entries if entries is not None else [self.entry()],
            expected_revision=expected,
            idempotency_key=key,
        )

    def issue(self, rfq, key="issue-1"):
        rfq.refresh_from_db()
        if rfq.status == "draft":
            submit_rfq_for_issue(
                organization=self.organization, actor=self.owner, rfq=rfq
            )
        return issue_rfq(
            organization=self.organization,
            actor=self.owner,
            rfq=rfq,
            suppliers=[self.supplier],
            idempotency_key=key,
        )


class ExplicitScopeTests(CommercialScopeFixture, TestCase):
    def test_no_silent_default_and_issue_fails_atomically_without_definition(self):
        rfq = self.draft_rfq()
        self.assertTrue(rfq.commercial_scope_required)
        self.assertFalse(rfq.scope_definitions.exists())
        with self.assertRaisesMessage(ValueError, "صریحاً"):
            self.issue(rfq)
        self.assertFalse(RequestForQuotationVersion.objects.exists())
        self.assertFalse(RFQCommercialScope.objects.exists())

    def test_line_partial_flags_pin_and_retry_are_exact_and_audited(self):
        rfq = self.draft_rfq()
        definition = self.define(
            rfq, [self.entry(allows_split_award=True, allows_alternates=True)]
        )
        self.assertFalse(RFQCommercialScope.objects.exists())
        version = self.issue(rfq)
        scope = version.commercial_scopes.get()
        self.assertEqual(scope.required_quantity, Decimal(5))
        self.assertTrue(scope.allows_split_award)
        self.assertTrue(scope.allows_alternates)
        self.assertEqual(
            scope.rfq_version_line.purchase_request_item_id, self.source[0].pk
        )
        self.assertEqual(version.commercial_scope_definition_id, definition.pk)
        self.assertEqual(self.issue(rfq).pk, version.pk)
        self.assertEqual(version.commercial_scopes.count(), 1)
        self.assertEqual(
            AuditEvent.objects.filter(
                action=AuditAction.RFQ_COMMERCIAL_SCOPE_DEFINED
            ).count(),
            1,
        )
        self.assertIn(
            definition.payload_fingerprint,
            str(AuditEvent.objects.get(action=AuditAction.RFQ_ISSUED).metadata),
        )

    def test_lot_retains_explicit_members_quantities_and_unit_without_allocations(self):
        from .models import SourcingAwardAllocation

        rfq = self.draft_rfq(items=2)
        entry = self.entry(
            scope_type="lot",
            quantity="1",
            unit_of_measure_id=str(self.unit.pk),
            independently_awardable=False,
            lines=[
                {"purchase_request_item_id": str(item.pk), "quantity": "3"}
                for item in self.source
            ],
        )
        definition = self.define(rfq, [entry])
        scope = self.issue(rfq).commercial_scopes.get()
        self.assertEqual(scope.scope_type, "lot")
        self.assertIsNone(scope.rfq_version_line_id)
        self.assertEqual(scope.required_quantity, Decimal(1))
        self.assertEqual(len(definition.payload["scopes"][0]["lines"]), 2)
        self.assertFalse(SourcingAwardAllocation.objects.exists())

    def test_invalid_source_quantities_flags_and_units_fail_closed(self):
        rfq = self.draft_rfq()
        cases = [
            self.entry(quantity="11"),
            self.entry(quantity="0"),
            self.entry(quantity="NaN"),
            self.entry(item=self.other_material),
            self.entry(scope_type="other"),
            self.entry(independently_awardable=False, allows_split_award=True),
            self.entry(allows_alternates=None),
            self.entry(scope_type="lot", unit_of_measure_id=str(self.other_unit.pk)),
        ]
        for index, entry in enumerate(cases):
            with (
                self.subTest(index=index),
                self.assertRaises((ValueError, PermissionDenied)),
            ):
                self.define(rfq, [entry], key=f"invalid-{index}")
        self.assertFalse(RFQCommercialScopeDefinition.objects.exists())

    def test_revision_optimism_idempotency_and_immutable_definition(self):
        rfq = self.draft_rfq()
        first = self.define(rfq)
        self.assertEqual(self.define(rfq).pk, first.pk)
        with self.assertRaises(ValueError):
            self.define(rfq, [self.entry(quantity="2")])
        second = self.define(rfq, [self.entry(quantity="2")], expected=1, key="scope-2")
        with self.assertRaises(ValueError):
            self.define(rfq, expected=1, key="stale")
        first.refresh_from_db()
        self.assertEqual(first.payload["scopes"][0]["required_quantity"], "5.0000")
        for mutate in (
            lambda: first.save(),
            lambda: first.delete(),
            lambda: RFQCommercialScopeDefinition.objects.filter(pk=first.pk).update(
                payload={}
            ),
        ):
            with self.assertRaises(ValidationError):
                mutate()
        self.assertEqual(self.issue(rfq).commercial_scope_definition_id, second.pk)

    def test_source_drift_requires_new_explicit_definition(self):
        rfq = self.draft_rfq(items=2, selected=1)
        self.define(rfq)
        add_rfq_line(
            organization=self.organization,
            actor=self.owner,
            rfq=rfq,
            purchase_request_item=self.source[1],
            quantity=Decimal(10),
        )
        with self.assertRaisesMessage(ValueError, "تغییر"):
            self.issue(rfq)
        self.define(
            rfq,
            [self.entry(), self.entry(code="قلم دوم", item=self.source[1])],
            expected=1,
            key="recheck",
        )
        self.assertEqual(self.issue(rfq).commercial_scopes.count(), 2)

    def test_scope_issue_rolls_back_version_invitations_and_scope_on_failure(self):
        rfq = self.draft_rfq()
        self.define(rfq)
        with (
            patch(
                "apps.procurement.commercial_scope_services.freeze_commercial_scopes",
                side_effect=ValueError("freeze failure"),
            ),
            self.assertRaises(ValueError),
        ):
            self.issue(rfq)
        self.assertFalse(RequestForQuotationVersion.objects.exists())
        self.assertFalse(RFQCommercialScope.objects.exists())
        rfq.refresh_from_db()
        self.assertEqual(rfq.status, "submitted_for_issue")

    def test_addendum_requires_explicit_next_definition_and_preserves_prior_scope(self):
        rfq = self.draft_rfq()
        definition = self.define(rfq)
        version = self.issue(rfq)
        rfq.refresh_from_db()
        args = {
            "organization": self.organization,
            "actor": self.owner,
            "rfq": rfq,
            "closing_at": rfq.closing_at + timedelta(days=1),
            "earliest_opening_at": rfq.earliest_opening_at + timedelta(days=1),
            "terms": "شرایط جدید",
            "idempotency_key": "addendum-1",
        }
        with self.assertRaises(ValueError):
            issue_rfq_addendum(**args)
        second = self.define(rfq, [self.entry(quantity="2")], key="version-2")
        addendum = issue_rfq_addendum(**args)
        self.assertEqual(issue_rfq_addendum(**args).pk, addendum.pk)
        self.assertEqual(addendum.commercial_scope_definition_id, second.pk)
        self.assertEqual(addendum.commercial_scopes.get().required_quantity, Decimal(2))
        version.refresh_from_db()
        self.assertEqual(version.commercial_scope_definition_id, definition.pk)
        self.assertEqual(version.commercial_scopes.get().required_quantity, Decimal(5))
        with self.assertRaises(ValidationError):
            RequestForQuotationVersion.objects.filter(pk=version.pk).update(
                commercial_scope_definition=second
            )
        with self.assertRaises(ValidationError):
            RFQCommercialScope.objects.create(
                organization=self.organization,
                rfq_version=version,
                rfq_version_line=version.lines.get(),
                scope_type="line",
                scope_code="late policy",
                required_quantity=Decimal(3),
                unit_of_measure=self.unit,
                created_by=self.owner,
            )

    def test_permission_wrong_project_and_tenant_are_denied_in_service(self):
        rfq = self.draft_rfq()
        with self.assertRaises(PermissionDenied):
            self.define(rfq, actor=self.viewer)
        with self.assertRaises(PermissionDenied):
            self.define(rfq, actor=self.outsider)
        membership = self.organization.memberships.get(user=self.owner)
        membership.scope_grants.update(revoked_at=timezone.now())
        other = Project.objects.create(
            organization=self.organization, code="BOUND", name="Other project"
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type="project",
            project=other,
            reason="test fixture",
        )
        with self.assertRaises(PermissionDenied):
            self.define(rfq)

    def test_http_explicit_form_validation_replay_and_issue(self):
        rfq = self.draft_rfq()
        self.login(self.owner)
        url = reverse("procurement:rfq_scope_define", args=[rfq.pk])
        form = self.client.get(url).context["form"]
        payload = {
            name: form[name].value()
            for name in (
                "version_number",
                "expected_revision",
                "idempotency_key",
                "source_fingerprint",
            )
        }
        payload.update(
            scope_code="خرید سیمان",
            scope_type="line",
            member_0="5",
            independently_awardable="no",
            allows_split_award="yes",
            allows_alternates="no",
            operation="append",
        )
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "خرید سیمان", status_code=400)
        self.assertFalse(rfq.scope_definitions.exists())
        payload["independently_awardable"] = "yes"
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        self.assertEqual(rfq.scope_definitions.count(), 1)
        self.issue(rfq)
        response = self.client.get(reverse("procurement:rfq_detail", args=[rfq.pk]))
        self.assertContains(response, "تنظیمات نسخه جاری")
        self.login(self.viewer)
        self.assertEqual(self.client.get(url).status_code, 403)


class ScopeConcurrencyTests(CommercialScopeFixture, TransactionTestCase):
    serialized_rollback = True

    def test_two_revisions_with_same_expected_revision_cannot_overwrite(self):
        rfq = self.draft_rfq()
        barrier = Barrier(2)
        entry = self.entry()

        def action(index):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    define_rfq_commercial_scope(
                        organization=self.organization,
                        actor=self.owner,
                        rfq=rfq,
                        version_number=1,
                        scopes=[entry],
                        expected_revision=0,
                        idempotency_key=f"concurrent-{index}",
                    )
                    return "created"
                except ValueError:
                    return "stale"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertCountEqual(
                list(executor.map(action, range(2))), ["created", "stale"]
            )
        self.assertEqual(rfq.scope_definitions.count(), 1)


class LegacyScopeMigrationTests(TransactionTestCase):
    serialized_rollback = True

    def test_existing_rfqs_remain_legacy_without_inferred_scope(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        self.assertTrue(connection.settings_dict["NAME"].startswith("test_"))
        old = [("procurement", "0016_external_portal_original_evidence")]
        new = [("procurement", "0017_mvp04b_explicit_rfq_scope")]
        try:
            executor = MigrationExecutor(connection)
            executor.migrate(old)
            registry = executor.loader.project_state(old).apps
            organization = registry.get_model(
                "organizations", "Organization"
            ).objects.create(name="Historical Co", slug="scope-migration")
            project = registry.get_model("projects", "Project").objects.create(
                organization=organization, name="Historical project", code="HIST"
            )
            pr = registry.get_model("procurement", "PurchaseRequest").objects.create(
                organization=organization,
                project=project,
                title="Historical PR",
                request_number="HIST",
            )
            legacy = registry.get_model(
                "procurement", "RequestForQuotation"
            ).objects.create(
                organization=organization,
                project=project,
                purchase_request=pr,
                title="Historical RFQ",
                rfq_number="HIST",
                closing_at=timezone.now(),
                earliest_opening_at=timezone.now() + timedelta(days=1),
            )
            executor = MigrationExecutor(connection)
            executor.migrate(new)
            current = executor.loader.project_state(new).apps
            rfq_model = current.get_model("procurement", "RequestForQuotation")
            self.assertFalse(
                rfq_model.objects.get(pk=legacy.pk).commercial_scope_required
            )
            self.assertTrue(
                rfq_model._meta.get_field("commercial_scope_required").get_default()
            )
            self.assertEqual(
                current.get_model(
                    "procurement", "RFQCommercialScopeDefinition"
                ).objects.count(),
                0,
            )
        finally:
            MigrationExecutor(connection).migrate(new)
