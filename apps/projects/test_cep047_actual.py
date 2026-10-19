"""Real target transactions with explicit synthetic approved policy bindings.

The native adapters are exercised separately. These bindings never activate a
development tenant or select a production allocation/recognition policy.
"""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase, TransactionTestCase

from apps.audit.models import AuditEvent
from apps.organizations.catalog_bootstrap import synchronize_authorization_catalog
from apps.projects import actual_integration as integration
from apps.projects import test_p4_budget_preparation as helpers
from apps.projects.actual_sources import (
    SOURCE_MODELS,
    ActualRejected,
    NativeActualSource,
)
from apps.projects.models import ProjectCostFact
from apps.projects.services import (
    accept_budget_version,
    approve_project_cost_source_contract,
    create_project_cost_source_contract,
)
from apps.projects.test_cep005_commitment_integration import _authorized_project


class ActualIdentityUnitTests(SimpleTestCase):
    def test_exact_contract_source_type_identity_version_and_recognition_key(self):
        source = NativeActualSource(
            "pcp-inv-actual",
            SOURCE_MODELS["pcp-inv-actual"],
            "source-uuid",
            "version-1",
            {},
            Decimal("10.00"),
            "IRR",
            "project-uuid",
            True,
            "recognize",
        )
        contract = SimpleNamespace(pk="contract-uuid")
        expected = integration._stable_payload_hash(
            {
                "key": (
                    "contract-uuid",
                    source.source_type,
                    source.source_id,
                    source.source_version,
                    "ACTUAL",
                )
            }
        )
        self.assertEqual(integration._identity(contract, source), expected)
        self.assertEqual(
            integration._identity(contract, replace(source, active=False)), expected
        )
        self.assertNotEqual(
            integration._identity(
                contract, replace(source, source_version="version-2")
            ),
            expected,
        )
        self.assertNotEqual(
            integration._identity(SimpleNamespace(pk="other-contract"), source),
            expected,
        )


