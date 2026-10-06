"""P9-S06–S11 shared inspection mechanics with profile-owned HSE/QA meaning."""
# ruff: noqa: RUF012

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.documents.models import DocumentVersion
from core.models import CreatedAtModel, TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class ControlProfile(models.TextChoices):
    HSE = "hse", "HSE"
    QA_QC = "qa_qc", "QA/QC"


class TemplateStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    UNDER_REVIEW = "under_review", "در بررسی"
    PUBLISHED = "published", "منتشرشده"
    RETIRED = "retired", "بازنشسته"


class InspectionStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    SCHEDULED = "scheduled", "برنامه‌ریزی‌شده"
    IN_PROGRESS = "in_progress", "در حال اجرا"
    SUBMITTED = "submitted", "ارسال‌شده"
    UNDER_REVIEW = "under_review", "در بررسی"
    PASSED = "passed", "قبول"
    CONDITIONAL = "conditional", "قبول مشروط"
    FAILED = "failed", "ردشده"
    CANCELLED = "cancelled", "لغوشده"
    SUPERSEDED = "superseded", "جایگزین‌شده"


class FindingStatus(models.TextChoices):
    RECORDED = "recorded", "ثبت‌شده"
    TRIAGED = "triaged", "طبقه‌بندی‌شده"
    ASSIGNED = "assigned", "تخصیص‌یافته"
    CORRECTION_IN_PROGRESS = "correction_in_progress", "اصلاح در حال انجام"
    PENDING_VERIFICATION = "pending_verification", "در انتظار راستی‌آزمایی"
    VERIFIED = "verified", "راستی‌آزمایی‌شده"
    CLOSED = "closed", "بسته‌شده"
    DISMISSED = "dismissed", "مختومه بدون اقدام"


class PermitStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    SUBMITTED = "submitted", "ارسال‌شده"
    UNDER_REVIEW = "under_review", "در بررسی"
    ISSUED = "issued", "صادرشده"
    SUSPENDED = "suspended", "تعلیق‌شده"
    EXPIRED = "expired", "منقضی"
    REVOKED = "revoked", "ابطال‌شده"
    CANCELLED = "cancelled", "لغوشده"
    SUPERSEDED = "superseded", "جایگزین‌شده"


class TestStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    REQUESTED = "requested", "درخواست‌شده"
    SCHEDULED = "scheduled", "برنامه‌ریزی‌شده"
    IN_EXECUTION = "in_execution", "در حال اجرا"
    RESULT_ENTERED = "result_entered", "نتیجه ثبت‌شده"
    UNDER_REVIEW = "under_review", "در بررسی"
    ACCEPTED = "accepted", "پذیرفته‌شده"
    REJECTED = "rejected", "ردشده"
    INVALIDATED = "invalidated", "بی‌اعتبارشده"
    CANCELLED = "cancelled", "لغوشده"
    SUPERSEDED = "superseded", "جایگزین‌شده"


class NcrStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    ISSUED = "issued", "صادرشده"
    DISPOSITION_PENDING = "disposition_pending", "در انتظار تعیین تکلیف"
    ACTION_IN_PROGRESS = "action_in_progress", "اقدام در حال انجام"
    PENDING_VERIFICATION = "pending_verification", "در انتظار راستی‌آزمایی"
    VERIFIED = "verified", "راستی‌آزمایی‌شده"
    CLOSED = "closed", "بسته‌شده"
    VOIDED = "voided", "باطل‌شده"


class CapaType(models.TextChoices):
    CORRECTIVE = "corrective", "اقدام اصلاحی"
    PREVENTIVE = "preventive", "اقدام پیشگیرانه"


class CapaStatus(models.TextChoices):
    PROPOSED = "proposed", "پیشنهادشده"
    APPROVED = "approved", "تأییدشده"
    ASSIGNED = "assigned", "تخصیص‌یافته"
    IN_PROGRESS = "in_progress", "در حال اجرا"
    PENDING_VERIFICATION = "pending_verification", "در انتظار راستی‌آزمایی"
    VERIFIED = "verified", "راستی‌آزمایی‌شده"
    EFFECTIVENESS_PENDING = "effectiveness_pending", "در انتظار ارزیابی اثربخشی"
    EFFECTIVE = "effective", "اثربخش"
    INEFFECTIVE = "ineffective", "غیراثربخش"
    CLOSED = "closed", "بسته‌شده"
    REJECTED = "rejected", "ردشده"
    CANCELLED = "cancelled", "لغوشده"


