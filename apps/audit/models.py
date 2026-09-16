from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import CreatedAtModel, UUIDModel


class AuditAction(models.TextChoices):
    WORKFLOW_DEFINITION_CREATED = (
        "workflow_definition.created",
        "تعریف گردش‌کار ایجاد شد",
    )
    WORKFLOW_DRAFT_UPDATED = "workflow_draft.updated", "پیش‌نویس گردش‌کار ویرایش شد"
    WORKFLOW_DEFINITION_VALIDATED = (
        "workflow_definition.validated",
        "تعریف گردش‌کار اعتبارسنجی شد",
    )
    WORKFLOW_VERSION_PUBLISHED = (
        "workflow_version.published",
        "نسخه گردش‌کار منتشر شد",
    )
    WORKFLOW_VERSION_RETIRED = (
        "workflow_version.retired",
        "نسخه گردش‌کار بازنشسته شد",
    )
    WORKFLOW_INSTANCE_STARTED = "workflow_instance.started", "اجرای گردش‌کار آغاز شد"
    WORKFLOW_INSTANCE_ADVANCED = "workflow_instance.advanced", "گردش‌کار پیش رفت"
    WORKFLOW_INSTANCE_SUSPENDED = (
        "workflow_instance.suspended",
        "اجرای گردش‌کار تعلیق شد",
    )
    WORKFLOW_INSTANCE_RESUMED = (
        "workflow_instance.resumed",
        "اجرای گردش‌کار از سر گرفته شد",
    )
    WORKFLOW_INSTANCE_CANCELLED = "workflow_instance.cancelled", "اجرای گردش‌کار لغو شد"
    WORKFLOW_INSTANCE_COMPLETED = (
        "workflow_instance.completed",
        "اجرای گردش‌کار تکمیل شد",
    )
    WORKFLOW_INSTANCE_MIGRATED = (
        "workflow_instance.migrated",
        "نسخه اجرای گردش‌کار تغییر کرد",
    )
    WORKFLOW_STEP_ACTIVATED = "workflow_step.activated", "گام گردش‌کار فعال شد"
    WORKFLOW_ROUTING_RESOLVED = "workflow_routing.resolved", "مسیریابی گردش‌کار انجام شد"
    WORKFLOW_ROUTING_FALLBACK = (
        "workflow_routing.fallback",
        "مسیر جایگزین گردش‌کار استفاده شد",
    )
    WORKFLOW_ROUTING_UNRESOLVABLE = (
        "workflow_routing.unresolvable",
        "مسیریابی گردش‌کار حل‌نشدنی بود",
    )
    WORKFLOW_CANDIDATES_CHANGED = (
        "workflow_candidates.changed",
        "نامزدهای گردش‌کار تغییر کردند",
    )
    WORK_ITEM_CLAIMED = "work_item.claimed", "کار اخذ شد"
    WORK_ITEM_RELEASED = "work_item.released", "کار آزاد شد"
    WORK_ITEM_REASSIGNED = "work_item.reassigned", "کار مجدداً تخصیص یافت"
    WORK_ITEM_COMPLETED = "work_item.completed", "کار تکمیل شد"
    WORK_ITEM_CANCELLED = "work_item.cancelled", "کار لغو شد"
    WORKFLOW_DELEGATION_CREATED = (
        "workflow_delegation.created",
        "واگذاری گردش‌کار ایجاد شد",
    )
    WORKFLOW_DELEGATION_REVOKED = (
        "workflow_delegation.revoked",
        "واگذاری گردش‌کار لغو شد",
    )
    ORGANIZATION_CREATED = "organization.created", "سازمان ایجاد شد"
    ORGANIZATION_SETTINGS_UPDATED = (
        "organization_settings.updated",
        "تنظیمات سازمان به‌روزرسانی شد",
    )
    BUSINESS_PARTY_CREATED = "business_party.created", "طرف تجاری ایجاد شد"
    BUSINESS_PARTY_UPDATED = "business_party.updated", "طرف تجاری به‌روزرسانی شد"
    BUSINESS_PARTY_ARCHIVED = "business_party.archived", "طرف تجاری بایگانی شد"
    PARTY_ROLE_ASSIGNED = "party_role.assigned", "نقش طرف تجاری تخصیص یافت"
    PARTY_CONTACT_ADDED = "party_contact.added", "راه ارتباطی طرف تجاری افزوده شد"
    UNIT_OF_MEASURE_CREATED = "unit_of_measure.created", "واحد اندازه‌گیری ایجاد شد"
    UNIT_OF_MEASURE_ARCHIVED = "unit_of_measure.archived", "واحد اندازه‌گیری بایگانی شد"
    MATERIAL_CATEGORY_CREATED = (
        "material_category.created",
        "دسته‌بندی مصالح ایجاد شد",
    )
    MATERIAL_CATEGORY_UPDATED = (
        "material_category.updated",
        "دسته‌بندی مصالح به‌روزرسانی شد",
    )
    MATERIAL_CATEGORY_ARCHIVED = (
        "material_category.archived",
        "دسته‌بندی مصالح بایگانی شد",
    )
    MATERIAL_CREATED = "material.created", "مصالح ایجاد شد"
    MATERIAL_UPDATED = "material.updated", "مصالح به‌روزرسانی شد"
    MATERIAL_ARCHIVED = "material.archived", "مصالح بایگانی شد"
    PROJECT_CREATED = "project.created", "پروژه ایجاد شد"
    PROJECT_ARCHIVED = "project.archived", "پروژه بایگانی شد"
    PROJECT_SITE_CREATED = "project_site.created", "کارگاه پروژه ایجاد شد"
    PROJECT_PHASE_CREATED = "project_phase.created", "فاز پروژه ایجاد شد"
    PROJECT_PHASE_STATUS_CHANGED = (
        "project_phase.status_changed",
        "وضعیت فاز پروژه تغییر کرد",
    )
    WBS_NODE_CREATED = "wbs_node.created", "گره ساختار شکست ایجاد شد"
    WBS_NODE_UPDATED = "wbs_node.updated", "گره ساختار شکست به‌روزرسانی شد"
    WBS_NODE_ARCHIVED = "wbs_node.archived", "گره ساختار شکست بایگانی شد"
    ACTIVITY_CREATED = "activity.created", "فعالیت ایجاد شد"
    ACTIVITY_STATUS_CHANGED = "activity.status_changed", "وضعیت فعالیت تغییر کرد"
    ACTIVITY_ARCHIVED = "activity.archived", "فعالیت بایگانی شد"
    CONTRACT_CREATED = "contract.created", "قرارداد ایجاد شد"
    CONTRACT_UPDATED = "contract.updated", "قرارداد به‌روزرسانی شد"
    CONTRACT_STATUS_CHANGED = "contract.status_changed", "وضعیت قرارداد تغییر کرد"
    CONTRACT_ITEM_ADDED = "contract.item_added", "ردیف قرارداد افزوده شد"
    CONTRACT_AMENDMENT_APPROVED = (
        "contract.amendment_approved",
        "الحاقیه قرارداد تأیید شد",
    )
    ESTIMATE_CREATED = "estimate.created", "برآورد ایجاد شد"
    ESTIMATE_ITEM_ADDED = "estimate.item_added", "ردیف برآورد افزوده شد"
    ESTIMATE_APPROVED = "estimate.approved", "برآورد تأیید شد"
    ESTIMATE_REVISION_CREATED = "estimate.revision_created", "بازنگری برآورد ایجاد شد"
    ESTIMATE_REVISION_APPROVED = (
        "estimate.revision_approved",
        "بازنگری برآورد تأیید شد",
    )
    EXPENSE_RECORDED = "expense.recorded", "هزینه ثبت شد"
    EXPENSE_VOIDED = "expense.voided", "هزینه باطل شد"
    EXPENSE_CATEGORY_CREATED = "expense_category.created", "دسته هزینه ایجاد شد"
    EXPENSE_CATEGORY_ARCHIVED = "expense_category.archived", "دسته هزینه بایگانی شد"
    PAYMENT_RECORDED = "payment.recorded", "پرداخت ثبت شد"
    PAYMENT_VOIDED = "payment.voided", "پرداخت باطل شد"
    PAYMENT_ALLOCATION_CREATED = (
        "payment_allocation.created",
        "تخصیص پرداخت ایجاد شد",
    )
    PAYMENT_ALLOCATION_REVERSED = (
        "payment_allocation.reversed",
        "تخصیص پرداخت برگشت داده شد",
    )
    DOCUMENT_UPLOADED = "document.uploaded", "سند بارگذاری شد"
    DOCUMENT_VERSION_ADDED = "document.version_added", "نسخه سند افزوده شد"
    DOCUMENT_LINK_ADDED = "document.link_added", "لینک سند افزوده شد"
    DOCUMENT_DOWNLOADED = "document.downloaded", "سند دریافت شد"
    DOCUMENT_ARCHIVED = "document.archived", "سند بایگانی شد"
    DAILY_REPORT_CREATED = "daily_report.created", "گزارش روزانه ایجاد شد"
    DAILY_REPORT_SUBMITTED = "daily_report.submitted", "گزارش روزانه ارسال شد"
    DAILY_REPORT_APPROVED = "daily_report.approved", "گزارش روزانه تأیید شد"
    DAILY_REPORT_LABOR_ADDED = (
        "daily_report.labor_added",
        "نیروی انسانی به گزارش روزانه افزوده شد",
    )
    DAILY_REPORT_EQUIPMENT_ADDED = (
        "daily_report.equipment_added",
        "تجهیزات به گزارش روزانه افزوده شد",
    )
    DAILY_REPORT_MATERIAL_ADDED = (
        "daily_report.material_added",
        "مصالح به گزارش روزانه افزوده شد",
    )
    DAILY_ACTIVITY_ADDED = "daily_activity.added", "فعالیت روزانه افزوده شد"
    DELAY_EVENT_ADDED = "delay_event.added", "رویداد تأخیر افزوده شد"
    DEPARTMENT_CREATED = "department.created", "واحد سازمانی ایجاد شد"
    DEPARTMENT_UPDATED = "department.updated", "واحد سازمانی به‌روزرسانی شد"
    DEPARTMENT_ARCHIVED = "department.archived", "واحد سازمانی بایگانی شد"
    POSITION_CREATED = "position.created", "سمت شغلی ایجاد شد"
    POSITION_UPDATED = "position.updated", "سمت شغلی به‌روزرسانی شد"
    POSITION_ARCHIVED = "position.archived", "سمت شغلی بایگانی شد"
    WORK_TEAM_CREATED = "work_team.created", "گروه کاری ایجاد شد"
    WORK_TEAM_ARCHIVED = "work_team.archived", "گروه کاری بایگانی شد"
    EMPLOYEE_CREATED = "employee.created", "کارمند ایجاد شد"
    EMPLOYEE_POSITION_ASSIGNED = (
        "employee_position_assignment.created",
        "سمت شغلی به کارمند تخصیص یافت",
    )
    EMPLOYEE_POSITION_ENDED = (
        "employee_position_assignment.ended",
        "تخصیص سمت شغلی کارمند پایان یافت",
    )
    EMPLOYEE_STATUS_CHANGED = "employee.status_changed", "وضعیت کارمند تغییر کرد"
    EMPLOYEE_ARCHIVED = "employee.archived", "کارمند بایگانی شد"
    EMPLOYEE_PROJECT_ASSIGNED = (
        "employee_project_assignment.created",
        "کارمند به پروژه تخصیص یافت",
    )
    EMPLOYEE_PROJECT_ASSIGNMENT_STATUS_CHANGED = (
        "employee_project_assignment.status_changed",
        "وضعیت تخصیص کارمند به پروژه تغییر کرد",
    )
    PURCHASE_REQUEST_CREATED = "purchase_request.created", "درخواست خرید ایجاد شد"
    PURCHASE_REQUEST_ITEM_ADDED = (
        "purchase_request.item_added",
        "ردیف درخواست خرید افزوده شد",
    )
    PURCHASE_REQUEST_SUBMITTED = (
        "purchase_request.submitted",
        "درخواست خرید ارسال شد",
    )
    PURCHASE_REQUEST_APPROVED = "purchase_request.approved", "درخواست خرید تأیید شد"
    PURCHASE_REQUEST_REJECTED = "purchase_request.rejected", "درخواست خرید رد شد"
    PURCHASE_REQUEST_CANCELLED = (
        "purchase_request.cancelled",
        "درخواست خرید لغو شد",
    )
    PURCHASE_ORDER_CREATED = "purchase_order.created", "سفارش خرید ایجاد شد"
    PURCHASE_ORDER_ITEM_ADDED = "purchase_order.item_added", "ردیف سفارش خرید افزوده شد"
    PURCHASE_ORDER_ISSUED = "purchase_order.issued", "سفارش خرید صادر شد"
    PURCHASE_ORDER_COMPLETED = "purchase_order.completed", "سفارش خرید تکمیل شد"
    PURCHASE_ORDER_CANCELLED = "purchase_order.cancelled", "سفارش خرید لغو شد"
    GOODS_RECEIPT_CREATED = "goods_receipt.created", "رسید کالا ایجاد شد"
    GOODS_RECEIPT_ITEM_ADDED = "goods_receipt.item_added", "ردیف رسید کالا افزوده شد"
    GOODS_RECEIPT_POSTED = "goods_receipt.posted", "رسید کالا ثبت شد"
    GOODS_RECEIPT_VOIDED = "goods_receipt.voided", "رسید کالا باطل شد"
    WAREHOUSE_CREATED = "warehouse.created", "انبار ایجاد شد"
    WAREHOUSE_ARCHIVED = "warehouse.archived", "انبار بایگانی شد"
    STOCK_TRANSACTION_CREATED = (
        "stock_transaction.created",
        "تراکنش انبار ایجاد شد",
    )
    STOCK_TRANSACTION_POSTED = (
        "stock_transaction.posted",
        "تراکنش انبار ثبت شد",
    )
    STOCK_TRANSACTION_REVERSED = (
        "stock_transaction.reversed",
        "تراکنش انبار برگشت داده شد",
    )
    EQUIPMENT_CREATED = "equipment.created", "تجهیز ایجاد شد"
    EQUIPMENT_STATUS_CHANGED = "equipment.status_changed", "وضعیت تجهیز تغییر کرد"
    EQUIPMENT_ARCHIVED = "equipment.archived", "تجهیز بایگانی شد"
    EQUIPMENT_ASSIGNMENT_CREATED = (
        "equipment_assignment.created",
        "تجهیز به پروژه تخصیص یافت",
    )
    EQUIPMENT_ASSIGNMENT_STATUS_CHANGED = (
        "equipment_assignment.status_changed",
        "وضعیت تخصیص تجهیز تغییر کرد",
    )
    MAINTENANCE_RECORD_CREATED = (
        "maintenance_record.created",
        "سابقه سرویس یا تعمیر ایجاد شد",
    )
    MAINTENANCE_STATUS_CHANGED = (
        "maintenance_record.status_changed",
        "وضعیت سرویس یا تعمیر تغییر کرد",
    )
    SAFETY_INCIDENT_CREATED = "safety_incident.created", "حادثه ایمنی ثبت شد"
    SAFETY_INCIDENT_REVIEWED = "safety_incident.reviewed", "حادثه ایمنی بررسی شد"
    SAFETY_INCIDENT_ASSIGNED = "safety_incident.assigned", "حادثه ایمنی تخصیص یافت"
    SAFETY_CORRECTIVE_ACTION_STARTED = (
        "safety_incident.corrective_action_started",
        "اقدام اصلاحی حادثه ایمنی آغاز شد",
    )
    SAFETY_INCIDENT_RESOLVED = "safety_incident.resolved", "حادثه ایمنی رفع شد"
    SAFETY_INCIDENT_CLOSED = "safety_incident.closed", "حادثه ایمنی بسته شد"
    QUALITY_ISSUE_CREATED = "quality_issue.created", "مسئله کیفیت ثبت شد"
    QUALITY_ISSUE_REVIEWED = "quality_issue.reviewed", "مسئله کیفیت بررسی شد"
    QUALITY_ISSUE_ASSIGNED = "quality_issue.assigned", "مسئله کیفیت تخصیص یافت"
    QUALITY_CORRECTIVE_ACTION_STARTED = (
        "quality_issue.corrective_action_started",
        "اقدام اصلاحی مسئله کیفیت آغاز شد",
    )
    QUALITY_ISSUE_SUBMITTED_FOR_VERIFICATION = (
        "quality_issue.submitted_for_verification",
        "مسئله کیفیت برای راستی‌آزمایی ارسال شد",
    )
    QUALITY_ISSUE_VERIFIED = (
        "quality_issue.verified",
        "مسئله کیفیت راستی‌آزمایی شد",
    )
    QUALITY_ISSUE_CLOSED = "quality_issue.closed", "مسئله کیفیت بسته شد"
    MEMBERSHIP_PROVISIONED = (
        "membership.provisioned",
        "کاربر در انتظار تعیین نقش به شرکت تخصیص یافت",
    )
    MEMBERSHIP_ROLE_CHANGED = "membership.role_changed", "نقش عضویت تغییر کرد"
    MEMBERSHIP_STATUS_CHANGED = (
        "membership.status_changed",
        "وضعیت عضویت تغییر کرد",
    )
    ORGANIZATION_ACCOUNT_CREATED = (
        "organization_account.created",
        "حساب کاربری شرکت ایجاد شد",
    )
    ORGANIZATION_MEMBER_PASSWORD_RESET = (
        "organization_member.password_reset",
        "گذرواژه عضو شرکت بازنشانی شد",
    )
    ACCOUNT_CONNECTION_REQUESTED = (
        "account_connection.requested",
        "درخواست اتصال حساب به شرکت ثبت شد",
    )
    ACCOUNT_CONNECTION_ACCEPTED = (
        "account_connection.accepted",
        "درخواست اتصال حساب پذیرفته شد",
    )
    ACCOUNT_CONNECTION_REJECTED = (
        "account_connection.rejected",
        "درخواست اتصال حساب رد شد",
    )
    EMPLOYEE_ACCOUNT_LINKED = (
        "employee.account_linked",
        "حساب کاربری به کارمند متصل شد",
    )
    EMPLOYEE_ACCOUNT_UNLINKED = (
        "employee.account_unlinked",
        "حساب کاربری کارمند قطع شد",
    )
    EMPLOYEE_PROFILE_IMAGE_UPDATED = (
        "employee.profile_image_updated",
        "عکس پرسنلی کارمند به‌روزرسانی شد",
    )
    USER_PASSWORD_INITIALIZED = (
        "user.password_initialized",
        "گذرواژه شخصی کاربر تعیین شد",
    )
    USER_ACCOUNT_STATUS_CHANGED = (
        "user.account_status_changed",
        "وضعیت حساب کاربر تغییر کرد",
    )
    USER_PERMISSIONS_CHANGED = (
        "user.permissions_changed",
        "مجوزهای ویژه کاربر تغییر کرد",
    )
    ROLE_CREATED = "role.created", "نقش شرکتی ایجاد شد"
    ROLE_UPDATED = "role.updated", "نقش شرکتی به‌روزرسانی شد"
    ROLE_DELETED = "role.deleted", "نقش شرکتی حذف شد"
    ROLE_PERMISSIONS_CHANGED = (
        "role.permissions_changed",
        "مجوزهای نقش شرکتی تغییر کرد",
    )


