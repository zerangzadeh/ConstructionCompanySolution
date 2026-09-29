from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.identifiers import canonicalize_lower_identifier
from core.models import TimeStampedModel, UUIDModel

from .registry import registry


def canonical_scope(scope: dict[str, Any]) -> tuple[dict[str, Any], str]:
    if not isinstance(scope, dict):
        raise ValidationError({"scope": "محدوده باید یک شیء JSON باشد."})
    normalized = {str(key): scope[key] for key in sorted(scope)}
    if any(not isinstance(value, (str, int, bool)) for value in normalized.values()):
        raise ValidationError(
            {"scope": "مقادیر محدوده باید scalar و declarative باشند."}
        )
    encoded = json.dumps(
        normalized, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    )
    return normalized, sha256(encoded.encode()).hexdigest()


class WorkflowVersionStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    PUBLISHED = "published", "منتشرشده"
    RETIRED = "retired", "بازنشسته"


class WorkflowInstanceStatus(models.TextChoices):
    ACTIVE = "active", "فعال"
    COMPLETED = "completed", "تکمیل‌شده"
    CANCELLED = "cancelled", "لغوشده"
    SUSPENDED = "suspended", "تعلیق‌شده"


class WorkflowStepInstanceStatus(models.TextChoices):
    ACTIVE = "active", "فعال"
    COMPLETED = "completed", "تکمیل‌شده"
    CANCELLED = "cancelled", "لغوشده"


class WorkItemStatus(models.TextChoices):
    OPEN = "open", "باز"
    CLAIMED = "claimed", "اخذشده"
    UNRESOLVED = "unresolved", "حل‌نشده"
    COMPLETED = "completed", "تکمیل‌شده"
    CANCELLED = "cancelled", "لغوشده"


class WorkItemAssignmentAction(models.TextChoices):
    ASSIGN = "assign", "تخصیص"
    CLAIM = "claim", "اخذ"
    RELEASE = "release", "آزادسازی"
    REASSIGN = "reassign", "تخصیص مجدد"
    RECOVER = "recover", "بازیابی"
    COMPLETE = "complete", "تکمیل"
    CANCEL = "cancel", "لغو"