class EvidencePurpose(models.TextChoices):
    EXECUTION = "execution", "اجرای بازرسی"
    PERMIT = "permit", "مجوز"
    TEST = "test", "آزمون"
    FINDING = "finding", "یافته"
    NCR = "ncr", "عدم انطباق"
    IMPLEMENTATION = "implementation", "اجرای اقدام"
    VERIFICATION = "verification", "راستی‌آزمایی"
    EFFECTIVENESS = "effectiveness", "اثربخشی"
    CLOSURE = "closure", "بستن"


class ScopedControlModel(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="+"
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="+"
    )
    site = models.ForeignKey(
        "projects.ProjectSite",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    profile = models.CharField(
        max_length=10, choices=ControlProfile.choices, db_index=True
    )

    class Meta:
        abstract = True

    def validate_scope(self) -> None:
        relations = {"project": self.project}
        if self.site_id:
            relations["site"] = self.site
            if self.site.project_id != self.project_id:
                raise ValidationError({"site": "کارگاه باید متعلق به پروژه باشد."})
        validate_related_organizations(self, **relations)

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding and hasattr(self, "status"):
            previous_status = (
                type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
            )
            if previous_status != self.status and not getattr(
                self, "_service_transition", False
            ):
                raise ValidationError("تغییر وضعیت فقط از طریق سرویس چرخه عمر مجاز است.")
            if previous_status != "draft" and not getattr(
                self, "_service_transition", False
            ):
                raise ValidationError("رکورد ارسال‌شده یا نهایی فقط با سابقه کنترل‌شده تغییر می‌کند.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("رکورد کنترل HSE/QA بخشی از سابقه است و حذف نمی‌شود.")


class InspectionTemplate(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="inspection_templates",
    )
    profile = models.CharField(
        max_length=10, choices=ControlProfile.choices, db_index=True
    )
    code = models.CharField(max_length=50)
    title = models.CharField(max_length=200)
    status = models.CharField(
        max_length=20, choices=TemplateStatus.choices, default=TemplateStatus.DRAFT
    )
    current_version = models.ForeignKey(
        "InspectionTemplateVersion",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="inspection_templates_created",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "profile", "code"],
                name="compliance_template_code_uq",
            )
        ]

    def clean(self) -> None:
        self.code = self.code.strip().upper()
        self.title = self.title.strip()
        if not self.code or not self.title:
            raise ValidationError("کد و عنوان الگوی بازرسی الزامی است.")
        if self.current_version_id and self.current_version.template_id != self.pk:
            raise ValidationError("نسخه جاری باید متعلق به همین الگو باشد.")


class InspectionTemplateVersion(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="+"
    )
    template = models.ForeignKey(
        InspectionTemplate, on_delete=models.PROTECT, related_name="versions"
    )
    version_number = models.PositiveIntegerField()
    checklist = models.JSONField(default=list)
    required_evidence = models.JSONField(default=list, blank=True)
    outcome_rules = models.JSONField(default=dict)
    source_references = models.JSONField(default=list)
    canonical_hash = models.CharField(max_length=64)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="inspection_template_versions_published",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["template", "version_number"],
                name="compliance_template_version_uq",
            )
        ]
        ordering = ["version_number"]

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("نسخه منتشرشده الگو تغییرپذیر نیست.")
        validate_related_organizations(self, template=self.template)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("نسخه منتشرشده الگو حذف نمی‌شود.")


