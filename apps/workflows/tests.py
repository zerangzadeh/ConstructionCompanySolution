from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, models, transaction
from django.test import TestCase, TransactionTestCase

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.models import (
    BusinessPermission,
    MembershipRole,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.services import create_organization_with_owner

from .models import (
    WorkflowRoutingRule,
    WorkflowStepDefinition,
    WorkflowTemplate,
    WorkflowType,
    WorkflowVersion,
    WorkflowVersionStatus,
)
from .registry import registry
from .services import (
    create_draft_version,
    create_workflow_draft,
    edit_workflow_draft,
    publish_workflow_version,
    retire_workflow_version,
    supersede_workflow_version,
    validate_workflow_draft,
)
from .simulation import simulate_workflow_selection, simulate_workflow_version


def valid_configuration() -> dict:
    return {
        "steps": [
            {"key": "start", "step_type": "start", "is_start": True},
            {
                "key": "decision",
                "step_type": "approval",
                "configuration": {"decision_policy": "any"},
                "routing": [
                    {"resolver_type": "organization_owner", "configuration": {}}
                ],
            },
            {"key": "approved", "step_type": "end", "is_terminal": True},
            {"key": "rejected", "step_type": "end", "is_terminal": True},
        ],
        "transitions": [
            {
                "source": "start",
                "target": "decision",
                "outcome": "submitted",
                "is_default": True,
            },
            {
                "source": "decision",
                "target": "approved",
                "outcome": "approved",
                "domain_command": "procurement.purchase_request.approve",
                "required_permission": "purchase_requests.approve",
            },
            {
                "source": "decision",
                "target": "rejected",
                "outcome": "rejected",
                "domain_command": "procurement.purchase_request.reject",
                "required_permission": "purchase_requests.reject",
            },
        ],
    }


class WorkflowCatalogFlushTests(TransactionTestCase):
    def test_flush_recreates_registered_workflow_types(self) -> None:
        call_command("flush", verbosity=0, interactive=False)

        self.assertEqual(
            set(WorkflowType.objects.values_list("code", flat=True)),
            set(registry.workflow_types),
        )
        for workflow_type in WorkflowType.objects.all():
            specification = registry.workflow_types[workflow_type.code]
            self.assertEqual(workflow_type.subject_type, specification.subject_type)
            self.assertEqual(
                workflow_type.subject_adapter, specification.subject_adapter
            )
            self.assertEqual(
                set(workflow_type.allowed_scope_fields),
                set(specification.allowed_scope_fields),
            )


class WorkflowFoundationTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="wf-owner", password="password")
        self.organization = create_organization_with_owner(
            owner=self.owner, name="Workflow Org", slug="workflow-org"
        )
        self.other_owner = User.objects.create_user(
            username="wf-other-owner", password="password"
        )
        self.other_organization = create_organization_with_owner(
            owner=self.other_owner, name="Other Org", slug="other-workflow-org"
        )
        self.workflow_type = WorkflowType.objects.get(
            code="procurement.purchase_request_approval"
        )

    def create_draft(
        self, *, code: str = "purchase-approval", scope: dict | None = None
    ):
        version = create_workflow_draft(
            actor=self.owner,
            organization=self.organization,
            workflow_type_code=self.workflow_type.code,
            code=code,
            name=code,
            scope=scope,
        )
        return edit_workflow_draft(
            actor=self.owner,
            organization=self.organization,
            version_id=version.pk,
            configuration=valid_configuration(),
        )

    def test_catalog_and_default_grants_are_migrated(self) -> None:
        codes = {
            "workflows.view",
            "workflows.create",
            "workflows.change_draft",
            "workflows.publish",
            "workflows.retire",
        }
        self.assertEqual(
            set(
                BusinessPermission.objects.filter(code__in=codes).values_list(
                    "code", flat=True
                )
            ),
            codes,
        )
        owner_role = OrganizationRole.objects.get(code=MembershipRole.COMPANY_OWNER)
        manager_role = OrganizationRole.objects.get(code=MembershipRole.COMPANY_MANAGER)
        operations_role = OrganizationRole.objects.get(
            code=MembershipRole.OPERATIONS_MANAGER
        )
        self.assertEqual(
            set(
                owner_role.permissions.filter(code__in=codes).values_list(
                    "code", flat=True
                )
            ),
            codes,
        )
        self.assertEqual(
            set(
                manager_role.permissions.filter(code__in=codes).values_list(
                    "code", flat=True
                )
            ),
            {"workflows.view"},
        )
        self.assertFalse(operations_role.permissions.filter(code__in=codes).exists())
        self.assertTrue(
            WorkflowTemplate.objects.filter(workflow_type=self.workflow_type).exists()
        )

    def test_owner_can_manage_and_unprivileged_member_cannot(self) -> None:
        self.create_draft()
        member = User.objects.create_user(username="wf-member", password="password")
        member_role = OrganizationRole.objects.get(code=MembershipRole.MEMBER)
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=member,
            role=member_role.code,
            role_definition=member_role,
            status="active",
        )
        with self.assertRaises(PermissionDenied):
            create_workflow_draft(
                actor=member,
                organization=self.organization,
                workflow_type_code=self.workflow_type.code,
                code="forbidden",
                name="Forbidden",
            )

    def test_tenant_isolation_and_cross_tenant_references(self) -> None:
        version = self.create_draft()
        with self.assertRaises(PermissionDenied):
            edit_workflow_draft(
                actor=self.other_owner,
                organization=self.other_organization,
                version_id=version.pk,
                configuration=valid_configuration(),
            )
        step = WorkflowStepDefinition(
            organization=self.other_organization,
            version=version,
            key="cross-tenant",
            name="Cross tenant",
            step_type="end",
            is_terminal=True,
        )
        with self.assertRaises(ValidationError):
            step.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            WorkflowStepDefinition.objects.bulk_create([step])
        with self.assertRaises(ValidationError):
            simulate_workflow_version(
                actor=self.other_owner,
                organization=self.other_organization,
                version=version,
                context={},
            )

    def test_only_drafts_are_editable_and_published_graph_cannot_be_deleted(
        self,
    ) -> None:
        version = self.create_draft()
        published = publish_workflow_version(
            actor=self.owner, organization=self.organization, version_id=version.pk
        )
        published.change_summary = "changed"
        with self.assertRaises(ValidationError):
            published.save()
        with self.assertRaises(ValidationError):
            published.delete()
        step = WorkflowStepDefinition.objects.filter(version=published).first()
        assert step is not None
        step.name = "changed"
        with self.assertRaises(ValidationError):
            step.save()
        with self.assertRaises(ValidationError):
            WorkflowStepDefinition.objects.filter(pk=step.pk).delete()
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.QuerySet.update(
                WorkflowStepDefinition.objects.filter(pk=step.pk), name="raw change"
            )

    def test_version_uniqueness_and_partial_unique_publication_guard(self) -> None:
        first = self.create_draft()
        publish_workflow_version(
            actor=self.owner, organization=self.organization, version_id=first.pk
        )
        second = WorkflowVersion.objects.create(
            organization=self.organization,
            definition=first.definition,
            version_number=2,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.QuerySet.update(
                WorkflowVersion.objects.filter(pk=second.pk),
                status=WorkflowVersionStatus.PUBLISHED,
            )
        with self.assertRaises(ValidationError):
            WorkflowVersion.objects.create(
                organization=self.organization,
                definition=first.definition,
                version_number=2,
            )

    def test_graph_validation_reports_unreachable_cycle(self) -> None:
        first = self.create_draft(code="project-route", scope={"project_id": "p-1"})
        publish_workflow_version(
            actor=self.owner, organization=self.organization, version_id=first.pk
        )
        broken = self.create_draft(code="broken", scope={"project_id": "p-2"})
        orphan = WorkflowStepDefinition.objects.create(
            organization=self.organization,
            version=broken,
            key="orphan",
            name="Orphan",
            step_type="end",
            is_terminal=True,
        )
        start = broken.steps.get(key="start")
        decision = broken.steps.get(key="decision")
        from .models import WorkflowTransitionDefinition

        WorkflowTransitionDefinition.objects.create(
            organization=self.organization,
            version=broken,
            source_step=decision,
            target_step=start,
            outcome="cycle",
        )
        report = validate_workflow_draft(
            actor=self.owner, organization=self.organization, version_id=broken.pk
        )
        codes = {item["code"] for item in report}
        self.assertIn("invalid_cycle", codes)
        self.assertIn("unreachable_step", codes)
        self.assertEqual(orphan.key, "orphan")

    def test_unregistered_types_and_executable_expressions_are_rejected(self) -> None:
        version = create_workflow_draft(
            actor=self.owner,
            organization=self.organization,
            workflow_type_code=self.workflow_type.code,
            code="unsafe",
            name="Unsafe",
        )
        configuration = valid_configuration()
        configuration["steps"][1]["configuration"] = {"sql": "SELECT 1"}
        with self.assertRaises(ValidationError):
            edit_workflow_draft(
                actor=self.owner,
                organization=self.organization,
                version_id=version.pk,
                configuration=configuration,
            )
        configuration = valid_configuration()
        configuration["steps"][1]["routing"][0]["resolver_type"] = "tenant.custom"
        with self.assertRaises(ValidationError):
            edit_workflow_draft(
                actor=self.owner,
                organization=self.organization,
                version_id=version.pk,
                configuration=configuration,
            )

    def test_publication_retirement_and_validation_are_audited(self) -> None:
        version = self.create_draft()
        self.assertEqual(
            validate_workflow_draft(
                actor=self.owner, organization=self.organization, version_id=version.pk
            ),
            [],
        )
        version = publish_workflow_version(
            actor=self.owner, organization=self.organization, version_id=version.pk
        )
        retired = retire_workflow_version(
            actor=self.owner,
            organization=self.organization,
            version_id=version.pk,
            reason="نسخه جدید",
        )
        self.assertEqual(retired.status, WorkflowVersionStatus.RETIRED)
        actions = set(
            AuditEvent.objects.filter(entity_id=str(version.pk)).values_list(
                "action", flat=True
            )
        )
        self.assertTrue(
            {
                AuditAction.WORKFLOW_DEFINITION_VALIDATED,
                AuditAction.WORKFLOW_VERSION_PUBLISHED,
                AuditAction.WORKFLOW_VERSION_RETIRED,
            }.issubset(actions)
        )

    def test_supersede_retires_old_version_and_publishes_new_atomically(self) -> None:
        old_version = self.create_draft()
        old_version = publish_workflow_version(
            actor=self.owner,
            organization=self.organization,
            version_id=old_version.pk,
        )
        new_version = create_draft_version(
            actor=self.owner,
            organization=self.organization,
            definition_id=old_version.definition_id,
            change_summary="Second policy",
        )
        new_version = edit_workflow_draft(
            actor=self.owner,
            organization=self.organization,
            version_id=new_version.pk,
            configuration=valid_configuration(),
        )
        published = supersede_workflow_version(
            actor=self.owner,
            organization=self.organization,
            new_version_id=str(new_version.pk),
            replaced_version_id=str(old_version.pk),
            reason="Policy replacement",
        )
        old_version.refresh_from_db()
        self.assertEqual(old_version.status, WorkflowVersionStatus.RETIRED)
        self.assertEqual(published.status, WorkflowVersionStatus.PUBLISHED)

    def test_dry_run_is_explanatory_and_does_not_mutate(self) -> None:
        version = self.create_draft()
        result = simulate_workflow_version(
            actor=self.owner,
            organization=self.organization,
            version=version,
            context={"amount": "100"},
        )
        self.assertTrue(result["valid"])
        self.assertFalse(result["mutated"])
        published = publish_workflow_version(
            actor=self.owner, organization=self.organization, version_id=version.pk
        )
        selection = simulate_workflow_selection(
            actor=self.owner,
            organization=self.organization,
            workflow_type_code=self.workflow_type.code,
            context={},
        )
        self.assertEqual(selection["selected_version"], str(published.pk))

    def test_routing_target_from_another_tenant_blocks_publication(self) -> None:
        version = self.create_draft()
        other_membership = OrganizationMembership.objects.get(
            organization=self.other_organization, user=self.other_owner
        )
        decision = version.steps.get(key="decision")
        WorkflowRoutingRule.objects.filter(step=decision).delete()
        WorkflowRoutingRule.objects.create(
            organization=self.organization,
            version=version,
            step=decision,
            resolver_type="explicit_membership",
            configuration={"membership_id": str(other_membership.pk)},
            order=0,
        )
        report = validate_workflow_draft(
            actor=self.owner, organization=self.organization, version_id=version.pk
        )
        self.assertIn("routing_target_cross_tenant", {item["code"] for item in report})
        with self.assertRaises(ValidationError):
            publish_workflow_version(
                actor=self.owner, organization=self.organization, version_id=version.pk
            )
