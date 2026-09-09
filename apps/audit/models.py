from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import CreatedAtModel, UUIDModel


class AuditAction(models.TextChoices):
    ORGANIZATION_CREATED = "organization.created", "Organization created"
    ORGANIZATION_SETTINGS_UPDATED = (
        "organization_settings.updated",
        "Organization settings updated",
    )
    BUSINESS_PARTY_CREATED = "business_party.created", "Business party created"
    BUSINESS_PARTY_UPDATED = "business_party.updated", "Business party updated"
    BUSINESS_PARTY_ARCHIVED = "business_party.archived", "Business party archived"
    PARTY_ROLE_ASSIGNED = "party_role.assigned", "Party role assigned"
    PARTY_CONTACT_ADDED = "party_contact.added", "Party contact added"
    UNIT_OF_MEASURE_CREATED = "unit_of_measure.created", "Unit of measure created"
    UNIT_OF_MEASURE_ARCHIVED = "unit_of_measure.archived", "Unit of measure archived"
    MATERIAL_CATEGORY_CREATED = (
        "material_category.created",
        "Material category created",
    )
    MATERIAL_CATEGORY_UPDATED = (
        "material_category.updated",
        "Material category updated",
    )
    MATERIAL_CATEGORY_ARCHIVED = (
        "material_category.archived",
        "Material category archived",
    )
    MATERIAL_CREATED = "material.created", "Material created"
    MATERIAL_UPDATED = "material.updated", "Material updated"
    MATERIAL_ARCHIVED = "material.archived", "Material archived"
    PROJECT_CREATED = "project.created", "Project created"
    PROJECT_ARCHIVED = "project.archived", "Project archived"
    PROJECT_SITE_CREATED = "project_site.created", "Project site created"
    PROJECT_PHASE_CREATED = "project_phase.created", "Project phase created"
    PROJECT_PHASE_STATUS_CHANGED = (
        "project_phase.status_changed",
        "Project phase status changed",
    )
    WBS_NODE_CREATED = "wbs_node.created", "WBS node created"
    WBS_NODE_UPDATED = "wbs_node.updated", "WBS node updated"
    WBS_NODE_ARCHIVED = "wbs_node.archived", "WBS node archived"
    ACTIVITY_CREATED = "activity.created", "Activity created"
    ACTIVITY_STATUS_CHANGED = "activity.status_changed", "Activity status changed"
    ACTIVITY_ARCHIVED = "activity.archived", "Activity archived"
    CONTRACT_CREATED = "contract.created", "Contract created"
    CONTRACT_UPDATED = "contract.updated", "Contract updated"
    CONTRACT_STATUS_CHANGED = "contract.status_changed", "Contract status changed"
    CONTRACT_ITEM_ADDED = "contract.item_added", "Contract item added"
    CONTRACT_AMENDMENT_APPROVED = (
        "contract.amendment_approved",
        "Contract amendment approved",
    )
    ESTIMATE_CREATED = "estimate.created", "Estimate created"
    ESTIMATE_ITEM_ADDED = "estimate.item_added", "Estimate item added"
    ESTIMATE_APPROVED = "estimate.approved", "Estimate approved"
    ESTIMATE_REVISION_CREATED = "estimate.revision_created", "Estimate revision created"
    ESTIMATE_REVISION_APPROVED = (
        "estimate.revision_approved",
        "Estimate revision approved",
    )
    EXPENSE_RECORDED = "expense.recorded", "Expense recorded"
    EXPENSE_VOIDED = "expense.voided", "Expense voided"
    EXPENSE_CATEGORY_CREATED = "expense_category.created", "Expense category created"
    EXPENSE_CATEGORY_ARCHIVED = "expense_category.archived", "Expense category archived"
    PAYMENT_RECORDED = "payment.recorded", "Payment recorded"
    PAYMENT_VOIDED = "payment.voided", "Payment voided"
    PAYMENT_ALLOCATION_CREATED = (
        "payment_allocation.created",
        "Payment allocation created",
    )
    PAYMENT_ALLOCATION_REVERSED = (
        "payment_allocation.reversed",
        "Payment allocation reversed",
    )
    DOCUMENT_UPLOADED = "document.uploaded", "Document uploaded"
    DOCUMENT_DOWNLOADED = "document.downloaded", "Document downloaded"
    DOCUMENT_ARCHIVED = "document.archived", "Document archived"
    DAILY_REPORT_CREATED = "daily_report.created", "Daily report created"
    DAILY_REPORT_SUBMITTED = "daily_report.submitted", "Daily report submitted"
    DAILY_REPORT_APPROVED = "daily_report.approved", "Daily report approved"
    DAILY_REPORT_LABOR_ADDED = "daily_report.labor_added", "Daily report labor added"
    DAILY_REPORT_EQUIPMENT_ADDED = (
        "daily_report.equipment_added",
        "Daily report equipment added",
    )
    DAILY_REPORT_MATERIAL_ADDED = (
        "daily_report.material_added",
        "Daily report material added",
    )
    DAILY_ACTIVITY_ADDED = "daily_activity.added", "Daily activity added"
    DELAY_EVENT_ADDED = "delay_event.added", "Delay event added"
    DEPARTMENT_CREATED = "department.created", "Department created"
    DEPARTMENT_ARCHIVED = "department.archived", "Department archived"
    POSITION_CREATED = "position.created", "Position created"
    POSITION_ARCHIVED = "position.archived", "Position archived"
    WORK_TEAM_CREATED = "work_team.created", "Work team created"
    WORK_TEAM_ARCHIVED = "work_team.archived", "Work team archived"
    EMPLOYEE_CREATED = "employee.created", "Employee created"
    EMPLOYEE_STATUS_CHANGED = "employee.status_changed", "Employee status changed"
    EMPLOYEE_ARCHIVED = "employee.archived", "Employee archived"
    EMPLOYEE_PROJECT_ASSIGNED = (
        "employee_project_assignment.created",
        "Employee assigned to project",
    )
    EMPLOYEE_PROJECT_ASSIGNMENT_STATUS_CHANGED = (
        "employee_project_assignment.status_changed",
        "Employee project assignment status changed",
    )
    MEMBERSHIP_INVITED = "membership.invited", "Membership invited"
    MEMBERSHIP_ACCEPTED = "membership.accepted", "Membership accepted"


class AuditEventQuerySet(models.QuerySet):
    """Prevent bulk mutation of immutable audit evidence."""

    def update(self, **kwargs: object) -> int:
        raise ValidationError("Audit events are immutable.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ValidationError("Audit events are immutable.")


class AuditEventManager(models.Manager.from_queryset(AuditEventQuerySet)):
    """Allow only normal single-event creation through the default manager."""

    def bulk_create(self, *args: object, **kwargs: object) -> list[models.Model]:
        raise ValidationError("Audit events must be created individually.")


class AuditEvent(UUIDModel, CreatedAtModel):
    """Immutable record of an important business action."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    action = models.CharField(max_length=64, choices=AuditAction.choices)
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    objects = AuditEventManager()

    class Meta:
        ordering = ["-created_at"]  # noqa: RUF012
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "-created_at"],
                name="audit_org_created_idx",
            ),
            models.Index(
                fields=["action", "-created_at"],
                name="audit_action_created_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.action} ({self.entity_type}:{self.entity_id})"

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("Audit events are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("Audit events are immutable.")