class Inspection(ScopedControlModel):
    number = models.CharField(max_length=50)
    template_version = models.ForeignKey(
        InspectionTemplateVersion, on_delete=models.PROTECT, related_name="inspections"
    )
    title = models.CharField(max_length=200)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    responses = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=24,
        choices=InspectionStatus.choices,
        default=InspectionStatus.DRAFT,
        db_index=True,
    )
    template_snapshot_hash = models.CharField(max_length=64)
    canonical_hash = models.CharField(max_length=64, blank=True)
    operation_key = models.UUIDField(default=uuid.uuid4)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="inspections_created",
    )
    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="inspections_assigned",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="inspections_submitted",
        null=True,
        blank=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="inspections_reviewed",
        null=True,
        blank=True,
    )
    review_reason = models.TextField(blank=True)
    replaces = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="reinspections",
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "profile", "number"],
                name="compliance_inspection_number_uq",
            ),
            models.UniqueConstraint(
                fields=["organization", "created_by", "operation_key"],
                name="compliance_inspection_op_uq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organization", "project", "site", "profile", "status"],
                name="compliance_inspect_scope_idx",
            )
        ]

    def clean(self) -> None:
        self.validate_scope()
        validate_related_organizations(self, template_version=self.template_version)
        if self.template_version.template.profile != self.profile:
            raise ValidationError("پروفایل الگو و بازرسی باید یکسان باشد.")
        if self.template_snapshot_hash != self.template_version.canonical_hash:
            raise ValidationError("هش نسخه الگو با نسخه پین‌شده سازگار نیست.")
        if self.replaces_id:
            validate_related_organizations(self, replaces=self.replaces)
            if self.replaces.profile != self.profile:
                raise ValidationError("بازرسی جایگزین باید همان پروفایل را داشته باشد.")

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("سابقه بازرسی حذف نمی‌شود.")


class InspectionFinding(ScopedControlModel):
    number = models.CharField(max_length=50)
    inspection = models.ForeignKey(
        Inspection,
        on_delete=models.PROTECT,
        related_name="findings",
        null=True,
        blank=True,
    )
    source_test = models.ForeignKey(
        "QualityTest",
        on_delete=models.PROTECT,
        related_name="findings",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    classification = models.CharField(max_length=60, blank=True)
    severity = models.CharField(max_length=40, blank=True)
    disposition = models.TextField(blank=True)
    correction = models.TextField(blank=True)
    status = models.CharField(
        max_length=30,
        choices=FindingStatus.choices,
        default=FindingStatus.RECORDED,
        db_index=True,
    )
    responsible_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="compliance_findings_assigned",
        null=True,
        blank=True,
    )
    due_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="compliance_findings_created",
    )
    implemented_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="compliance_findings_implemented",
        null=True,
        blank=True,
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="compliance_findings_verified",
        null=True,
        blank=True,
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="compliance_findings_closed",
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "profile", "number"],
                name="compliance_finding_number_uq",
            )
        ]

    def clean(self) -> None:
        self.validate_scope()
        if not self.inspection_id and not self.source_test_id:
            raise ValidationError("یافته باید منبع بازرسی یا آزمون داشته باشد.")
        if self.inspection_id:
            validate_related_organizations(self, inspection=self.inspection)
            if (
                self.inspection.profile != self.profile
                or self.inspection.project_id != self.project_id
            ):
                raise ValidationError("منبع بازرسی با دامنه یافته سازگار نیست.")
        if self.source_test_id:
            validate_related_organizations(self, source_test=self.source_test)
            if self.profile != ControlProfile.QA_QC:
                raise ValidationError("یافته آزمون فقط برای پروفایل QA/QC مجاز است.")


class Permit(ScopedControlModel):
    number = models.CharField(max_length=50)
    permit_type = models.CharField(max_length=100)
    rule_source = models.CharField(max_length=300, blank=True)
    rule_version = models.CharField(max_length=100, blank=True)
    issuer_name = models.CharField(max_length=200, blank=True)
    scope_description = models.TextField()
    conditions = models.JSONField(default=list, blank=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=PermitStatus.choices,
        default=PermitStatus.DRAFT,
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="permits_created",
    )
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="permits_issued",
        null=True,
        blank=True,
    )
    replaces = models.ForeignKey(
        "self", on_delete=models.PROTECT, related_name="renewals", null=True, blank=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "number"], name="compliance_permit_number_uq"
            )
        ]

    def clean(self) -> None:
        self.validate_scope()
        if self.profile != ControlProfile.HSE:
            raise ValidationError("مجوز در این بسته فقط در اختیار پروفایل HSE است.")
        if self.status in {
            PermitStatus.ISSUED,
            PermitStatus.SUSPENDED,
            PermitStatus.EXPIRED,
            PermitStatus.REVOKED,
            PermitStatus.SUPERSEDED,
        }:
            if not all(
                (
                    self.rule_source.strip(),
                    self.rule_version.strip(),
                    self.issuer_name.strip(),
                    self.valid_from,
                    self.valid_until,
                )
            ):
                raise ValidationError(
                    "صدور مجوز بدون منبع، نسخه، صادرکننده و دوره اعتبار مجاز نیست."
                )
            if self.valid_from >= self.valid_until:
                raise ValidationError("پایان اعتبار باید پس از شروع اعتبار باشد.")

    @property
    def is_currently_valid(self) -> bool:
        if (
            self.status != PermitStatus.ISSUED
            or self.valid_from is None
            or self.valid_until is None
        ):
            return False
        now = timezone.now()
        return self.valid_from <= now < self.valid_until


