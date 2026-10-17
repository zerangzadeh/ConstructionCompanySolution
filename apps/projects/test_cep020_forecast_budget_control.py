from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.estimates.services import (
    add_estimate_item,
    approve_estimate,
    create_estimate,
)
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationRole,
    OrganizationSettings,
)
from apps.projects import test_p4_budget_preparation as budget_helpers
from apps.projects.budget_control import _classify_overrun, evaluate_budget_control
from apps.projects.forecast_governance import (
    forecast_submission_key,
    requester_forecast_status,
    submit_project_cost_forecast,
)
from apps.projects.models import ForecastReviewStatus, ProjectForecastTransition
from apps.projects.services import (
    accept_budget_version,
    add_cbs_node,
    add_cost_center,
    create_cost_structure_version,
    create_project,
    create_project_cost_forecast_draft,
    create_wbs_node,
    lock_cost_structure_version,
)
from apps.workflows.models import WorkflowType
from apps.workflows.runtime import claim_work_item, complete_work_item
from apps.workflows.services import (
    create_workflow_draft,
    edit_workflow_draft,
    publish_workflow_version,
)


class ForecastGovernanceTests(TestCase):
    _draft = budget_helpers.BudgetPreparationTests._draft
    _classify_and_submit = budget_helpers.BudgetPreparationTests._classify_and_submit

    def setUp(self) -> None:
        self.preparer = User.objects.create_user(username="cep020-preparer")
        self.approver = User.objects.create_user(username="cep020-approver")
        self.outsider = User.objects.create_user(username="cep020-outsider")
        self.organization = Organization.objects.create(
            name="CEP-020 Org", slug="cep020-org"
        )
        self.other_organization = Organization.objects.create(
            name="CEP-020 Other", slug="cep020-other"
        )
        OrganizationSettings.objects.create(
            organization=self.organization, currency="IRR"
        )
        OrganizationSettings.objects.create(
            organization=self.other_organization, currency="IRR"
        )
        owner_role = OrganizationRole.objects.get(code=MembershipRole.COMPANY_OWNER)
        for organization, user in (
            (self.organization, self.preparer),
            (self.organization, self.approver),
            (self.other_organization, self.outsider),
        ):
            membership = organization.memberships.create(
                user=user,
                role=MembershipRole.COMPANY_OWNER,
                role_definition=owner_role,
                status=MembershipStatus.ACTIVE,
            )
            membership.role_assignments.create(
                organization=organization,
                role=owner_role,
                reason="Explicit CEP-020 test authority",
            )
            membership.scope_grants.create(
                organization=organization,
                scope_type=AuthorizationScopeType.ORGANIZATION,
                reason="Explicit CEP-020 test scope",
            )
        self.project = create_project(
            organization=self.organization,
            actor=self.preparer,
            code="CEP020",
            name="Forecast project",
            estimated_budget=Decimal("999.00"),
            actual_budget=Decimal("111.00"),
        )
        self.wbs = create_wbs_node(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
            code="W1",
            title="Work",
        )
        self.estimate = create_estimate(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
            estimate_number="CEP020-EST",
            title="Approved estimate source",
        )
        add_estimate_item(
            estimate=self.estimate,
            actor=self.preparer,
            description="Included line",
            quantity=Decimal(2),
            unit_price=Decimal("50.00"),
        )
        add_estimate_item(
            estimate=self.estimate,
            actor=self.preparer,
            description="Excluded line",
            quantity=Decimal(1),
            unit_price=Decimal("25.00"),
        )
        approve_estimate(estimate=self.estimate, actor=self.preparer)
        self.estimate.refresh_from_db()
        self.revision = self.estimate.current_revision
        self.structure = create_cost_structure_version(
            organization=self.organization,
            actor=self.preparer,
            code="CBS",
            version=1,
            name="Approved planning structure",
            governance_reference="PO-G07-EXPLICIT",
        )
        self.cbs = add_cbs_node(
            structure=self.structure,
            actor=self.preparer,
            code="C1",
            name="Direct cost",
        )
        self.cost_center = add_cost_center(
            structure=self.structure,
            actor=self.preparer,
            code="CC1",
            name="Project responsibility",
        )
        lock_cost_structure_version(structure=self.structure, actor=self.preparer)
        self.structure.refresh_from_db()
        submitted = self._classify_and_submit(self._draft())
        self.budget = accept_budget_version(
            budget=submitted,
            actor=self.approver,
            approval_reason="Independent acceptance for forecast review tests",
        )
        owner_role.permissions.add(
            BusinessPermission.objects.get(
                code=BusinessPermissionCode.PROJECT_FORECASTS_REVIEW
            )
        )

    def _workflow(self):
        workflow_type = WorkflowType.objects.get(code="projects.forecast_approval")
        version = create_workflow_draft(
            actor=self.preparer,
            organization=self.organization,
            workflow_type_code=workflow_type.code,
            code="forecast-review-test",
            name="Forecast review",
            scope={"project_id": str(self.project.pk)},
        )
        configuration = {
            "steps": [
                {"key": "start", "step_type": "start", "is_start": True},
                {
                    "key": "review",
                    "step_type": "approval",
                    "required_permission": str(
                        BusinessPermissionCode.PROJECT_FORECASTS_REVIEW
                    ),
                    "configuration": {
                        "decision_policy": "any",
                        "exclude_creator": True,
                    },
                    "routing": [
                        {
                            "resolver_type": "business_permission",
                            "configuration": {
                                "permission": str(
                                    BusinessPermissionCode.PROJECT_FORECASTS_REVIEW
                                ),
                            },
                        }
                    ],
                },
                {"key": "approved", "step_type": "end", "is_terminal": True},
                {"key": "rejected", "step_type": "end", "is_terminal": True},
            ],
            "transitions": [
                {
                    "source": "start",
                    "target": "review",
                    "outcome": "submitted",
                    "is_default": True,
                },
                {
                    "source": "review",
                    "target": "approved",
                    "outcome": "approved",
                    "domain_command": "projects.forecast.approve",
                    "required_permission": str(
                        BusinessPermissionCode.PROJECT_FORECASTS_REVIEW
                    ),
                },
                {
                    "source": "review",
                    "target": "rejected",
                    "outcome": "rejected",
                    "domain_command": "projects.forecast.reject",
                    "required_permission": str(
                        BusinessPermissionCode.PROJECT_FORECASTS_REVIEW
                    ),
                },
            ],
        }
        version = edit_workflow_draft(
            actor=self.preparer,
            organization=self.organization,
            version_id=version.pk,
            configuration=configuration,
        )
        return publish_workflow_version(
            actor=self.preparer, organization=self.organization, version_id=version.pk
        )

    def _forecast(self):
        return create_project_cost_forecast_draft(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
            cutoff_date=date(2026, 10, 1),
            uncommitted_etc=Decimal("100.00"),
            assumptions="Documented remaining-work estimate",
        )

    def test_approved_reforecast_supersedes_without_changing_budget(self) -> None:
        version = self._workflow()
        first = self._forecast()
        instance = submit_project_cost_forecast(
            forecast=first,
            actor=self.preparer,
            workflow_version=version,
            reason="Submit version one",
            idempotency_key=forecast_submission_key(first),
        )
        first.review.refresh_from_db()
        self.assertEqual(first.review.status, ForecastReviewStatus.UNDER_REVIEW)
        item = instance.work_items.get()
        with self.assertRaises(PermissionDenied):
            claim_work_item(
                actor=self.preparer,
                organization=self.organization,
                work_item_id=item.pk,
                idempotency_key="self-claim",
            )
        claim_work_item(
            actor=self.approver,
            organization=self.organization,
            work_item_id=item.pk,
            idempotency_key="claim-v1",
        )
        complete_work_item(
            actor=self.approver,
            organization=self.organization,
            work_item_id=item.pk,
            outcome="approved",
            idempotency_key="approve-v1",
            command_context={"reason": "Source and assumptions reviewed"},
        )
        first.review.refresh_from_db()
        self.assertEqual(first.review.status, ForecastReviewStatus.APPROVED)
        second = self._forecast()
        self.assertEqual(second.review.predecessor_id, first.review.pk)
        next_instance = submit_project_cost_forecast(
            forecast=second,
            actor=self.preparer,
            workflow_version=version,
            reason="Reforecast",
            idempotency_key=forecast_submission_key(second),
        )
        next_item = next_instance.work_items.get()
        claim_work_item(
            actor=self.approver,
            organization=self.organization,
            work_item_id=next_item.pk,
            idempotency_key="claim-v2",
        )
        complete_work_item(
            actor=self.approver,
            organization=self.organization,
            work_item_id=next_item.pk,
            outcome="approved",
            idempotency_key="approve-v2",
            command_context={"reason": "Updated assumptions reviewed"},
        )
        first.review.refresh_from_db()
        second.review.refresh_from_db()
        self.assertEqual(first.review.status, ForecastReviewStatus.SUPERSEDED)
        self.assertEqual(second.review.status, ForecastReviewStatus.APPROVED)
        self.project.budget_control.refresh_from_db()
        self.assertEqual(
            self.project.budget_control.governing_budget_id, self.budget.pk
        )
        self.assertEqual(
            ProjectForecastTransition.objects.filter(review=first.review).count(), 4
        )
        self.assertEqual(
            set(requester_forecast_status(forecast=second, actor=self.preparer)),
            {"forecast_id", "version", "as_of", "status"},
        )

    def test_rejection_and_cross_tenant_read_fail_closed(self) -> None:
        version = self._workflow()
        forecast = self._forecast()
        instance = submit_project_cost_forecast(
            forecast=forecast,
            actor=self.preparer,
            workflow_version=version,
            reason="Review requested",
            idempotency_key=forecast_submission_key(forecast),
        )
        item = instance.work_items.get()
        claim_work_item(
            actor=self.approver,
            organization=self.organization,
            work_item_id=item.pk,
            idempotency_key="claim-reject",
        )
        complete_work_item(
            actor=self.approver,
            organization=self.organization,
            work_item_id=item.pk,
            outcome="rejected",
            idempotency_key="reject",
            command_context={"reason": "Revise cost assumptions"},
        )
        forecast.review.refresh_from_db()
        self.assertEqual(forecast.review.status, ForecastReviewStatus.REJECTED)
        with self.assertRaises(PermissionDenied):
            requester_forecast_status(forecast=forecast, actor=self.outsider)
        with self.assertRaises(ValidationError):
            forecast.review.transitions.first().save()
        forecast.review.status = ForecastReviewStatus.APPROVED
        with self.assertRaises(ValidationError):
            forecast.review.save(update_fields=["status"])

    def test_review_requires_current_source_and_an_assigned_work_item(self) -> None:
        from apps.projects.forecast_governance import decide_project_cost_forecast

        version = self._workflow()
        forecast = self._forecast()
        with self.assertRaises(ValidationError):
            decide_project_cost_forecast(
                forecast=forecast,
                actor=self.approver,
                approved=True,
                reason="Premature approval",
            )
        instance = submit_project_cost_forecast(
            forecast=forecast,
            actor=self.preparer,
            workflow_version=version,
            reason="Review requested",
            idempotency_key=forecast_submission_key(forecast),
        )
        with self.assertRaises(PermissionDenied):
            decide_project_cost_forecast(
                forecast=forecast,
                actor=self.approver,
                approved=True,
                reason="Unassigned direct call",
            )
        item = instance.work_items.get()
        claim_work_item(
            actor=self.approver,
            organization=self.organization,
            work_item_id=item.pk,
            idempotency_key="claim-source-check",
        )
        self.project.budget_control.governing_budget = None
        self.project.budget_control.save(update_fields=["governing_budget"])
        with self.assertRaises(ValidationError):
            complete_work_item(
                actor=self.approver,
                organization=self.organization,
                work_item_id=item.pk,
                outcome="approved",
                idempotency_key="stale-source",
                command_context={"reason": "Source changed"},
            )

    def test_budget_control_is_inert_and_zero_tolerance_is_exact(self) -> None:
        with self.assertRaises(PermissionDenied):
            evaluate_budget_control(
                organization=self.organization,
                project=self.project,
                cbs_node=self.cbs,
                actor=self.preparer,
                event_key="unapproved.purchase_order",
                source_id="PO-1",
                source_version="1",
                actual_delta=Decimal("0.00"),
                open_commitment_delta=Decimal("1.00"),
            )
        self.assertEqual(
            _classify_overrun(
                budget_amount=Decimal("100.00"),
                actual_cost=Decimal("60.00"),
                open_commitment=Decimal("40.00"),
                actual_delta=Decimal("1.00"),
                open_commitment_delta=Decimal("-1.00"),
                response="WARNING",
                override_enabled=False,
                override_requested=False,
            ),
            ("ALLOW", Decimal("100.00"), Decimal("0.00")),
        )
        self.assertEqual(
            _classify_overrun(
                budget_amount=Decimal("100.00"),
                actual_cost=Decimal("60.00"),
                open_commitment=Decimal("40.00"),
                actual_delta=Decimal("1.00"),
                open_commitment_delta=Decimal("0.00"),
                response="HARD_STOP",
                override_enabled=False,
                override_requested=False,
            )[0],
            "BLOCK",
        )
        for response in ("WARNING", "HARD_STOP"):
            with self.assertRaises(ValidationError):
                _classify_overrun(
                    budget_amount=Decimal("100.00"),
                    actual_cost=Decimal("60.00"),
                    open_commitment=Decimal("40.00"),
                    actual_delta=Decimal("0.01"),
                    open_commitment_delta=Decimal("0.00"),
                    response="PROFILE_DEFAULT",
                    override_enabled=False,
                    override_requested=False,
                )
            self.assertEqual(
                _classify_overrun(
                    budget_amount=Decimal("100.00"),
                    actual_cost=Decimal("60.00"),
                    open_commitment=Decimal("40.00"),
                    actual_delta=Decimal("0.01"),
                    open_commitment_delta=Decimal("0.00"),
                    response=response,
                    override_enabled=True,
                    override_requested=True,
                )[0],
                "OVERRIDE",
            )

    def test_budget_control_contract_pins_policy_and_audits_override(self) -> None:
        synthetic_event = "test.synthetic_event"
        response_policy = SimpleNamespace(
            pk=uuid4(), parameters={"response": "HARD_STOP"}
        )
        override_policy = SimpleNamespace(
            pk=uuid4(), parameters={"override_enabled": True}
        )
        with (
            patch(
                "apps.projects.budget_control.APPROVED_CONTROL_EVENTS",
                frozenset({synthetic_event}),
            ),
            patch(
                "apps.projects.budget_control.resolve_active_tenant_policy",
                side_effect=(response_policy, override_policy),
            ) as resolve,
            patch("apps.projects.budget_control.record_audit_event") as audit,
        ):
            result = evaluate_budget_control(
                organization=self.organization,
                project=self.project,
                cbs_node=self.cbs,
                actor=self.preparer,
                event_key=synthetic_event,
                source_id="SOURCE-1",
                source_version="2",
                actual_delta=Decimal("999999.00"),
                open_commitment_delta=Decimal("0.00"),
                override_requested=True,
                override_reason="Explicit independent exception",
            )
        self.assertEqual(result.disposition, "OVERRIDE")
        self.assertEqual(
            result.policy_version_ids,
            (str(response_policy.pk), str(override_policy.pk)),
        )
        self.assertEqual(resolve.call_count, 2)
        self.assertEqual(audit.call_args.kwargs["metadata"]["source_version"], "2")
        self.assertEqual(
            audit.call_args.kwargs["metadata"]["override_reason"],
            "Explicit independent exception",
        )

    def test_budget_control_rejects_absent_policy_even_in_isolated_contract_test(
        self,
    ) -> None:
        synthetic_event = "test.synthetic_event"
        with (
            patch(
                "apps.projects.budget_control.APPROVED_CONTROL_EVENTS",
                frozenset({synthetic_event}),
            ),
            patch(
                "apps.projects.budget_control.resolve_active_tenant_policy",
                side_effect=ValidationError("No approved tenant policy"),
            ),
            self.assertRaises(ValidationError),
        ):
            evaluate_budget_control(
                organization=self.organization,
                project=self.project,
                cbs_node=self.cbs,
                actor=self.preparer,
                event_key=synthetic_event,
                source_id="SOURCE-1",
                source_version="2",
                actual_delta=Decimal("1.00"),
                open_commitment_delta=Decimal("0.00"),
            )
