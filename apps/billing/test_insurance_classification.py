"""B03 technical proof only: synthetic policies stay inside the test database."""

from datetime import date
from decimal import Decimal
from importlib import import_module

from django.apps import apps
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.billing import tests as fixtures
from apps.billing.models import ClaimAdjustmentType
from apps.billing.services import (
    _resolve_regulatory_rule_version,
    recalculate_progress_claim,
)
from apps.contracts.forms import ContractInsuranceClassificationForm
from apps.contracts.services import (
    approve_contract_term_version,
    create_contract_term_version,
    select_contract_insurance_classification,
)
from apps.organizations.models import (
    InsuranceClassification,
    MembershipScopeGrant,
    Organization,
    PlatformPolicyVersion,
    PolicySourceBasis,
    PolicyVersionStatus,
)
from apps.organizations.policy_services import (
    available_insurance_classifications,
    create_insurance_classification,
    create_platform_policy_version,
    link_policy_version_source,
    publish_platform_policy_version,
    record_optional_policy_review,
    record_policy_source,
    resolve_effective_platform_regulatory_policy,
    set_insurance_classification_active,
)
from apps.organizations.policy_specs import RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE


class InsuranceClassificationTests(TestCase):
    _publish_regulatory_rules = (
        fixtures.ProjectBaselineWorkflowTests._publish_regulatory_rules
    )
    _baseline = fixtures.ProjectBaselineWorkflowTests._baseline
    _approved_baseline = fixtures.ProgressRecordWorkflowTests._approved_baseline
    _record = fixtures.ProgressRecordWorkflowTests._record
    _verified_record = fixtures.ProgressClaimCalculationTests._verified_record
    _claim = fixtures.ProgressClaimCalculationTests._claim

    @classmethod
    def setUpTestData(cls):
        # Existing shared test DB may lack starter templates. Restore only the
        # two canonical prerequisites used by this focused test, in test data.
        from apps.workflows.models import WorkflowTemplate

        for module_name, function_name, code in [
            (
                "0018_project_baseline_compatibility_catalog",
                "seed_project_baseline_catalog",
                "project_baseline_f61",
            ),
            (
                "0019_progress_verification_compatibility_catalog",
                "seed_progress_catalog",
                "progress_verification_f62",
            ),
        ]:
            if not WorkflowTemplate.objects.filter(code=code).exists():
                getattr(
                    import_module("apps.workflows.migrations." + module_name),
                    function_name,
                )(apps, None)

    def setUp(self):
        fixtures.ProjectBaselineWorkflowTests.setUp(self)
        self.contract.contract_number = "CTR-01-01-01"
        self.contract.save()

    def _draft_term(self, **kwargs):
        return create_contract_term_version(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            effective_from=date(2026, 9, 1),
            reason="Test applicability revision",
            **kwargs,
        )

    def _select(self, term, classification=None, actor=None, organization=None):
        return select_contract_insurance_classification(
            organization=organization or self.organization,
            actor=actor or self.owner,
            term_version=term,
            insurance_classification=classification or self.insurance_classification,
            reason="Test-only selection",
        )

    def _resolve(self, term=None):
        return _resolve_regulatory_rule_version(
            organization=self.organization,
            term_version=term or self.contract_terms,
            on_date=date(2026, 9, 30),
        )

    def test_ctr_selection_resolves_policy_and_billing_uses_policy_rate_and_basis(self):
        rules = self._publish_regulatory_rules(
            effective_from=date(2026, 9, 1),
            tax_rate="0",
            insurance_rate="5",
            insurance_basis="after_contractual",
        )
        term = self._select(
            self._draft_term(retention_rate=Decimal(10), retention_cap=Decimal(6))
        )
        approve_contract_term_version(
            organization=self.organization,
            actor=self.manager,
            term_version=term,
            reason="Independent test approval",
        )
        claim = self._claim()
        self.assertEqual(self.contract.contract_number, "CTR-01-01-01")
        self.assertEqual(claim.contract_term_version_id, term.pk)
        self.assertEqual(claim.regulatory_rule_version_id, rules.pk)
        self.assertEqual(self._resolve(term).pk, rules.pk)
        self.assertEqual(rules.parameters["insurance_basis"], "after_contractual")
        adjustment = claim.adjustments.get(
            adjustment_type=ClaimAdjustmentType.STATUTORY_INSURANCE
        )
        self.assertEqual(adjustment.amount, Decimal("-2.7000"))
        self.assertEqual(adjustment.rate_snapshot, Decimal(5))
        self.assertEqual(adjustment.base_amount_snapshot, Decimal("54.0000"))
        self.assertEqual(claim.gross_amount, Decimal("60.0000"))
        term.refresh_from_db()
        self.assertEqual(term.contractual_insurance_rate, Decimal(0))
        self.assertNotIn("insurance_rate", {f.name for f in term._meta.fields})

    def test_missing_draft_expired_and_inactive_classifications_fail_closed(self):
        term = self._draft_term()
        missing = create_insurance_classification(
            actor=self.policy_author,
            code="test-unpublished",
            name="آزمون منتشرنشده",
            reason="Test",
        )
        draft = create_platform_policy_version(
            actor=self.policy_author,
            policy=self.regulatory_rules.policy,
            version=2,
            parameters=self.regulatory_rules.parameters,
            effective_from=timezone.localdate(),
            insurance_classification=missing,
            source_basis=PolicySourceBasis.PRODUCT_DEFINED,
            reason="Synthetic unapproved",
        )
        with self.assertRaises(ValidationError):
            publish_platform_policy_version(
                actor=self.policy_author,
                policy_version=draft,
                reason="Must deny synthetic approval",
            )
        with self.assertRaises(ValidationError):
            self._select(term, missing)
        self.assertNotIn(
            missing, available_insurance_classifications(on_date=date(2026, 9, 1))
        )
        with self.assertRaises(PermissionDenied):
            self._resolve(term)
        with self.assertRaises(ValidationError):
            resolve_effective_platform_regulatory_policy(
                code=RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE,
                consumer="billing.progress_claim.calculate",
                on_date=date(2025, 1, 1),
                insurance_classification=self.insurance_classification,
            )
        set_insurance_classification_active(
            actor=self.policy_author,
            classification=self.insurance_classification,
            is_active=False,
            reason="Test withdrawal",
        )
        with self.assertRaises(ValidationError):
            self._select(term)
        with self.assertRaises(ValidationError):
            self._resolve()

    def test_tenant_permissions_scope_and_approval_separation(self):
        term = self._draft_term()
        with self.assertRaises(PermissionDenied):
            self._select(term, actor=self.member)
        other = Organization.objects.create(name="Other", slug="b03-other")
        with self.assertRaises(PermissionDenied):
            self._select(term, organization=other)
        with self.assertRaises(PermissionDenied):
            _resolve_regulatory_rule_version(
                organization=other,
                term_version=self.contract_terms,
                on_date=date(2026, 9, 30),
            )
        self._select(term, actor=self.manager)
        with self.assertRaises(PermissionDenied):
            approve_contract_term_version(
                organization=self.organization,
                actor=self.manager,
                term_version=term,
                reason="Selector must not approve",
            )
        with self.assertRaises(PermissionDenied):
            approve_contract_term_version(
                organization=self.organization,
                actor=self.owner,
                term_version=term,
                reason="Creator must not approve",
            )
        self.organization.status = "suspended"
        self.organization.save()
        with self.assertRaises(PermissionDenied):
            self._select(term)

    def test_platform_catalog_authority_and_published_mapping_immutability(self):
        for actor in [
            self.owner,
            self.policy_author.__class__.objects.create_superuser(
                username="b03-super", password="unused"
            ),
        ]:
            with self.assertRaises(PermissionDenied):
                create_insurance_classification(
                    actor=actor, code="denied", name="Denied", reason="Test"
                )
        classification = create_insurance_classification(
            actor=self.policy_author,
            code="test-other",
            name="طبقه آزمون دیگر",
            reason="Test",
        )
        self.regulatory_rules.insurance_classification = classification
        with self.assertRaises(ValidationError):
            self.regulatory_rules.save()
        self.contract_terms.insurance_classification = classification
        with self.assertRaises(ValidationError):
            self.contract_terms.save()
        classification.name = "Changed"
        with self.assertRaises(ValidationError):
            classification.save()

    def test_multiple_classifications_publish_and_resolve_without_cross_fallback(self):
        today = timezone.localdate()
        other = create_insurance_classification(
            actor=self.policy_author,
            code="test-other",
            name="طبقه آزمون دیگر",
            reason="Test",
        )
        draft = create_platform_policy_version(
            actor=self.policy_author,
            policy=self.regulatory_rules.policy,
            version=2,
            parameters={**self.regulatory_rules.parameters, "insurance_rate": "7"},
            effective_from=today,
            insurance_classification=other,
            source_basis=PolicySourceBasis.EXTERNAL_AUTHORITY,
            reason="Test-only applicability",
        )
        source = record_policy_source(
            actor=self.policy_author,
            issuer="Synthetic test authority",
            title="Test",
            source_identifier="B03-TEST",
            version="1",
            applicability="Test database only",
            reason="Test",
        )
        link_policy_version_source(
            actor=self.policy_author, policy_version=draft, source=source, reason="Test"
        )
        record_optional_policy_review(
            actor=self.policy_approver,
            policy_version=draft,
            reviewer_identity="Synthetic test reviewer",
            qualification_summary="Test only",
            independence_statement="Test",
            evidence_reference="B03-TEST",
            reviewed_on=today,
            review_scope="Test mapping and parameters",
            disposition="accepted",
        )
        draft.insurance_classification = self.insurance_classification
        with self.assertRaises(ValidationError):
            draft.save()
        draft.refresh_from_db()
        published = publish_platform_policy_version(
            actor=self.policy_author,
            policy_version=draft,
            reason="Test-only publication",
        )
        resolved = resolve_effective_platform_regulatory_policy(
            code=RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE,
            consumer="billing.progress_claim.calculate",
            on_date=today,
            insurance_classification=other,
        )
        self.assertEqual(resolved.pk, published.pk)
        self.assertEqual(resolved.parameters["insurance_rate"], "7")
        self.assertEqual(self._resolve().pk, self.regulatory_rules.pk)

    def test_recalculation_rejects_mismatched_classification_and_missing_evidence(self):
        claim = self._claim()
        other = create_insurance_classification(
            actor=self.policy_author,
            code="test-other",
            name="طبقه آزمون دیگر",
            reason="Test",
        )
        PlatformPolicyVersion.objects.filter(
            pk=claim.regulatory_rule_version_id
        ).update(insurance_classification=other)
        with self.assertRaises(ValidationError):
            recalculate_progress_claim(
                organization=self.organization, actor=self.owner, claim=claim
            )
        PlatformPolicyVersion.objects.filter(
            pk=claim.regulatory_rule_version_id
        ).update(insurance_classification=self.insurance_classification)
        self.regulatory_rules.review_evidence.all().delete()
        with self.assertRaises(ValidationError):
            self._resolve()

    def test_form_and_http_tenant_selection_enforce_visibility_authority_and_csrf(self):
        term = self._draft_term()
        other = create_insurance_classification(
            actor=self.policy_author,
            code="test-unpublished",
            name="آزمون",
            reason="Test",
        )
        self.assertNotIn(
            other,
            ContractInsuranceClassificationForm(on_date=term.effective_from)
            .fields["insurance_classification"]
            .queryset,
        )
        url = reverse(
            "contracts:term_insurance_select", args=[self.contract.pk, term.pk]
        )
        payload = {
            f"{term.pk}-insurance_classification": str(
                self.insurance_classification.pk
            ),
            f"{term.pk}-reason": "Test",
        }
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertContains(
            self.client.get(reverse("contracts:detail", args=[self.contract.pk])),
            "طبقه‌بندی بیمه",
        )
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        term.refresh_from_db()
        self.assertEqual(
            term.insurance_classification_id, self.insurance_classification.pk
        )
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.owner)
        self.assertEqual(csrf.post(url, payload).status_code, 403)
        self.client.force_login(self.member)
        self.assertEqual(self.client.post(url, payload).status_code, 403)
        self.client.force_login(self.policy_author)
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("organizations:select"), response.url)

    def test_platform_http_classification_and_rule_mapping(self):
        self.client.force_login(self.policy_author)
        url = reverse("organizations:platform_policy_catalog")
        self.assertContains(self.client.get(url), "طبقه‌بندی بیمه")
        self.assertEqual(
            self.client.post(
                url,
                {
                    "action": "create_insurance_classification",
                    "code": "test-platform-ui",
                    "name": "آزمون پلتفرم",
                    "reason": "Test",
                },
            ).status_code,
            302,
        )
        classification = InsuranceClassification.objects.get(code="test-platform-ui")
        response = self.client.post(
            url,
            {
                "action": "create_version",
                "policy_id": str(self.regulatory_rules.policy_id),
                "version": "2",
                "effective_from": timezone.localdate().isoformat(),
                "source_basis": "product_defined",
                "parameters": '{"tax_rate":"0","tax_basis":"gross","insurance_rate":"0","insurance_basis":"gross"}',
                "insurance_classification_id": str(classification.pk),
                "reason": "Synthetic test draft",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            PlatformPolicyVersion.objects.filter(
                policy=self.regulatory_rules.policy,
                version=2,
                insurance_classification=classification,
                status=PolicyVersionStatus.DRAFT,
            ).exists()
        )
        self.client.force_login(self.owner)
        self.assertEqual(
            self.client.post(
                url,
                {
                    "action": "create_insurance_classification",
                    "code": "denied",
                    "name": "Denied",
                    "reason": "Test",
                },
            ).status_code,
            403,
        )

    def test_legacy_unclassified_terms_and_policies_have_no_runtime_fallback(self):
        term = self._draft_term()
        term = approve_contract_term_version(
            organization=self.organization,
            actor=self.manager,
            term_version=term,
            reason="Legacy unclassified test state",
        )
        with self.assertRaises(ValidationError):
            self._resolve(term)
        draft = PlatformPolicyVersion.objects.create(
            policy=self.regulatory_rules.policy,
            version=2,
            parameters=self.regulatory_rules.parameters,
            effective_from=timezone.localdate(),
            created_by=self.policy_author,
            source_basis=PolicySourceBasis.EXTERNAL_AUTHORITY,
            reason="Unclassified test draft",
        )
        with self.assertRaises(ValidationError):
            publish_platform_policy_version(
                actor=self.policy_author, policy_version=draft, reason="Must fail"
            )

    def test_project_scope_and_approval_revalidation_fail_closed(self):
        term = self._draft_term()
        MembershipScopeGrant.objects.filter(membership=self.manager_membership).update(
            revoked_at=timezone.now()
        )
        with self.assertRaises(PermissionDenied):
            self._select(term, actor=self.manager)
        self._select(term)
        MembershipScopeGrant.objects.filter(membership=self.manager_membership).update(
            revoked_at=None
        )
        set_insurance_classification_active(
            actor=self.policy_author,
            classification=self.insurance_classification,
            is_active=False,
            reason="Test deactivation before approval",
        )
        with self.assertRaises(ValidationError):
            approve_contract_term_version(
                organization=self.organization,
                actor=self.manager,
                term_version=term,
                reason="Must revalidate classification",
            )