class QualityTest(ScopedControlModel):
    number = models.CharField(max_length=50)
    title = models.CharField(max_length=200)
    method_reference = models.CharField(max_length=300)
    method_version = models.CharField(max_length=100)
    acceptance_criteria = models.JSONField(default=dict)
    specimen_id = models.CharField(max_length=100, blank=True)
    performer_name = models.CharField(max_length=200, blank=True)
    status = models.CharField(
        max_length=20,
        choices=TestStatus.choices,
        default=TestStatus.DRAFT,
        db_index=True,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="quality_tests_requested",
    )
    replaces = models.ForeignKey(
        "self", on_delete=models.PROTECT, related_name="retests", null=True, blank=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "number"], name="compliance_test_number_uq"
            )
        ]

    def clean(self) -> None:
        self.validate_scope()
        if self.profile != ControlProfile.QA_QC:
            raise ValidationError("آزمون فقط برای پروفایل QA/QC مجاز است.")
        if self.status not in {TestStatus.DRAFT, TestStatus.CANCELLED} and not all(
            (self.method_reference.strip(), self.method_version.strip())
        ):
            raise ValidationError("آزمون بدون مرجع روش و نسخه آن قابل اجرا نیست.")


class TestResult(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="+"
    )
    test = models.ForeignKey(
        QualityTest, on_delete=models.PROTECT, related_name="results"
    )
    sequence = models.PositiveIntegerField()
    values = models.JSONField(default=dict)
    units = models.JSONField(default=dict)
    criteria_snapshot = models.JSONField(default=dict)
    result_hash = models.CharField(max_length=64)
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="test_results_entered",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="test_results_reviewed",
        null=True,
        blank=True,
    )
    review_decision = models.CharField(max_length=20, blank=True)
    review_reason = models.TextField(blank=True)
    invalidated_at = models.DateTimeField(null=True, blank=True)
    invalidation_reason = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["test", "sequence"], name="compliance_test_result_seq_uq"
            )
        ]

    def clean(self) -> None:
        validate_related_organizations(self, test=self.test)
        if self.criteria_snapshot != self.test.acceptance_criteria:
            raise ValidationError(
                "معیار نتیجه باید تصویر دقیق معیار پین‌شده آزمون باشد."
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            original = (
                type(self)
                .objects.filter(pk=self.pk)
                .values(
                    "values",
                    "units",
                    "criteria_snapshot",
                    "result_hash",
                    "entered_by_id",
                )
                .first()
            )
            current = {key: getattr(self, key) for key in original} if original else {}
            if original and original != current:
                raise ValidationError("داده نتیجه آزمون پس از ثبت تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)


class Nonconformance(ScopedControlModel):
    number = models.CharField(max_length=50)
    finding = models.ForeignKey(
        InspectionFinding, on_delete=models.PROTECT, related_name="nonconformities"
    )
    description = models.TextField()
    disposition = models.TextField(blank=True)
    status = models.CharField(
        max_length=30, choices=NcrStatus.choices, default=NcrStatus.DRAFT, db_index=True
    )
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ncrs_issued",
        null=True,
        blank=True,
    )
    implemented_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ncrs_implemented",
        null=True,
        blank=True,
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ncrs_verified",
        null=True,
        blank=True,
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ncrs_closed",
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "number"], name="compliance_ncr_number_uq"
            )
        ]

    def clean(self) -> None:
        self.validate_scope()
        validate_related_organizations(self, finding=self.finding)
        if (
            self.profile != ControlProfile.QA_QC
            or self.finding.profile != ControlProfile.QA_QC
        ):
            raise ValidationError("NCR رسمی فقط از یافته QA/QC ایجاد می‌شود.")


