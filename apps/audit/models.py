import uuid

from django.conf import settings
from django.db import models


class AuditAction(models.TextChoices):
    ORGANIZATION_CREATED = "organization.created", "Organization created"
    PROJECT_CREATED = "project.created", "Project created"
    PROJECT_ARCHIVED = "project.archived", "Project archived"
    PROJECT_SITE_CREATED = "project_site.created", "Project site created"
    CONTRACT_CREATED = "contract.created", "Contract created"
    ESTIMATE_CREATED = "estimate.created", "Estimate created"
    ESTIMATE_ITEM_ADDED = "estimate.item_added", "Estimate item added"
    ESTIMATE_APPROVED = "estimate.approved", "Estimate approved"
    EXPENSE_RECORDED = "expense.recorded", "Expense recorded"
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
    MEMBERSHIP_INVITED = "membership.invited", "Membership invited"
    MEMBERSHIP_ACCEPTED = "membership.accepted", "Membership accepted"


class AuditEvent(models.Model):
    """Immutable record of an important business action."""

    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )
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
    created_at = models.DateTimeField(auto_now_add=True)

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
