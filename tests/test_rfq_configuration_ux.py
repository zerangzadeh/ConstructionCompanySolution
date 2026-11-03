"""RFQ configuration HTTP boundaries and persisted adapter results."""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.organizations.models import MembershipScopeGrant
from apps.organizations.services import set_active_organization
from apps.procurement.commercial_scope_services import latest_definition
from apps.procurement.rfq_services import add_rfq_line
from apps.procurement.test_mvp04b_scope import CommercialScopeFixture
from apps.projects.models import Project


class RFQConfigurationUXTests(CommercialScopeFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.login(self.owner)

    def detail(self, rfq):
        return reverse("procurement:rfq_detail", args=[rfq.pk])

    def configure(self, rfq):
        return reverse("procurement:rfq_scope_define", args=[rfq.pk])

    def data(self, rfq):
        form = self.client.get(self.detail(rfq)).context["configuration_form"]
        return {
            **{name: form[name].value() for name in form.fields},
            "operation": "configure_items",
        }

    def test_get_prefills_existing_rows_and_never_persists(self):
        rfq = self.draft_rfq(items=2)
        response = self.client.get(self.detail(rfq))
        form = response.context["configuration_form"]
        self.assertEqual(len(form.rows), 2)
        self.assertEqual(Decimal(form["quantity_0"].value()), Decimal(10))
        self.assertEqual(form["independently_awardable_0"].value(), "yes")
        self.assertNotIn("scope_code", form.fields)
        self.assertNotIn("unit_of_measure", form.fields)
        self.assertFalse(rfq.scope_definitions.exists())
        for forbidden in (
            "Commercial Scope",
            "تعریف صریح دامنه خرید",
            "مقدار حاکم بسته",
        ):
            self.assertNotContains(response, forbidden)

    def test_single_confirmation_multiple_rows_replays_and_issues_exactly(self):
        rfq = self.draft_rfq(items=2)
        data = self.data(rfq)
        data.update(
            quantity_0="3.25", allows_split_award_0="yes", allows_alternates_1="yes"
        )
        for _ in range(2):
            self.assertEqual(
                self.client.post(self.configure(rfq), data).status_code, 302
            )
        self.assertEqual(rfq.scope_definitions.count(), 1)
        scopes = list(
            self.issue(rfq).commercial_scopes.select_related("rfq_version_line")
        )
        by_item = {
            scope.rfq_version_line.purchase_request_item_id: scope for scope in scopes
        }
        self.assertEqual(by_item[self.source[0].pk].required_quantity, Decimal("3.25"))
        self.assertTrue(by_item[self.source[0].pk].allows_split_award)
        self.assertTrue(by_item[self.source[1].pk].allows_alternates)
        self.assertTrue(all(scope.independently_awardable for scope in scopes))
        self.assertEqual(
            list(rfq.lines.values_list("quantity", flat=True)), [Decimal(10)] * 2
        )

    def test_invalid_quantity_flags_and_missing_fields_retain_bound_errors(self):
        rfq = self.draft_rfq()
        baseline = self.data(rfq)
        for changes, field in (
            ({"quantity_0": "11"}, "quantity_0"),
            ({"quantity_0": "0"}, "quantity_0"),
            ({"quantity_0": "NaN"}, "quantity_0"),
            (
                {"independently_awardable_0": "no", "allows_split_award_0": "yes"},
                "allows_split_award_0",
            ),
            ({"allows_alternates_0": ""}, "allows_alternates_0"),
        ):
            with self.subTest(changes=changes):
                response = self.client.post(
                    self.configure(rfq), {**baseline, **changes}
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.context["configuration_form"].errors)
                self.assertFalse(rfq.scope_definitions.exists())

    def test_stale_revision_and_source_changes_fail_without_overwrite(self):
        rfq = self.draft_rfq(items=2, selected=1)
        stale = self.data(rfq)
        first = self.define(rfq)
        self.assertEqual(self.client.post(self.configure(rfq), stale).status_code, 400)
        data = self.data(rfq)
        add_rfq_line(
            organization=self.organization,
            actor=self.owner,
            rfq=rfq,
            purchase_request_item=self.source[1],
            quantity=10,
        )
        self.assertEqual(self.client.post(self.configure(rfq), data).status_code, 400)
        self.assertEqual(latest_definition(rfq, 1).pk, first.pk)

    def test_existing_false_flag_and_multiple_scopes_are_preserved(self):
        rfq = self.draft_rfq()
        original = [
            self.entry(code="اول", quantity="3", independently_awardable=False),
            self.entry(code="دوم", quantity="4", allows_alternates=True),
        ]
        self.define(rfq, original)
        data = self.data(rfq)
        self.assertEqual(data["independently_awardable_0"], "no")
        self.assertEqual(self.client.post(self.configure(rfq), data).status_code, 302)
        entries = latest_definition(rfq, 1).payload["scopes"]
        self.assertEqual({s["scope_code"] for s in entries}, {"اول", "دوم"})
        self.assertFalse(
            next(s for s in entries if s["scope_code"] == "اول")[
                "independently_awardable"
            ]
        )

    def test_group_members_prefill_select_and_replace_without_losing_lines(self):
        rfq = self.draft_rfq(items=2)
        self.client.post(self.configure(rfq), self.data(rfq))
        form = self.client.get(self.configure(rfq)).context["form"]
        data = {
            name: form[name].value()
            for name in (
                "version_number",
                "expected_revision",
                "source_fingerprint",
                "idempotency_key",
            )
        }
        data.update(
            selection_ui="1",
            scope_type="lot",
            scope_code="گروه فونداسیون",
            required_quantity="1",
            unit_of_measure=str(self.unit.pk),
            independently_awardable="no",
            allows_split_award="yes",
            allows_alternates="yes",
            select_0="on",
            select_1="on",
            member_0="10",
            member_1="10",
            operation="append",
        )
        self.assertEqual(self.client.post(self.configure(rfq), data).status_code, 302)
        before = latest_definition(rfq, 1)
        self.assertEqual(len(before.payload["scopes"]), 3)
        edit = self.configure(rfq) + "?edit=" + "گروه فونداسیون"
        form = self.client.get(edit).context["form"]
        self.assertTrue(form["select_0"].value())
        data.update(
            {
                name: form[name].value()
                for name in (
                    "expected_revision",
                    "source_fingerprint",
                    "idempotency_key",
                )
            }
        )
        data.update(operation="replace", member_0="2")
        self.assertEqual(self.client.post(edit, data).status_code, 302)
        after = latest_definition(rfq, 1)
        lot = next(s for s in after.payload["scopes"] if s["scope_type"] == "lot")
        self.assertEqual(len(after.payload["scopes"]), 3)
        self.assertEqual(
            sorted(m["quantity"] for m in lot["lines"]), ["10.0000", "2.0000"]
        )
        # Subsequent ordinary row confirmation retains the lot exactly.
        self.client.post(self.configure(rfq), self.data(rfq))
        self.assertIn(lot, latest_definition(rfq, 1).payload["scopes"])

    def test_only_group_configuration_does_not_infer_independent_line_scopes(self):
        rfq = self.draft_rfq(items=2)
        self.define(
            rfq,
            [
                self.entry(
                    scope_type="lot",
                    quantity="1",
                    unit_of_measure_id=str(self.unit.pk),
                    lines=[
                        {"purchase_request_item_id": str(item.pk), "quantity": "5"}
                        for item in self.source
                    ],
                )
            ],
        )
        response = self.client.get(self.detail(rfq))
        self.assertEqual(response.context["configuration_form"].rows, [])
        self.assertNotContains(response, "data-item-configuration")
        self.assertEqual(len(latest_definition(rfq, 1).payload["scopes"]), 1)

    def test_read_only_project_tenant_and_suspended_boundaries(self):
        rfq = self.draft_rfq()
        data = self.data(rfq)
        self.login(self.viewer)
        self.assertNotContains(
            self.client.get(self.detail(rfq)), "data-item-configuration"
        )
        self.assertEqual(self.client.post(self.configure(rfq), data).status_code, 403)
        self.login(self.outsider)
        session = self.client.session
        set_active_organization(session, self.other_organization)
        session.save()
        self.assertEqual(self.client.post(self.configure(rfq), data).status_code, 404)
        self.login(self.owner)
        self.organization.status = "suspended"
        self.organization.save(update_fields=["status"])
        self.assertEqual(self.client.post(self.configure(rfq), data).status_code, 403)
        self.organization.status = "active"
        self.organization.save(update_fields=["status"])
        membership = self.organization.memberships.get(user=self.owner)
        membership.scope_grants.update(revoked_at=timezone.now())
        project = Project.objects.create(
            organization=self.organization, code="OTHER-UX", name="Other"
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type="project",
            project=project,
            reason="test",
        )
        self.assertEqual(self.client.post(self.configure(rfq), data).status_code, 404)
        self.assertFalse(rfq.scope_definitions.exists())

    def test_forged_hidden_version_and_csrf_fail_closed(self):
        from django.test import Client

        rfq = self.draft_rfq()
        data = self.data(rfq)
        self.assertEqual(
            self.client.post(
                self.configure(rfq), {**data, "version_number": 2}
            ).status_code,
            400,
        )
        client = Client(enforce_csrf_checks=True)
        client.cookies = self.client.cookies
        self.assertEqual(client.post(self.configure(rfq), data).status_code, 403)
        self.assertFalse(rfq.scope_definitions.exists())