class CapaAction(ScopedControlModel):
    number = models.CharField(max_length=50)
    action_type = models.CharField(max_length=20, choices=CapaType.choices)
    finding = models.ForeignKey(
        InspectionFinding,
        on_delete=models.PROTECT,
        related_name="capa_actions",
        null=True,
        blank=True,
    )
    nonconformance = models.ForeignKey(
        Nonconformance,
        on_delete=models.PROTECT,
        related_name="capa_actions",
        null=True,
        blank=True,
    )
    problem_or_risk = models.TextField()
    cause_or_rationale = models.TextField()
    implementation_plan = models.TextField()
    verification_criteria = models.TextField()
    effectiveness_criteria = models.TextField()
    target_date = models.DateField()
    distinct_closer_required = models.BooleanField(default=False)
    status = models.CharField(
        max_length=30,
        choices=CapaStatus.choices,
        default=CapaStatus.PROPOSED,
        db_index=True,
    )
    responsible_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="capa_actions_assigned",
        null=True,
        blank=True,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="capa_actions_approved",
        null=True,
        blank=True,
    )
    implemented_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="capa_actions_implemented",
        null=True,
        blank=True,
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="capa_actions_verified",
        null=True,
        blank=True,
    )
    effectiveness_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="capa_effectiveness_reviewed",
        null=True,
        blank=True,
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="capa_actions_closed",
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "number"], name="compliance_capa_number_uq"
            ),
            models.CheckConstraint(
                condition=Q(finding__isnull=False) | Q(nonconformance__isnull=False),
                name="compliance_capa_source_required",
            ),
        ]

    def clean(self) -> None:
        self.validate_scope()
        if self.finding_id:
            validate_related_organizations(self, finding=self.finding)
        if self.nonconformance_id:
            validate_related_organizations(self, nonconformance=self.nonconformance)
        if (
            self.action_type == CapaType.PREVENTIVE
            and not self.cause_or_rationale.strip()
        ):
            raise ValidationError("اقدام پیشگیرانه به دلیل و شواهد ریسک نیاز دارد.")