class AuditEventQuerySet(models.QuerySet):
    """Prevent bulk mutation of immutable audit evidence."""

    def update(self, **kwargs: object) -> int:
        raise ValidationError("رویدادهای ممیزی قابل تغییر نیستند.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ValidationError("رویدادهای ممیزی قابل حذف نیستند.")


class AuditEventManager(models.Manager.from_queryset(AuditEventQuerySet)):
    """Allow only normal single-event creation through the default manager."""

    def bulk_create(self, *args: object, **kwargs: object) -> list[models.Model]:
        raise ValidationError("رویدادهای ممیزی باید به‌صورت جداگانه ایجاد شوند.")


class AuditEvent(UUIDModel, CreatedAtModel):
    """Immutable record of an important business action."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="عامل",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    action = models.CharField("عملیات", max_length=64, choices=AuditAction.choices)
    entity_type = models.CharField("نوع موجودیت", max_length=100)
    entity_id = models.CharField("شناسه موجودیت", max_length=100, blank=True)
    metadata = models.JSONField("فراداده", default=dict, blank=True)

    objects = AuditEventManager()

    class Meta:
        verbose_name = "رویداد ممیزی"
        verbose_name_plural = "رویدادهای ممیزی"
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
        return f"{self.get_action_display()} ({self.entity_type}:{self.entity_id})"

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("رویدادهای ممیزی قابل تغییر نیستند.")
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("رویدادهای ممیزی قابل حذف نیستند.")