class ActualTargetTests(TransactionTestCase):
    _draft = helpers.BudgetPreparationTests._draft
    _classify_and_submit = helpers.BudgetPreparationTests._classify_and_submit

    def setUp(self):
        # Also support an isolated, already-migrated PostgreSQL schema. When
        # pytest skips migration setup, Django's serialized baseline excludes
        # those apps; restore the existing code-owned catalogue after a flush.
        synchronize_authorization_catalog(using="default")
        with patch.object(helpers, "create_project", side_effect=_authorized_project):
            helpers.BudgetPreparationTests.setUp(self)
        self.budget = accept_budget_version(
            budget=self._classify_and_submit(self._draft()),
            actor=self.approver,
            approval_reason="Independent synthetic CEP047 budget",
        )
        self.sources = {}
        self.policies = {}
        self.mapping_changes = {}
        self.contracts = {}
        for key, model in SOURCE_MODELS.items():
            contract = create_project_cost_source_contract(
                organization=self.organization,
                actor=self.preparer,
                producer_key=key,
                version=1,
                measure="actual",
                source_model=model,
                event_schema=f"{key}.v1",
                classification_policy_reference="TEST-CLASSIFICATION-1",
                recognition_policy_reference="TEST-EXPLICIT-DATE-1",
                reconciliation_policy_reference="TEST-RECONCILIATION-1",
                requires_financial_evidence=True,
            )
            self.contracts[key] = approve_project_cost_source_contract(
                contract=contract,
                actor=self.approver,
            )
            self.sources[key, "source-1"] = NativeActualSource(
                key,
                model,
                "source-1",
                "native-version-1",
                {"native": "test"},
                Decimal("100.00"),
                "IRR",
                str(self.project.pk),
                True,
                "recognize",
            )
            self.policies[
                (
                    key,
                    "TEST-CLASSIFICATION-1",
                    "TEST-EXPLICIT-DATE-1",
                    "TEST-RECONCILIATION-1",
                )
            ] = integration.ActualPolicyBinding(self.map_source)
        self.native_patch = patch.object(
            integration, "read_native_actual", side_effect=self.read_source
        )
        self.native_patch.start()
        self.addCleanup(self.native_patch.stop)
        self.policy_patch = patch.object(integration, "POLICIES", self.policies)
        self.policy_patch.start()
        self.addCleanup(self.policy_patch.stop)

    def read_source(self, *, organization, producer_key, source_id, **kwargs):
        if organization.pk != self.organization.pk:
            raise ActualRejected("native_source_evidence_unavailable")
        return self.sources[producer_key, source_id]

    def map_source(self, *, source, **kwargs):
        effect = integration.ActualEffect(
            "explicit-allocation-line-1",
            self.project,
            self.cbs,
            self.wbs,
            self.cost_center,
            -source.amount
            if source.operation == "reverse" and source.amount > 0
            else source.amount,
            source.currency,
            date(2026, 10, 14),
            "TEST-NATIVE-VALUE-1",
            "TEST-FINANCIAL-EVIDENCE-1",
        )
        return integration.ActualMapping(
            (replace(effect, **self.mapping_changes),),
            "TEST-CUTOFF-1",
            "TEST-EXPLICIT-DATE-1",
            "TEST-NATIVE-UNIT-RATE-BOOK-1",
            "TEST-ATTRIBUTION-VERSION-1",
        )

    def candidate(self, key, source_id="source-1", **kwargs):
        return integration.prepare_actual_candidate(
            organization=self.organization,
            actor=kwargs.get("actor", self.preparer),
            contract_id=self.contracts[key].pk,
            source_id=source_id,
        )

    def consume(self, candidate, **kwargs):
        return integration.consume_actual_candidate(
            organization=self.organization,
            actor=self.preparer,
            candidate=candidate,
            **kwargs,
        )

    def reconcile(self, key, source="source-1"):
        return integration.reconcile_actual_candidate(
            organization=self.organization,
            actor=self.preparer,
            contract_id=self.contracts[key].pk,
            source_id=source,
        )

    def test_all_three_l2_candidates_are_read_only_and_explicit_consumption_is_idempotent(
        self,
    ):
        for key in SOURCE_MODELS:
            with self.subTest(key=key):
                before = ProjectCostFact.objects.count()
                candidate = self.candidate(key)
                self.assertEqual(ProjectCostFact.objects.count(), before)
                result = self.consume(candidate)
                self.assertEqual(self.consume(candidate).outcome, "replayed")
                self.assertEqual(ProjectCostFact.objects.count(), before + 1)
                fact = ProjectCostFact.objects.get(pk=result.fact_ids[0])
                self.assertEqual(fact.contract_id, self.contracts[key].pk)
                self.assertEqual(
                    (fact.source_id, fact.source_version),
                    (candidate.source_id, candidate.source_version),
                )
                self.assertEqual(fact.amount, Decimal("100.00"))
                report = self.reconcile(key)
                self.assertFalse(report["missing_target"])
                self.assertTrue(report["target_payload_matches"])
                print(
                    f"CEP047 {key}: L2 no-write -> explicit actual -> replay; reconciliation={report}"
                )

    def test_all_three_source_reversals_preserve_original_and_replay_without_reactivation(
        self,
    ):
        for key in SOURCE_MODELS:
            with self.subTest(key=key):
                candidate = self.candidate(key)
                result = self.consume(candidate)
                self.sources[key, "source-1"] = replace(candidate.source, active=False)
                self.sources[key, "reversal-2"] = replace(
                    candidate.source,
                    source_id="reversal-2",
                    source_version="reversal-version-2",
                    operation="reverse",
                    predecessor_id="source-1",
                )
                reverse_candidate = self.candidate(key, "reversal-2")
                inverse = self.consume(reverse_candidate)
                self.assertEqual(self.consume(reverse_candidate).outcome, "replayed")
                self.assertEqual(self.consume(candidate).fact_ids, result.fact_ids)
                original = ProjectCostFact.objects.get(pk=result.fact_ids[0])
                reversal = ProjectCostFact.objects.get(pk=inverse.fact_ids[0])
                self.assertEqual(reversal.reverses_id, original.pk)
                self.assertEqual(original.amount, -reversal.amount)
                self.assertEqual(original.amount, Decimal("100.00"))
                report = self.reconcile(key, "reversal-2")
                self.assertEqual(report["target_reversals"], inverse.fact_ids)
                print(
                    f"CEP047 {key}: native predecessor -> exact inverse; reconciliation={report}"
                )

    def test_explicit_successor_replaces_without_overwriting_finalized_facts(self):
        key = "pcp-eqp-actual"
        initial = self.candidate(key)
        first = self.consume(initial)
        self.sources[key, "replacement-2"] = replace(
            initial.source,
            source_id="replacement-2",
            source_version="replacement-version-2",
            amount=Decimal("120.00"),
            operation="replace",
            predecessor_id="source-1",
        )
        self.sources[key, "source-1"] = replace(initial.source, active=False)
        second = self.consume(self.candidate(key, "replacement-2"))
        self.assertEqual(len(second.fact_ids), 2)
        self.assertEqual(
            list(
                ProjectCostFact.objects.order_by("amount").values_list(
                    "amount", flat=True
                )
            ),
            [Decimal("-100.00"), Decimal("100.00"), Decimal("120.00")],
        )
        self.assertEqual(
            ProjectCostFact.objects.get(pk=first.fact_ids[0]).amount, Decimal("100.00")
        )
        self.sources[key, "replacement-2"] = replace(
            self.sources[key, "replacement-2"], active=False
        )
        self.sources[key, "replacement-3"] = replace(
            initial.source,
            source_id="replacement-3",
            source_version="replacement-version-3",
            amount=Decimal("130.00"),
            operation="replace",
            predecessor_id="replacement-2",
        )
        self.consume(self.candidate(key, "replacement-3"))
        report = self.reconcile(key)
        self.assertIsNone(report["active_source_version"])
        self.assertEqual(
            report["active_source_versions"],
            (
                {
                    "source_id": "replacement-3",
                    "source_version": "replacement-version-3",
                },
            ),
        )
        self.assertEqual(Decimal(report["lineage_net_amount"]), Decimal("130.00"))
        self.assertEqual(len(report["target_reversals"]), 2)
        self.assertFalse(report["lineage_cycle"])
        self.assertEqual(self.consume(initial).fact_ids, first.fact_ids)
        print(f"CEP047 explicit replacement chain reconciliation={report}")

    def test_all_three_failed_target_transactions_leave_durable_failure_and_retry_revalidates(
        self,
    ):
        for key in SOURCE_MODELS:
            with self.subTest(key=key):
                candidate = self.candidate(key)
                before = ProjectCostFact.objects.count()
                original = integration.record_project_cost_fact

                def fail_after_write(original=original, **kwargs):
                    original(**kwargs)
                    raise RuntimeError("synthetic failure after target insert")

                with (
                    patch.object(
                        integration,
                        "record_project_cost_fact",
                        side_effect=fail_after_write,
                    ),
                    self.assertRaises(RuntimeError),
                ):
                    self.consume(candidate)
                self.assertEqual(ProjectCostFact.objects.count(), before)
                event = AuditEvent.objects.filter(
                    entity_type=integration.ENTITY, metadata__stage="failed"
                ).first()
                self.assertEqual(event.metadata["error_code"], "target_failure")
                self.sources[key, "source-1"] = replace(candidate.source, active=False)
                with self.assertRaisesMessage(ActualRejected, "inactive_source"):
                    self.consume(candidate, retry_of=event.entity_id)
                self.sources[key, "source-1"] = candidate.source
                self.assertEqual(
                    self.consume(candidate, retry_of=event.entity_id).outcome,
                    "recorded",
                )
                self.assertEqual(ProjectCostFact.objects.count(), before + 1)
                print(
                    f"CEP047 {key}: insert -> rollback + durable failure -> denied inactive retry -> revalidated retry"
                )

    def test_no_approved_binding_no_fact_and_no_inferred_rounding(self):
        from uuid import uuid4

        key = "pcp-inv-actual"
        with self.assertRaisesMessage(
            ActualRejected, "approved_actual_contract_required"
        ):
            integration.prepare_actual_candidate(
                organization=self.organization,
                actor=self.preparer,
                contract_id=uuid4(),
                source_id="source-1",
            )
        with (
            patch.object(integration, "POLICIES", {}),
            self.assertRaisesMessage(
                ActualRejected, "approved_mapping_cutoff_classification_required"
            ),
        ):
            self.candidate(key)
        self.mapping_changes = {"amount": Decimal("1.001")}
        with self.assertRaisesMessage(
            ActualRejected, "explicit_fact_precision_mapping_required"
        ):
            self.candidate(key)
        self.assertFalse(ProjectCostFact.objects.exists())

    def test_source_version_policy_and_candidate_tampering_fail_closed(self):
        key = "pcp-inv-actual"
        candidate = self.candidate(key)
        with self.assertRaisesMessage(
            ActualRejected, "candidate_source_or_policy_drift"
        ):
            self.consume(replace(candidate, payload_hash="forged"))
        self.mapping_changes = {"amount": Decimal("101.00")}
        with self.assertRaisesMessage(
            ActualRejected, "candidate_source_or_policy_drift"
        ):
            self.consume(candidate)
        self.mapping_changes = {}
        self.consume(candidate)
        self.sources[key, "source-1"] = replace(
            candidate.source, source_version="new-version"
        )
        with self.assertRaisesMessage(
            ActualRejected, "source_version_or_contract_changed_without_successor"
        ):
            self.consume(self.candidate(key))
        report = self.reconcile(key)
        self.assertTrue(report["unlinked_version_or_contract_drift"])
        self.assertTrue(report["missing_target"])
        self.assertEqual(
            report["other_recorded_source_versions"][0]["source_version"],
            candidate.source_version,
        )

    def test_existing_tenant_authority_is_required(self):
        key = "pcp-inv-actual"
        with self.assertRaises(PermissionDenied):
            self.candidate(key, actor=self.outsider)
        candidate = self.candidate(key)
        # This actor is a member of the other tenant. The foreign producer
        # contract is deliberately indistinguishable from an unavailable one.
        with self.assertRaisesMessage(
            ActualRejected, "approved_actual_contract_required"
        ):
            integration.consume_actual_candidate(
                organization=self.other_organization,
                actor=self.outsider,
                candidate=candidate,
            )
        self.assertFalse(ProjectCostFact.objects.exists())

    def test_preexisting_authoritative_source_fact_cannot_be_recognized_twice(self):
        key = "pcp-inv-actual"
        candidate = self.candidate(key)
        effect = candidate.mapping.effects[0]
        original = integration.record_project_cost_fact(
            organization=self.organization,
            project=effect.project,
            actor=self.preparer,
            contract=self.contracts[key],
            kind="actual_recognized",
            source_id=candidate.source_id,
            source_version=candidate.source_version,
            source_line_id="previous-explicit-line",
            economic_event_id="previous-explicit-occurrence",
            occurrence_id="previous-explicit-target-write",
            recognition_date=effect.recognition_date,
            currency=effect.currency,
            amount=effect.amount,
            cbs_node=effect.cbs_node,
            wbs_node=effect.wbs_node,
            cost_center=effect.cost_center,
            classification_version=self.contracts[key].classification_policy_reference,
            valuation_reference=effect.valuation_reference,
            financial_evidence_reference=effect.financial_evidence_reference,
        )
        with self.assertRaisesMessage(
            ActualRejected, "source_facts_without_integration_lineage"
        ):
            self.consume(candidate)
        self.assertEqual(
            list(ProjectCostFact.objects.values_list("pk", flat=True)), [original.pk]
        )
        report = self.reconcile(key)
        self.assertEqual(report["unlinked_target_fact_ids"], (str(original.pk),))
        self.assertEqual(ProjectCostFact.objects.count(), 1)

    def test_native_domain_workflows_feed_all_three_candidates_and_exact_reversals(
        self,
    ):
        import json
        from datetime import timedelta

        from django.utils import timezone

        from apps.accounting.models import FiscalPeriod, FiscalYear, JournalEntry
        from apps.accounting.test_cep042_regression import explicit_fixture_authority
        from apps.accounts.models import User
        from apps.equipment import cost_services as equipment
        from apps.equipment.models import Equipment, EquipmentAssignment
        from apps.equipment.p8_services import record_usage
        from apps.fixed_assets import services as assets
        from apps.fixed_assets.test_p8_s24_s27 import P8CostAndFixedAssetTests
        from apps.inventory import p8_services as valuation
        from apps.inventory import services as inventory
        from apps.materials.models import Material, UnitOfMeasure
        from apps.organizations.models import (
            BusinessPermission,
            OrganizationMembership,
            OrganizationRole,
            PlatformPolicy,
            PlatformPolicyVersion,
            TenantPolicySelection,
        )
        from apps.organizations.policy_specs import (
            ACCOUNTING_MONEY_PRECISION_POLICY_CODE,
            ACCOUNTING_ROUNDING_POLICY_CODE,
            get_platform_policy_spec,
            initial_accounting_policy_parameters,
        )
        from apps.projects.actual_sources import read_native_actual
        from apps.projects.models import ProjectSite

        self.native_patch.stop()
        self.owner = self.preparer
        self.reviewer = User.objects.create_user(username="native-reviewer")
        self.organization.memberships.create(
            user=self.reviewer, role="company_owner", status="active"
        )
        role = OrganizationRole.objects.create(
            organization=self.organization,
            code="cep047-native-test-only",
            name="Explicit synthetic source workflow authority",
            created_by=self.preparer,
        )
        role.permissions.add(
            *BusinessPermission.objects.exclude(
                code__startswith="accounting_recognition."
            )
        )
        for actor in (self.owner, self.reviewer, self.approver):
            explicit_fixture_authority(
                OrganizationMembership.objects.get(
                    organization=self.organization,
                    user=actor,
                ),
                role,
            )
        self.today = timezone.localdate()
        self.site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="NATIVE",
            name="Native site",
        )
        self.equipment = Equipment.objects.create(
            organization=self.organization,
            code="NATIVE-EQ",
            name="Native equipment",
            category="Machinery",
        )
        deployment = EquipmentAssignment.objects.create(
            organization=self.organization,
            equipment=self.equipment,
            project=self.project,
            site=self.site,
            start_date=self.today - timedelta(days=30),
            status="active",
            created_by=self.owner,
            updated_by=self.owner,
        )
        P8CostAndFixedAssetTests._published_cost_policy(self)
        usage = record_usage(
            organization=self.organization,
            actor=self.owner,
            equipment=self.equipment,
            deployment=deployment,
            started_at=timezone.now() - timedelta(hours=2),
            ended_at=timezone.now(),
            runtime_hours=Decimal(2),
            source_key="CEP047-USAGE",
        )
        allocation = equipment.prepare_cost_allocation(
            organization=self.organization,
            actor=self.owner,
            usage=usage,
            source_key="CEP047-ALLOCATION",
            wbs_node=self.wbs,
            cost_center=self.cost_center,
        )
        equipment.finalize_cost_allocation(
            organization=self.organization, actor=self.reviewer, allocation=allocation
        )
        proposal = equipment.prepare_cost_handoff(
            organization=self.organization,
            actor=self.owner,
            allocation=allocation,
            occurrence_key="CEP047-EQ-PROPOSAL",
        )
        with self.assertRaisesMessage(
            ActualRejected, "equipment_proposal_not_reviewed"
        ):
            self.candidate("pcp-eqp-actual", allocation.pk)
        equipment.review_cost_handoff(
            organization=self.organization, actor=self.reviewer, envelope=proposal
        )

        # Reuse the established native capitalization fixture, with its independent
        # maker/reviewer/capitalizer and book policy; no direct finalized row seed.
        self._published_asset_policies = lambda convention: (
            P8CostAndFixedAssetTests._published_asset_policies(self, convention)
        )
        asset, book = P8CostAndFixedAssetTests._capitalized_asset(self)
        generic_asset_proposal = assets.prepare_handoff(
            organization=self.organization,
            actor=self.owner,
            consumer="project_cost",
            occurrence_key="CEP047-NOT-DEPRECIATION",
            asset_transaction=asset.transactions.get(transaction_type="capitalization"),
        )
        assets.review_handoff(
            organization=self.organization,
            actor=self.reviewer,
            envelope=generic_asset_proposal,
        )
        with self.assertRaisesMessage(
            ActualRejected, "approved_asset_allocation_evidence_required"
        ):
            self.candidate("pcp-fa-actual", generic_asset_proposal.pk)
        with self.assertRaisesMessage(
            ActualRejected, "native_source_evidence_unavailable"
        ):
            self.candidate("pcp-eqp-actual", self.equipment.pk)
        year = FiscalYear.objects.create(
            organization=self.organization,
            code="CEP047-FY",
            name="2026",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
            created_by=self.owner,
        )
        period = FiscalPeriod.objects.create(
            organization=self.organization,
            fiscal_year=year,
            number=1,
            name="January",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 1, 31),
        )
        run = assets.preview_depreciation(
            organization=self.organization,
            actor=self.owner,
            book_policy=book,
            fiscal_period=period,
            occurrence_key="CEP047-DEPRECIATION",
        )
        assets.finalize_depreciation(
            organization=self.organization, actor=self.reviewer, run=run
        )
        asset_proposal = assets.prepare_handoff(
            organization=self.organization,
            actor=self.owner,
            consumer="project_cost",
            occurrence_key="CEP047-FA-PROPOSAL",
            depreciation_line=run.lines.get(asset=asset),
        )
        with self.assertRaisesMessage(ActualRejected, "asset_proposal_not_reviewed"):
            self.candidate("pcp-fa-actual", asset_proposal.pk)
        assets.review_handoff(
            organization=self.organization, actor=self.reviewer, envelope=asset_proposal
        )

        for code in (
            ACCOUNTING_MONEY_PRECISION_POLICY_CODE,
            ACCOUNTING_ROUNDING_POLICY_CODE,
        ):
            spec = get_platform_policy_spec(code)
            policy, _ = PlatformPolicy.objects.get_or_create(
                code=code,
                defaults={
                    "name": spec.name,
                    "category": spec.category,
                    "sensitivity": spec.sensitivity,
                    "tenant_selectable": spec.tenant_selectable,
                    "requires_source_provenance": False,
                    "created_by": self.owner,
                    "updated_by": self.owner,
                },
            )
            version, _ = PlatformPolicyVersion.objects.get_or_create(
                policy=policy,
                version=1,
                defaults={
                    "parameters": initial_accounting_policy_parameters(code),
                    "effective_from": self.today,
                    "status": "published",
                    "source_basis": "product_defined",
                    "created_by": self.owner,
                    "published_by": self.owner,
                    "published_at": timezone.now(),
                    "reason": "Synthetic native fixture",
                },
            )
            membership = self.organization.memberships.get(user=self.owner)
            TenantPolicySelection.objects.create(
                organization=self.organization,
                policy=policy,
                policy_version=version,
                status="active",
                approved_by=membership,
                approved_at=timezone.now(),
                applied_by=membership,
                applied_at=timezone.now(),
                reason="Synthetic native fixture",
            )
        unit = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="CEP047-UNIT",
            name="Unit",
            symbol="u",
            category="count",
        )
        material = Material.objects.create(
            organization=self.organization,
            code="CEP047-MAT",
            name="Material",
            unit_of_measure=unit,
        )
        warehouse = inventory.create_warehouse(
            organization=self.organization,
            actor=self.owner,
            code="CEP047-WH",
            name="Warehouse",
        )

        def movement(kind, quantity, number):
            item = inventory.create_stock_transaction(
                organization=self.organization,
                actor=self.owner,
                transaction_number=number,
                transaction_type=kind,
                material=material,
                unit_of_measure=unit,
                quantity=Decimal(quantity),
                occurred_at=timezone.now(),
                project=self.project,
                **(
                    {"destination_warehouse": warehouse}
                    if kind == "adjustment_in"
                    else {"source_warehouse": warehouse}
                ),
            )
            return inventory.post_stock_transaction(
                organization=self.organization, actor=self.owner, stock_transaction=item
            )

        receipt = movement("adjustment_in", 10, "CEP047-OPENING")
        opening_event = valuation.finalize_valuation(
            organization=self.organization,
            actor=self.owner,
            stock_transaction=receipt,
            source_reference="TEST-OPENING",
            source_version="1",
            unit_cost=Decimal(10),
            idempotency_key="CEP047-OPENING",
        )
        valuation.supply_cost_envelope(
            organization=self.organization,
            actor=self.owner,
            valuation_event=opening_event,
            consumer="project_controls",
            idempotency_key="CEP047-NOT-CONSUMPTION",
        )
        with self.assertRaisesMessage(ActualRejected, "not_project_consumption"):
            self.candidate("pcp-inv-actual", opening_event.pk)
        self.assertFalse(ProjectCostFact.objects.exists())
        issue = movement("issue", 2, "CEP047-ISSUE")
        event = valuation.finalize_valuation(
            organization=self.organization,
            actor=self.owner,
            stock_transaction=issue,
            source_reference="TEST-CONSUMPTION",
            source_version="1",
            unit_cost=Decimal(0),
            idempotency_key="CEP047-ISSUE",
        )
        valuation.supply_cost_envelope(
            organization=self.organization,
            actor=self.owner,
            valuation_event=event,
            consumer="project_controls",
            idempotency_key="CEP047-INV-PROPOSAL",
        )

        originals = {}
        journal_count = JournalEntry.objects.count()
        for key, source in (
            ("pcp-inv-actual", event),
            ("pcp-eqp-actual", allocation),
            ("pcp-fa-actual", asset_proposal),
        ):
            before = ProjectCostFact.objects.count()
            candidate = self.candidate(key, source.pk)
            self.assertEqual(ProjectCostFact.objects.count(), before)
            originals[key] = candidate, self.consume(candidate)
            self.assertEqual(self.consume(candidate).outcome, "replayed")
            self.assertEqual(
                candidate.source,
                read_native_actual(
                    organization=self.organization,
                    actor=self.owner,
                    producer_key=key,
                    source_id=source.pk,
                ),
            )
            self.assertTrue(self.reconcile(key, source.pk)["target_payload_matches"])
            print(
                f"CEP047 NATIVE {key}: approved workflow evidence -> L2 -> explicit target -> replay"
            )

        inverse_stock = inventory.reverse_stock_transaction(
            organization=self.organization,
            actor=self.owner,
            stock_transaction=issue,
            reversal_number="CEP047-ISSUE-REV",
            reason="Reviewed correction",
        )
        inverse_event = valuation.reverse_valuation(
            organization=self.organization,
            actor=self.owner,
            stock_transaction=inverse_stock,
            idempotency_key="CEP047-INV-REV",
        )
        valuation.supply_cost_envelope(
            organization=self.organization,
            actor=self.owner,
            valuation_event=inverse_event,
            consumer="project_controls",
            idempotency_key="CEP047-INV-REV-PROPOSAL",
        )
        inverse_allocation = equipment.reverse_cost_allocation(
            organization=self.organization,
            actor=self.approver,
            allocation=allocation,
            reason="Reviewed correction",
        )
        inverse_proposal = equipment.prepare_cost_handoff(
            organization=self.organization,
            actor=self.owner,
            allocation=inverse_allocation,
            occurrence_key="CEP047-EQ-REV-PROPOSAL",
        )
        equipment.review_cost_handoff(
            organization=self.organization,
            actor=self.reviewer,
            envelope=inverse_proposal,
        )
        inverse_run = assets.reverse_depreciation(
            organization=self.organization,
            actor=self.approver,
            run=run,
            occurrence_key="CEP047-DEP-REV",
            reason="Reviewed correction",
        )
        inverse_asset_proposal = assets.prepare_handoff(
            organization=self.organization,
            actor=self.owner,
            consumer="project_cost",
            occurrence_key="CEP047-FA-REV-PROPOSAL",
            depreciation_line=inverse_run.lines.get(asset=asset),
        )
        assets.review_handoff(
            organization=self.organization,
            actor=self.reviewer,
            envelope=inverse_asset_proposal,
        )
        for key, source in (
            ("pcp-inv-actual", inverse_event),
            ("pcp-eqp-actual", inverse_allocation),
            ("pcp-fa-actual", inverse_asset_proposal),
        ):
            candidate, original_result = originals[key]
            native = read_native_actual(
                organization=self.organization,
                actor=self.owner,
                producer_key=key,
                source_id=source.pk,
            )
            self.assertEqual(native.predecessor_id, candidate.source_id)
            inverse = self.consume(self.candidate(key, source.pk))
            self.assertEqual(self.consume(candidate).outcome, "replayed")
            original = ProjectCostFact.objects.get(pk=original_result.fact_ids[0])
            reversed_fact = ProjectCostFact.objects.get(pk=inverse.fact_ids[0])
            self.assertEqual(
                (reversed_fact.reverses_id, reversed_fact.amount),
                (original.pk, -original.amount),
            )
            report = self.reconcile(key, candidate.source_id)
            self.assertFalse(report["source_active"])
            self.assertIn(str(reversed_fact.pk), report["target_reversals"])
            print(
                f"CEP047 NATIVE {key}: explicit source inverse -> linked target inverse; reconciliation={report}"
            )
        self.assertEqual(JournalEntry.objects.count(), journal_count)
        for event in AuditEvent.objects.filter(
            entity_type=integration.ENTITY,
            metadata__stage="succeeded",
        ).order_by("created_at"):
            self.assertTrue(event.metadata["native_lineage"])
            print("CEP047 TRACE " + json.dumps(event.metadata, sort_keys=True))