class ComplianceEvidenceLink(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="+"
    )
    purpose = models.CharField(
        max_length=30,
        choices=EvidencePurpose.choices,
        default=EvidencePurpose.EXECUTION,
    )
    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.PROTECT,
        related_name="compliance_evidence_links",
    )
    document_version = models.ForeignKey(
        DocumentVersion,
        on_delete=models.PROTECT,
        related_name="compliance_evidence_links",
    )
    sha256 = models.CharField(max_length=64)
    inspection = models.ForeignKey(
        Inspection,
        on_delete=models.PROTECT,
        related_name="evidence_links",
        null=True,
        blank=True,
    )
    permit = models.ForeignKey(
        Permit,
        on_delete=models.PROTECT,
        related_name="evidence_links",
        null=True,
        blank=True,
    )
    test = models.ForeignKey(
        QualityTest,
        on_delete=models.PROTECT,
        related_name="evidence_links",
        null=True,
        blank=True,
    )
    test_result = models.ForeignKey(
        TestResult,
        on_delete=models.PROTECT,
        related_name="evidence_links",
        null=True,
        blank=True,
    )
    finding = models.ForeignKey(
        InspectionFinding,
        on_delete=models.PROTECT,
        related_name="evidence_links",
        null=True,
        blank=True,
    )
    nonconformance = models.ForeignKey(
        Nonconformance,
        on_delete=models.PROTECT,
        related_name="evidence_links",
        null=True,
        blank=True,
    )
    capa_action = models.ForeignKey(
        CapaAction,
        on_delete=models.PROTECT,
        related_name="evidence_links",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="compliance_evidence_linked",
    )
    operation_key = models.UUIDField(default=uuid.uuid4)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "created_by", "operation_key"],
                name="compliance_evidence_op_uq",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        inspection__isnull=False,
                        permit__isnull=True,
                        test__isnull=True,
                        test_result__isnull=True,
                        finding__isnull=True,
                        nonconformance__isnull=True,
                        capa_action__isnull=True,
                    )
                    | Q(
                        inspection__isnull=True,
                        permit__isnull=False,
                        test__isnull=True,
                        test_result__isnull=True,
                        finding__isnull=True,
                        nonconformance__isnull=True,
                        capa_action__isnull=True,
                    )
                    | Q(
                        inspection__isnull=True,
                        permit__isnull=True,
                        test__isnull=False,
                        test_result__isnull=True,
                        finding__isnull=True,
                        nonconformance__isnull=True,
                        capa_action__isnull=True,
                    )
                    | Q(
                        inspection__isnull=True,
                        permit__isnull=True,
                        test__isnull=True,
                        test_result__isnull=False,
                        finding__isnull=True,
                        nonconformance__isnull=True,
                        capa_action__isnull=True,
                    )
                    | Q(
                        inspection__isnull=True,
                        permit__isnull=True,
                        test__isnull=True,
                        test_result__isnull=True,
                        finding__isnull=False,
                        nonconformance__isnull=True,
                        capa_action__isnull=True,
                    )
                    | Q(
                        inspection__isnull=True,
                        permit__isnull=True,
                        test__isnull=True,
                        test_result__isnull=True,
                        finding__isnull=True,
                        nonconformance__isnull=False,
                        capa_action__isnull=True,
                    )
                    | Q(
                        inspection__isnull=True,
                        permit__isnull=True,
                        test__isnull=True,
                        test_result__isnull=True,
                        finding__isnull=True,
                        nonconformance__isnull=True,
                        capa_action__isnull=False,
                    )
                ),
                name="compliance_evidence_one_subject",
            ),
        ]

    @property
    def target(self) -> models.Model:
        return next(
            subject
            for subject in (
                self.inspection,
                self.permit,
                self.test,
                self.test_result,
                self.finding,
                self.nonconformance,
                self.capa_action,
            )
            if subject is not None
        )

    @property
    def target_type(self) -> str:
        for field_name in (
            "inspection",
            "permit",
            "test",
            "test_result",
            "finding",
            "nonconformance",
            "capa_action",
        ):
            if getattr(self, f"{field_name}_id") is not None:
                return field_name
        raise ValidationError("پیوند شواهد موضوع معتبری ندارد.")

    def clean(self) -> None:
        if self.document_version_id:
            validate_related_organizations(self, document_version=self.document_version)
            if self.document_id != self.document_version.document_id:
                raise ValidationError("نسخه شواهد باید متعلق به همان سند باشد.")
            if self.sha256 != self.document_version.sha256:
                raise ValidationError("هش شواهد باید با نسخه DMS یکسان باشد.")
        subjects = [
            self.inspection,
            self.permit,
            self.test,
            self.test_result,
            self.finding,
            self.nonconformance,
            self.capa_action,
        ]
        selected = [subject for subject in subjects if subject is not None]
        if len(selected) != 1:
            raise ValidationError("پیوند شواهد باید دقیقاً یک موضوع داشته باشد.")
        validate_related_organizations(self, subject=selected[0])

    def save(self, *args: object, **kwargs: object) -> None:
        if self.document_version_id:
            self.document_id = self.document_version.document_id
            self.sha256 = self.document_version.sha256
        if not self._state.adding:
            raise ValidationError("پیوند نسخه شواهد تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("پیوند شواهد نهایی حذف نمی‌شود.")


class ComplianceLifecycleEvent(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="+"
    )
    entity_type = models.CharField(max_length=30)
    entity_id = models.UUIDField()
    profile = models.CharField(max_length=10, choices=ControlProfile.choices)
    from_status = models.CharField(max_length=30)
    to_status = models.CharField(max_length=30)
    reason = models.TextField(blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="compliance_lifecycle_events",
    )
    operation_key = models.UUIDField()
    payload_hash = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "actor", "entity_type", "operation_key"],
                name="compliance_event_op_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["organization", "entity_type", "entity_id", "created_at"],
                name="compliance_event_subject_idx",
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("تاریخچه چرخه عمر تغییرپذیر نیست.")
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("تاریخچه چرخه عمر حذف نمی‌شود.")


class ComplianceDownstreamProposal(ScopedControlModel):
    source_type = models.CharField(max_length=30)
    source_id = models.UUIDField()
    source_hash = models.CharField(max_length=64)
    target_domain = models.CharField(max_length=40)
    proposal_payload = models.JSONField(default=dict)
    status = models.CharField(max_length=20, default="draft")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="compliance_proposals_created",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="compliance_proposals_reviewed",
        null=True,
        blank=True,
    )
    operation_key = models.UUIDField(default=uuid.uuid4)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "created_by", "operation_key"],
                name="compliance_proposal_op_uq",
            )
        ]

    def clean(self) -> None:
        self.validate_scope()

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("پیشنهاد پایین‌دستی بخشی از سابقه است و حذف نمی‌شود.")