class WorkflowType(UUIDModel, TimeStampedModel):
    code = models.CharField("کد", max_length=100, unique=True)
    name = models.CharField("عنوان", max_length=255)
    description = models.TextField("توضیحات", blank=True)
    subject_type = models.CharField("نوع موضوع", max_length=100)
    subject_adapter = models.CharField("آداپتور موضوع", max_length=100)
    allowed_scope_fields = models.JSONField("فیلدهای محدوده مجاز", default=list)
    is_active = models.BooleanField("فعال", default=True, db_index=True)

    class Meta:
        ordering = ["code"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        specification = registry.workflow_types.get(self.code)
        if specification is None:
            raise ValidationError({"code": "نوع گردش‌کار در کد ثبت نشده است."})
        if self.subject_type != specification.subject_type:
            raise ValidationError(
                {"subject_type": "نوع موضوع با registry مطابقت ندارد."}
            )
        if self.subject_adapter != specification.subject_adapter:
            raise ValidationError({"subject_adapter": "آداپتور موضوع ثبت‌شده نیست."})
        if set(self.allowed_scope_fields) != set(specification.allowed_scope_fields):
            raise ValidationError(
                {"allowed_scope_fields": "محدوده با registry مطابقت ندارد."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        self.code = canonicalize_lower_identifier(self.code)
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class WorkflowTemplate(UUIDModel, TimeStampedModel):
    workflow_type = models.ForeignKey(
        WorkflowType, on_delete=models.PROTECT, related_name="templates"
    )
    code = models.SlugField("کد", max_length=100)
    name = models.CharField("عنوان", max_length=255)
    description = models.TextField("توضیحات", blank=True)
    configuration = models.JSONField("پیکربندی", default=dict)
    is_active = models.BooleanField("فعال", default=True, db_index=True)

    class Meta:
        ordering = ["code"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["workflow_type", "code"],
                name="workflow_template_type_code_uniq",
            )
        ]

    def clean(self) -> None:
        super().clean()
        from .validators import validate_configuration_payload

        validate_configuration_payload(
            self.configuration, workflow_type_code=self.workflow_type.code
        )

    def save(self, *args: object, **kwargs: object) -> None:
        self.code = canonicalize_lower_identifier(self.code)
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class WorkflowDefinition(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="workflow_definitions",
    )
    workflow_type = models.ForeignKey(
        WorkflowType, on_delete=models.PROTECT, related_name="definitions"
    )
    code = models.SlugField("کد", max_length=100)
    name = models.CharField("عنوان", max_length=255)
    description = models.TextField("توضیحات", blank=True)
    scope = models.JSONField("محدوده", default=dict, blank=True)
    scope_key = models.CharField("کلید محدوده", max_length=64, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="workflow_definitions_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="workflow_definitions_updated",
    )

    class Meta:
        ordering = ["code"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "workflow_type", "code"],
                name="workflow_definition_org_type_code_uniq",
            ),
            models.UniqueConstraint(
                fields=["organization", "workflow_type", "scope_key"],
                name="workflow_definition_org_type_scope_uniq",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "workflow_type"],
                name="workflow_def_org_type_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        normalized, scope_key = canonical_scope(self.scope)
        allowed = set(self.workflow_type.allowed_scope_fields)
        unknown = set(normalized) - allowed
        if unknown:
            raise ValidationError(
                {"scope": f"فیلدهای محدوده ثبت‌نشده: {', '.join(sorted(unknown))}"}
            )
        self.scope = normalized
        self.scope_key = scope_key

    def save(self, *args: object, **kwargs: object) -> None:
        self.code = canonicalize_lower_identifier(self.code)
        self.full_clean()
        if (
            self.pk
            and self.versions.filter(status=WorkflowVersionStatus.PUBLISHED).exists()
        ):
            previous = type(self).objects.get(pk=self.pk)
            if (
                previous.workflow_type_id != self.workflow_type_id
                or previous.scope_key != self.scope_key
                or previous.code != self.code
            ):
                raise ValidationError("هویت و محدوده تعریف منتشرشده قابل تغییر نیست.")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class VersionQuerySet(models.QuerySet):
    def update(self, **kwargs: object) -> int:
        if self.exclude(status=WorkflowVersionStatus.DRAFT).exists():
            raise ValidationError("نسخه منتشرشده یا بازنشسته قابل تغییر نیست.")
        return super().update(**kwargs)

    def delete(self) -> tuple[int, dict[str, int]]:
        if self.exclude(status=WorkflowVersionStatus.DRAFT).exists():
            raise ValidationError("نسخه منتشرشده یا بازنشسته قابل حذف نیست.")
        return super().delete()


class WorkflowVersion(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="workflow_versions",
    )
    definition = models.ForeignKey(
        WorkflowDefinition, on_delete=models.PROTECT, related_name="versions"
    )
    version_number = models.PositiveIntegerField("شماره نسخه")
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=WorkflowVersionStatus.choices,
        default=WorkflowVersionStatus.DRAFT,
        db_index=True,
    )
    change_summary = models.TextField("خلاصه تغییر", blank=True)
    validation_report = models.JSONField("گزارش اعتبارسنجی", default=list, blank=True)
    validated_at = models.DateTimeField("زمان اعتبارسنجی", null=True, blank=True)
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="workflow_versions_validated",
    )
    published_at = models.DateTimeField("زمان انتشار", null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="workflow_versions_published",
    )
    retired_at = models.DateTimeField("زمان بازنشستگی", null=True, blank=True)
    retired_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="workflow_versions_retired",
    )

    objects = models.Manager.from_queryset(VersionQuerySet)()

    class Meta:
        ordering = ["version_number"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "definition", "version_number"],
                name="workflow_version_org_def_number_uniq",
            ),
            models.UniqueConstraint(
                fields=["definition"],
                condition=Q(status=WorkflowVersionStatus.PUBLISHED),
                name="workflow_version_one_published_per_def",
            ),
            models.CheckConstraint(
                condition=Q(version_number__gte=1), name="workflow_version_number_gte_1"
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "definition", "status"],
                name="workflow_ver_org_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if (
            self.definition_id
            and self.organization_id != self.definition.organization_id
        ):
            raise ValidationError(
                {"definition": "تعریف گردش‌کار متعلق به سازمان دیگری است."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values("status").first()
            if previous and previous["status"] != WorkflowVersionStatus.DRAFT:
                raise ValidationError("نسخه منتشرشده یا بازنشسته قابل تغییر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        if self.status != WorkflowVersionStatus.DRAFT:
            raise ValidationError("نسخه منتشرشده یا بازنشسته قابل حذف نیست.")
        return super().delete(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.definition} v{self.version_number}"


class DraftConfigurationQuerySet(models.QuerySet):
    def update(self, **kwargs: object) -> int:
        if self.exclude(version__status=WorkflowVersionStatus.DRAFT).exists():
            raise ValidationError("پیکربندی نسخه منتشرشده قابل تغییر نیست.")
        return super().update(**kwargs)

    def delete(self) -> tuple[int, dict[str, int]]:
        if self.exclude(version__status=WorkflowVersionStatus.DRAFT).exists():
            raise ValidationError("پیکربندی نسخه منتشرشده قابل حذف نیست.")
        return super().delete()


class DraftOwnedModel(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    version = models.ForeignKey(WorkflowVersion, on_delete=models.CASCADE)

    objects = models.Manager.from_queryset(DraftConfigurationQuerySet)()

    class Meta:
        abstract = True

    def clean(self) -> None:
        super().clean()
        if self.version_id and self.organization_id != self.version.organization_id:
            raise ValidationError({"version": "نسخه متعلق به سازمان دیگری است."})
        if self.version_id and self.version.status != WorkflowVersionStatus.DRAFT:
            raise ValidationError("تنها پیکربندی نسخه پیش‌نویس قابل تغییر است.")

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        if self.version.status != WorkflowVersionStatus.DRAFT:
            raise ValidationError("پیکربندی نسخه منتشرشده قابل حذف نیست.")
        return super().delete(*args, **kwargs)


class WorkflowStepDefinition(DraftOwnedModel):
    version = models.ForeignKey(
        WorkflowVersion, on_delete=models.CASCADE, related_name="steps"
    )
    key = models.SlugField("کلید", max_length=100)
    name = models.CharField("عنوان", max_length=255)
    step_type = models.CharField("نوع گام", max_length=100)
    is_start = models.BooleanField("گام شروع", default=False)
    is_terminal = models.BooleanField("گام پایانی", default=False)
    domain_command = models.CharField("فرمان دامنه", max_length=150, blank=True)
    required_permission = models.CharField("مجوز لازم", max_length=100, blank=True)
    configuration = models.JSONField("پیکربندی", default=dict, blank=True)

    class Meta:
        ordering = ["key"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "version", "key"],
                name="workflow_step_org_ver_key_uniq",
            )
        ]

    def clean(self) -> None:
        super().clean()
        specification = registry.step_types.get(self.step_type)
        if specification is None:
            raise ValidationError({"step_type": "نوع گام ثبت نشده است."})
        specification.schema.validate(self.configuration, label="پیکربندی گام")


class WorkflowTransitionDefinition(DraftOwnedModel):
    version = models.ForeignKey(
        WorkflowVersion, on_delete=models.CASCADE, related_name="transitions"
    )
    source_step = models.ForeignKey(
        WorkflowStepDefinition,
        on_delete=models.CASCADE,
        related_name="outgoing_transitions",
    )
    target_step = models.ForeignKey(
        WorkflowStepDefinition,
        on_delete=models.PROTECT,
        related_name="incoming_transitions",
    )
    outcome = models.SlugField("نتیجه", max_length=100)
    domain_command = models.CharField("فرمان دامنه", max_length=150, blank=True)
    required_permission = models.CharField("مجوز لازم", max_length=100, blank=True)
    priority = models.PositiveSmallIntegerField("اولویت", default=0)
    is_default = models.BooleanField("مسیر پیش‌فرض", default=False)

    class Meta:
        ordering = ["priority", "outcome"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "version", "source_step", "outcome"],
                name="workflow_transition_org_source_outcome_uniq",
            ),
            models.CheckConstraint(
                condition=~Q(source_step=models.F("target_step")),
                name="workflow_transition_no_self_loop",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        for field_name, step in (
            ("source_step", self.source_step),
            ("target_step", self.target_step),
        ):
            if (
                step.version_id != self.version_id
                or step.organization_id != self.organization_id
            ):
                raise ValidationError(
                    {field_name: "گام انتقال متعلق به همین نسخه و سازمان نیست."}
                )


class WorkflowCondition(DraftOwnedModel):
    version = models.ForeignKey(
        WorkflowVersion, on_delete=models.CASCADE, related_name="conditions"
    )
    transition = models.ForeignKey(
        WorkflowTransitionDefinition,
        on_delete=models.CASCADE,
        related_name="conditions",
    )
    condition_type = models.CharField("نوع شرط", max_length=100)
    configuration = models.JSONField("پیکربندی", default=dict, blank=True)
    order = models.PositiveSmallIntegerField("ترتیب", default=0)
    negate = models.BooleanField("نقیض", default=False)

    class Meta:
        ordering = ["order"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "transition", "order"],
                name="workflow_condition_org_transition_order_uniq",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if (
            self.transition.version_id != self.version_id
            or self.transition.organization_id != self.organization_id
        ):
            raise ValidationError(
                {"transition": "انتقال متعلق به همین نسخه و سازمان نیست."}
            )
        specification = registry.condition_types.get(self.condition_type)
        if specification is None:
            raise ValidationError({"condition_type": "نوع شرط ثبت نشده است."})
        specification.schema.validate(self.configuration, label="پیکربندی شرط")


class WorkflowRoutingRule(DraftOwnedModel):
    version = models.ForeignKey(
        WorkflowVersion, on_delete=models.CASCADE, related_name="routing_rules"
    )
    step = models.ForeignKey(
        WorkflowStepDefinition, on_delete=models.CASCADE, related_name="routing_rules"
    )
    resolver_type = models.CharField("نوع مسیریاب", max_length=100)
    configuration = models.JSONField("پیکربندی", default=dict, blank=True)
    order = models.PositiveSmallIntegerField("ترتیب", default=0)
    is_fallback = models.BooleanField("مسیر جایگزین", default=False)

    class Meta:
        ordering = ["order"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "step", "order"],
                name="workflow_routing_org_step_order_uniq",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if (
            self.step.version_id != self.version_id
            or self.step.organization_id != self.organization_id
        ):
            raise ValidationError(
                {"step": "گام مسیریابی متعلق به همین نسخه و سازمان نیست."}
            )
        specification = registry.routing_resolvers.get(self.resolver_type)
        if specification is None:
            raise ValidationError({"resolver_type": "نوع مسیریاب ثبت نشده است."})
        specification.schema.validate(self.configuration, label="پیکربندی مسیریابی")


class RuntimeStateQuerySet(models.QuerySet):
    terminal_states: tuple[str, ...] = ()

    def update(self, **kwargs: object) -> int:
        if self.filter(status__in=self.terminal_states).exists():
            raise ValidationError("سابقه تکمیل‌شده یا لغوشده قابل تغییر نیست.")
        return super().update(**kwargs)

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ValidationError("سابقه runtime قابل حذف نیست؛ از لغو استفاده کنید.")


class WorkflowInstanceQuerySet(RuntimeStateQuerySet):
    terminal_states = (
        WorkflowInstanceStatus.COMPLETED,
        WorkflowInstanceStatus.CANCELLED,
    )


class WorkflowInstance(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="workflow_instances",
    )
    definition = models.ForeignKey(
        WorkflowDefinition, on_delete=models.PROTECT, related_name="instances"
    )
    version = models.ForeignKey(
        WorkflowVersion, on_delete=models.PROTECT, related_name="instances"
    )
    subject_type = models.CharField("نوع موضوع", max_length=100)
    subject_id = models.UUIDField("شناسه عمومی موضوع")
    subject_context = models.JSONField("زمینه ثبت‌شده موضوع", default=dict, blank=True)
    processed_operations = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=WorkflowInstanceStatus.choices,
        default=WorkflowInstanceStatus.ACTIVE,
        db_index=True,
    )
    idempotency_key = models.CharField("کلید تکرارپذیری", max_length=128)
    started_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="workflow_instances_started",
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspension_reason = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)

    objects = models.Manager.from_queryset(WorkflowInstanceQuerySet)()

    class Meta:
        ordering = ["-created_at"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="workflow_inst_org_idem_uniq",
            ),
            models.UniqueConstraint(
                fields=["organization", "definition", "subject_type", "subject_id"],
                condition=Q(
                    status__in=(
                        WorkflowInstanceStatus.ACTIVE,
                        WorkflowInstanceStatus.SUSPENDED,
                    )
                ),
                name="workflow_inst_one_open_subject",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "status", "subject_type"],
                name="workflow_inst_org_state_idx",
            ),
            models.Index(
                fields=["organization", "subject_type", "subject_id"],
                name="workflow_inst_org_subject_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.version_id:
            if (
                self.organization_id != self.version.organization_id
                or self.definition_id != self.version.definition_id
            ):
                raise ValidationError(
                    {"version": "نسخه متعلق به همین تعریف و سازمان نیست."}
                )
            if (
                self._state.adding
                and self.version.status != WorkflowVersionStatus.PUBLISHED
            ):
                raise ValidationError({"version": "فقط نسخه منتشرشده قابل اجرا است."})
            expected_type = self.version.definition.workflow_type.subject_type
            if self.subject_type != expected_type:
                raise ValidationError(
                    {"subject_type": "نوع موضوع با نسخه مطابقت ندارد."}
                )
        if self.subject_type not in {
            item.subject_type for item in registry.subject_adapters.values()
        }:
            raise ValidationError({"subject_type": "نوع موضوع در کد ثبت نشده است."})
        if (
            self.started_by_id
            and self.started_by.organization_id != self.organization_id
        ):
            raise ValidationError(
                {"started_by": "عضویت آغازکننده متعلق به سازمان نیست."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values("status").first()
            if previous and previous["status"] in (
                WorkflowInstanceStatus.COMPLETED,
                WorkflowInstanceStatus.CANCELLED,
            ):
                raise ValidationError("نمونه تکمیل‌شده یا لغوشده تغییرناپذیر است.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("سابقه runtime قابل حذف نیست؛ از لغو استفاده کنید.")


class WorkflowStepInstanceQuerySet(RuntimeStateQuerySet):
    terminal_states = (
        WorkflowStepInstanceStatus.COMPLETED,
        WorkflowStepInstanceStatus.CANCELLED,
    )


class WorkflowStepInstance(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="workflow_step_instances",
    )
    instance = models.ForeignKey(
        WorkflowInstance, on_delete=models.PROTECT, related_name="step_instances"
    )
    step_definition = models.ForeignKey(
        WorkflowStepDefinition,
        on_delete=models.PROTECT,
        related_name="runtime_instances",
    )
    sequence = models.PositiveIntegerField("ترتیب اجرا")
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=WorkflowStepInstanceStatus.choices,
        default=WorkflowStepInstanceStatus.ACTIVE,
        db_index=True,
    )
    activated_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    outcome = models.CharField(max_length=100, blank=True)

    objects = models.Manager.from_queryset(WorkflowStepInstanceQuerySet)()

    class Meta:
        ordering = ["sequence"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "instance", "sequence"],
                name="workflow_step_inst_org_seq_uniq",
            ),
            models.UniqueConstraint(
                fields=["organization", "instance"],
                condition=Q(status=WorkflowStepInstanceStatus.ACTIVE),
                name="workflow_step_inst_one_active",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "instance", "status"],
                name="workflow_step_org_state_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.instance_id and self.organization_id != self.instance.organization_id:
            raise ValidationError({"instance": "نمونه متعلق به سازمان دیگری است."})
        if self._state.adding and self.step_definition_id:
            if self.step_definition.organization_id != self.organization_id:
                raise ValidationError(
                    {"step_definition": "گام متعلق به سازمان دیگری است."}
                )
            if self.step_definition.version_id != self.instance.version_id:
                raise ValidationError(
                    {"step_definition": "گام متعلق به نسخه فعال نمونه نیست."}
                )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values("status").first()
            if previous and previous["status"] in (
                WorkflowStepInstanceStatus.COMPLETED,
                WorkflowStepInstanceStatus.CANCELLED,
            ):
                raise ValidationError("سابقه گام نهایی‌شده تغییرناپذیر است.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("سابقه گام runtime قابل حذف نیست.")


class WorkItemQuerySet(RuntimeStateQuerySet):
    terminal_states = (WorkItemStatus.COMPLETED, WorkItemStatus.CANCELLED)


class WorkItem(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="workflow_work_items",
    )
    instance = models.ForeignKey(
        WorkflowInstance, on_delete=models.PROTECT, related_name="work_items"
    )
    step_instance = models.ForeignKey(
        WorkflowStepInstance, on_delete=models.PROTECT, related_name="work_items"
    )
    action_key = models.CharField("کلید اقدام", max_length=150)
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=WorkItemStatus.choices,
        default=WorkItemStatus.OPEN,
        db_index=True,
    )
    required_permission = models.CharField(max_length=100, blank=True)
    current_assignee = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assigned_work_items",
    )
    assigned_via_position = models.ForeignKey(
        "workforce.EmployeePositionAssignment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="qualified_work_items",
    )
    due_at = models.DateTimeField(null=True, blank=True)
    priority = models.PositiveSmallIntegerField(default=0)
    routing_basis = models.JSONField(default=list, blank=True)
    unresolved_at = models.DateTimeField(null=True, blank=True)
    unresolved_reason = models.TextField(blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    completion_outcome = models.CharField(max_length=100, blank=True)
    idempotency_key = models.CharField(max_length=128)

    objects = models.Manager.from_queryset(WorkItemQuerySet)()

    class Meta:
        ordering = ["-priority", "due_at", "created_at"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "step_instance", "action_key"],
                name="workflow_item_org_step_action_uniq",
            ),
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="workflow_item_org_idem_uniq",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "status", "current_assignee", "due_at"],
                name="workflow_item_org_queue_idx",
            ),
            models.Index(
                fields=["organization", "instance", "status"],
                name="workflow_item_org_inst_idx",
            ),
        ]

    @property
    def is_overdue(self) -> bool:
        return bool(
            self.status
            in (
                WorkItemStatus.OPEN,
                WorkItemStatus.CLAIMED,
                WorkItemStatus.UNRESOLVED,
            )
            and self.due_at
            and self.due_at < timezone.now()
        )

    def clean(self) -> None:
        super().clean()
        if self.instance_id and self.organization_id != self.instance.organization_id:
            raise ValidationError({"instance": "نمونه متعلق به سازمان دیگری است."})
        if self.step_instance_id and (
            self.organization_id != self.step_instance.organization_id
            or self.instance_id != self.step_instance.instance_id
        ):
            raise ValidationError({"step_instance": "گام متعلق به همین نمونه نیست."})
        for field_name in ("current_assignee", "assigned_via_position"):
            value = getattr(self, field_name, None)
            if value is not None and value.organization_id != self.organization_id:
                raise ValidationError({field_name: "مرجع متعلق به سازمان دیگری است."})

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values("status").first()
            if previous and previous["status"] in (
                WorkItemStatus.COMPLETED,
                WorkItemStatus.CANCELLED,
            ):
                raise ValidationError("کار نهایی‌شده تغییرناپذیر است.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("سابقه کار runtime قابل حذف نیست.")


class WorkItemCandidateQuerySet(models.QuerySet):
    def update(self, **kwargs: object) -> int:
        if self.filter(
            work_item__status__in=(WorkItemStatus.COMPLETED, WorkItemStatus.CANCELLED)
        ).exists():
            raise ValidationError("نامزدهای کار نهایی‌شده تغییرناپذیرند.")
        return super().update(**kwargs)

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ValidationError("سابقه نامزد کار قابل حذف نیست.")


class WorkItemCandidate(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="workflow_work_item_candidates",
    )
    work_item = models.ForeignKey(
        WorkItem, on_delete=models.PROTECT, related_name="candidates"
    )
    membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="candidate_work_items",
    )
    qualifying_position_assignment = models.ForeignKey(
        "workforce.EmployeePositionAssignment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="work_item_candidates",
    )
    routing_basis = models.JSONField(default=list)
    is_active = models.BooleanField(default=True, db_index=True)
    removed_at = models.DateTimeField(null=True, blank=True)
    removal_reason = models.TextField(blank=True)

    objects = models.Manager.from_queryset(WorkItemCandidateQuerySet)()

    class Meta:
        ordering = ["created_at"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "work_item", "membership"],
                condition=Q(is_active=True),
                name="workflow_candidate_one_active",
            )
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "membership", "is_active"],
                name="workflow_cand_org_member_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        references = {
            "work_item": self.work_item if self.work_item_id else None,
            "membership": self.membership if self.membership_id else None,
            "qualifying_position_assignment": (
                self.qualifying_position_assignment
                if self.qualifying_position_assignment_id
                else None
            ),
        }
        for field_name, value in references.items():
            if value is not None and value.organization_id != self.organization_id:
                raise ValidationError({field_name: "مرجع متعلق به سازمان دیگری است."})

    def save(self, *args: object, **kwargs: object) -> None:
        if self.work_item_id and self.work_item.status in (
            WorkItemStatus.COMPLETED,
            WorkItemStatus.CANCELLED,
        ):
            raise ValidationError("نامزدهای کار نهایی‌شده تغییرناپذیرند.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("سابقه نامزد کار قابل حذف نیست.")


class ImmutableHistoryQuerySet(models.QuerySet):
    def update(self, **kwargs: object) -> int:
        raise ValidationError("تاریخچه تخصیص قابل تغییر نیست.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ValidationError("تاریخچه تخصیص قابل حذف نیست.")


class WorkItemAssignmentHistory(UUIDModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="workflow_assignment_history",
    )
    work_item = models.ForeignKey(
        WorkItem, on_delete=models.PROTECT, related_name="assignment_history"
    )
    action = models.CharField(max_length=20, choices=WorkItemAssignmentAction.choices)
    actor_membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="workflow_assignment_actions",
    )
    from_membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="workflow_assignments_released",
    )
    to_membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="workflow_assignments_received",
    )
    qualifying_position_assignment = models.ForeignKey(
        "workforce.EmployeePositionAssignment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="workflow_assignment_history",
    )
    permission_code = models.CharField(max_length=100, blank=True)
    reason = models.TextField(blank=True)
    previous_state = models.CharField(max_length=20)
    new_state = models.CharField(max_length=20)
    outcome = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    idempotency_key = models.CharField(max_length=128)
    occurred_at = models.DateTimeField(default=timezone.now)

    objects = models.Manager.from_queryset(ImmutableHistoryQuerySet)()

    class Meta:
        ordering = ["occurred_at", "pk"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "work_item", "idempotency_key"],
                name="workflow_hist_org_item_idem_uniq",
            )
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "work_item", "occurred_at"],
                name="workflow_hist_org_item_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        references = {
            "work_item": self.work_item if self.work_item_id else None,
            "actor_membership": (
                self.actor_membership if self.actor_membership_id else None
            ),
            "from_membership": self.from_membership
            if self.from_membership_id
            else None,
            "to_membership": self.to_membership if self.to_membership_id else None,
            "qualifying_position_assignment": (
                self.qualifying_position_assignment
                if self.qualifying_position_assignment_id
                else None
            ),
        }
        for field_name, value in references.items():
            if value is not None and value.organization_id != self.organization_id:
                raise ValidationError({field_name: "مرجع متعلق به سازمان دیگری است."})

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("تاریخچه تخصیص append-only است.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("تاریخچه تخصیص قابل حذف نیست.")


class WorkflowDelegation(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="workflow_delegations",
    )
    delegator = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="workflow_delegations_given",
    )
    delegate = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="workflow_delegations_received",
    )
    workflow_type = models.ForeignKey(
        WorkflowType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="delegations",
    )
    permission = models.ForeignKey(
        "organizations.BusinessPermission",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="workflow_delegations",
    )
    scope = models.JSONField(default=dict, blank=True)
    idempotency_key = models.CharField(max_length=128)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    reason = models.TextField()
    created_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="workflow_delegations_created",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="workflow_delegations_revoked",
    )
    revoke_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-starts_at"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="workflow_deleg_org_idem_uniq",
            ),
            models.CheckConstraint(
                condition=~Q(delegator=models.F("delegate")),
                name="workflow_delegation_not_self",
            ),
            models.CheckConstraint(
                condition=Q(ends_at__gt=models.F("starts_at")),
                name="workflow_delegation_date_order",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "delegator", "starts_at", "ends_at"],
                name="workflow_deleg_org_date_idx",
            ),
            models.Index(
                fields=["organization", "delegate", "revoked_at"],
                name="workflow_deleg_org_recv_idx",
            ),
        ]

    @property
    def is_effective(self) -> bool:
        now = timezone.now()
        return self.revoked_at is None and self.starts_at <= now < self.ends_at

    def clean(self) -> None:
        super().clean()
        for field_name in ("delegator", "delegate", "created_by", "revoked_by"):
            value = getattr(self, field_name, None)
            if value is not None and value.organization_id != self.organization_id:
                raise ValidationError({field_name: "عضویت متعلق به سازمان دیگری است."})
        if self.ends_at and self.starts_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "پایان واگذاری باید پس از شروع باشد."})
        if not self.reason.strip():
            raise ValidationError({"reason": "دلیل واگذاری الزامی است."})
        normalized_scope, _ = canonical_scope(self.scope)
        if normalized_scope and not self.workflow_type_id:
            raise ValidationError({"scope": "محدوده واگذاری به نوع گردش‌کار نیاز دارد."})
        if self.workflow_type_id:
            unknown = set(normalized_scope) - set(
                self.workflow_type.allowed_scope_fields
            )
            if unknown:
                raise ValidationError({"scope": "محدوده واگذاری ثبت نشده است."})
        self.scope = normalized_scope

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            immutable_fields = (
                "organization_id",
                "delegator_id",
                "delegate_id",
                "workflow_type_id",
                "permission_id",
                "scope",
                "starts_at",
                "ends_at",
                "reason",
                "created_by_id",
            )
            if any(
                getattr(previous, name) != getattr(self, name)
                for name in immutable_fields
            ):
                raise ValidationError("واگذاری فقط قابل لغو است و قابل بازنویسی نیست.")
        self.full_clean()
        super().save(*args, **kwargs)
