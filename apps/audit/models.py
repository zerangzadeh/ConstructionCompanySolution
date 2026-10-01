import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import CreatedAtModel, UUIDModel


class AuditAction(models.TextChoices):
    TREASURY_ACCOUNT_CREATED = "treasury.account_created", "حساب خزانه‌داری ایجاد شد"
    TREASURY_ACCOUNT_TRANSITIONED = (
        "treasury.account_transitioned",
        "وضعیت حساب خزانه‌داری تغییر کرد",
    )
    TREASURY_MAPPING_VERSIONED = (
        "treasury.mapping_versioned",
        "نسخه نگاشت حسابداری خزانه‌داری ثبت شد",
    )
    TREASURY_MOVEMENT_CREATED = (
        "treasury.movement_created",
        "حرکت خزانه‌داری ایجاد شد",
    )
    TREASURY_MOVEMENT_TRANSITIONED = (
        "treasury.movement_transitioned",
        "وضعیت حرکت خزانه‌داری تغییر کرد",
    )
    TREASURY_MOVEMENT_REVERSED = (
        "treasury.movement_reversed",
        "حرکت خزانه‌داری برگشت خورد",
    )
    TREASURY_CHEQUE_CREATED = "treasury.cheque_created", "چک ثبت شد"
    TREASURY_CHEQUE_TRANSITIONED = (
        "treasury.cheque_transitioned",
        "وضعیت چک تغییر کرد",
    )
    TREASURY_RECONCILIATION_RETAINED = (
        "treasury.reconciliation_retained",
        "تطبیق خزانه‌داری با دفترکل نگهداری شد",
    )
    TREASURY_RECONCILIATION_REVIEWED = (
        "treasury.reconciliation_reviewed",
        "تطبیق خزانه‌داری با دفترکل مستقل بررسی شد",
    )
    TREASURY_PAYMENT_REQUEST_CREATED = (
        "treasury.payment_request_created",
        "درخواست پرداخت خزانه‌داری ایجاد شد",
    )
    TREASURY_PAYMENT_REQUEST_TRANSITIONED = (
        "treasury.payment_request_transitioned",
        "وضعیت درخواست پرداخت تغییر کرد",
    )
    TREASURY_PAYMENT_REQUEST_RELEASED = (
        "treasury.payment_request_released",
        "پرداخت قطعی به درخواست متصل شد",
    )
    TREASURY_ADVANCE_OPENED = "treasury.advance_opened", "تنخواه باز شد"
    TREASURY_ADVANCE_REVERSED = "treasury.advance_reversed", "تنخواه برگشت شد"
    TREASURY_ADVANCE_SETTLEMENT_CREATED = (
        "treasury.advance_settlement_created",
        "تسویه نقدی تنخواه ثبت شد",
    )
    TREASURY_ADVANCE_SETTLEMENT_TRANSITIONED = (
        "treasury.advance_settlement_transitioned",
        "وضعیت تسویه تنخواه تغییر کرد",
    )
    TREASURY_ADVANCE_SETTLEMENT_REVERSED = (
        "treasury.advance_settlement_reversed",
        "تسویه تنخواه برگشت شد",
    )
    TREASURY_ADVANCE_RECONCILIATION_RETAINED = (
        "treasury.advance_reconciliation_retained",
        "شواهد تطبیق تنخواه نگهداری شد",
    )
    TREASURY_STATEMENT_IMPORT_PREVIEWED = (
        "treasury.statement_import_previewed",
        "پیش‌نمایش ورود صورتحساب بانکی نگهداری شد",
    )
    TREASURY_STATEMENT_IMPORT_DECIDED = (
        "treasury.statement_import_decided",
        "ورود صورتحساب بانکی تعیین تکلیف شد",
    )
    TREASURY_STATEMENT_MATCH_PROPOSED = (
        "treasury.statement_match_proposed",
        "پیشنهاد تطبیق بانکی نگهداری شد",
    )
    TREASURY_STATEMENT_MATCH_DECIDED = (
        "treasury.statement_match_decided",
        "پیشنهاد تطبیق بانکی تعیین تکلیف شد",
    )
    TREASURY_CLEARING_REVERSED = (
        "treasury.clearing_reversed",
        "تسویه بانکی برگشت شد",
    )
    TREASURY_BANK_RECONCILIATION_RETAINED = (
        "treasury.bank_reconciliation_retained",
        "شواهد تطبیق بانکی نگهداری شد",
    )
    SUBLEDGER_OBLIGATION_RECOGNIZED = (
        "subledger.obligation_recognized",
        "تعهد AP/AR شناسایی شد",
    )
    SUBLEDGER_SETTLEMENT_ALLOCATED = (
        "subledger.settlement_allocated",
        "تسویه AP/AR تخصیص یافت",
    )
    SUBLEDGER_SETTLEMENT_REVERSED = (
        "subledger.settlement_reversed",
        "تخصیص تسویه AP/AR برگشت خورد",
    )
    SUBLEDGER_WRITEOFF_PROPOSED = (
        "subledger.writeoff_proposed",
        "پیشنهاد سوخت AP/AR ثبت شد",
    )
    SUBLEDGER_AGING_RETAINED = (
        "subledger.aging_retained",
        "شواهد aging AP/AR نگهداری شد",
    )
    SUBLEDGER_RECONCILIATION_RETAINED = (
        "subledger.reconciliation_retained",
        "شواهد تطبیق AP/AR نگهداری شد",
    )
    SUBLEDGER_RECONCILIATION_REVIEWED = (
        "subledger.reconciliation_reviewed",
        "تطبیق AP/AR مستقل بررسی شد",
    )
    ACCOUNTING_ACCOUNT_CREATED = "accounting.account_created", "حساب دفترکل ایجاد شد"
    ACCOUNTING_FISCAL_YEAR_CREATED = (
        "accounting.fiscal_year_created",
        "سال مالی ایجاد شد",
    )
    ACCOUNTING_FISCAL_PERIOD_CREATED = (
        "accounting.fiscal_period_created",
        "دوره مالی ایجاد شد",
    )
    ACCOUNTING_JOURNAL_CREATED = "accounting.journal_created", "سند حسابداری ایجاد شد"
    ACCOUNTING_JOURNAL_SUBMITTED = (
        "accounting.journal_submitted",
        "سند حسابداری ارسال شد",
    )
    ACCOUNTING_JOURNAL_POSTED = "accounting.journal_posted", "سند حسابداری ثبت قطعی شد"
    ACCOUNTING_JOURNAL_REVERSED = (
        "accounting.journal_reversed",
        "سند حسابداری برگشت خورد",
    )
    ACCOUNTING_OPENING_IMPORT_CREATED = (
        "accounting.opening_import_created",
        "ورودی افتتاحیه ایجاد شد",
    )
    ACCOUNTING_OPENING_IMPORT_SUBMITTED = (
        "accounting.opening_import_submitted",
        "ورودی افتتاحیه ارسال شد",
    )
    ACCOUNTING_OPENING_IMPORT_ACCEPTED = (
        "accounting.opening_import_accepted",
        "ورودی افتتاحیه پذیرفته شد",
    )
    ACCOUNTING_PERIOD_CLOSED = "accounting.period_closed", "دوره مالی بسته شد"
    ACCOUNTING_PERIOD_REOPENED = "accounting.period_reopened", "دوره مالی بازگشایی شد"
    ACCOUNTING_RECONCILIATION_RUN_CREATED = (
        "accounting.reconciliation_run_created",
        "اجرای تطبیق حسابداری نگهداری شد",
    )
    ACCOUNTING_RECONCILIATION_EXCEPTION_DISPOSED = (
        "accounting.reconciliation_exception_disposed",
        "استثنای تطبیق حسابداری تعیین تکلیف شد",
    )
    ACCOUNTING_RECONCILIATION_SIGNED_OFF = (
        "accounting.reconciliation_signed_off",
        "تطبیق حسابداری به‌طور مستقل تأیید شد",
    )
    ACCOUNTING_STATEMENT_RETAINED = (
        "accounting.statement_retained",
        "صورت مالی نگهداری شد",
    )
    ACCOUNTING_CONTROLLED_ADJUSTMENT_CREATED = (
        "accounting.controlled_adjustment_created",
        "تعدیل کنترل‌شده ایجاد شد",
    )
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
    WORKFLOW_UNRESOLVED_RECOVERED = (
        "workflow_routing.unresolved_recovered",
        "کار حل‌نشده بازیابی شد",
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
    POLICY_SOURCE_RECORDED = "policy.source_recorded", "منبع سیاست ثبت شد"
    PLATFORM_POLICY_CREATED = "policy.platform_created", "سیاست پلتفرم ایجاد شد"
    PLATFORM_POLICY_VERSION_CREATED = (
        "policy.version_created",
        "نسخه سیاست پلتفرم ایجاد شد",
    )
    PLATFORM_POLICY_VERSION_PUBLISHED = (
        "policy.version_published",
        "نسخه سیاست پلتفرم منتشر شد",
    )
    PLATFORM_POLICY_SOURCE_LINKED = (
        "policy.source_linked",
        "منبع به نسخه سیاست پیوند شد",
    )
    PLATFORM_POLICY_VERSION_RETIRED = (
        "policy.version_retired",
        "نسخه سیاست پلتفرم بازنشسته شد",
    )
    PLATFORM_POLICY_DEACTIVATED = (
        "policy.deactivated",
        "سیاست پلتفرم غیرفعال شد",
    )
    POLICY_REVIEW_EVIDENCE_RECORDED = (
        "policy.review_evidence_recorded",
        "مدرک اختیاری بررسی سیاست ثبت شد",
    )
    TENANT_POLICY_APPROVED = "policy.tenant_approved", "سیاست Tenant تأیید شد"
    TENANT_POLICY_SELECTED = "policy.tenant_selected", "سیاست Tenant انتخاب شد"
    TENANT_POLICY_APPLIED = "policy.tenant_applied", "سیاست Tenant اعمال شد"
    BUSINESS_PARTY_CREATED = "business_party.created", "طرف تجاری ایجاد شد"
    BUSINESS_PARTY_UPDATED = "business_party.updated", "طرف تجاری به‌روزرسانی شد"
    BUSINESS_PARTY_ARCHIVED = "business_party.archived", "طرف تجاری بایگانی شد"
    BUSINESS_PARTY_MERGED = "business_party.merged", "ادغام طرف تجاری ثبت شد"
    PARTY_RESTRICTION_CREATED = (
        "party_restriction.created",
        "محدودیت طرف تجاری ثبت شد",
    )
    PARTY_RESTRICTION_REVOKED = (
        "party_restriction.revoked",
        "محدودیت طرف تجاری لغو شد",
    )
    PARTY_ROLE_ASSIGNED = "party_role.assigned", "نقش طرف تجاری تخصیص یافت"
    PARTY_CONTACT_ADDED = "party_contact.added", "راه ارتباطی طرف تجاری افزوده شد"
    PARTY_ALIAS_RECORDED = "party_alias.recorded", "نام مستعار طرف تجاری ثبت شد"
    PARTY_CLASSIFICATION_CREATED = (
        "party_classification.created",
        "دسته یا برچسب طرف تجاری ایجاد شد",
    )
    PARTY_CLASSIFICATION_ASSIGNED = (
        "party_classification.assigned",
        "دسته یا برچسب به طرف تجاری تخصیص یافت",
    )
    PARTY_CLASSIFICATION_REVOKED = (
        "party_classification.revoked",
        "انتساب دسته یا برچسب طرف تجاری لغو شد",
    )
    PARTY_REPRESENTATIVE_RECORDED = (
        "party_representative.recorded",
        "نماینده یا امضادار طرف تجاری ثبت شد",
    )
    PARTY_REPRESENTATIVE_REVOKED = (
        "party_representative.revoked",
        "نماینده یا امضادار طرف تجاری لغو شد",
    )
    UNIT_OF_MEASURE_CREATED = "unit_of_measure.created", "واحد اندازه‌گیری ایجاد شد"
    UNIT_OF_MEASURE_ARCHIVED = "unit_of_measure.archived", "واحد اندازه‌گیری بایگانی شد"
    UOM_FAMILY_CONFIGURED = "unit.family_configured", "خانواده واحد پیکربندی شد"
    UOM_CONVERSION_VERSION_CREATED = (
        "unit.conversion_version_created",
        "نسخه تبدیل واحد ایجاد شد",
    )
    UOM_ROUNDING_POLICY_CREATED = (
        "unit.rounding_policy_created",
        "سیاست گرد کردن کمیت ایجاد شد",
    )
    UOM_CONVERSION_APPLIED = "unit.conversion_applied", "تبدیل کمیت اعمال شد"
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
    MATERIAL_ALIAS_RECORDED = "material.alias_recorded", "شناسه جایگزین مصالح ثبت شد"
    MATERIAL_DUPLICATE_REVIEWED = (
        "material.duplicate_reviewed",
        "نامزد تکراری مصالح بررسی شد",
    )
    MATERIAL_SUPERSEDED = (
        "material.superseded",
        "جایگزینی غیرمخرب مصالح ثبت شد",
    )
    MATERIAL_ATTRIBUTE_DEFINITION_VERSION_CREATED = (
        "material_attribute.definition_version_created",
        "نسخه تعریف ویژگی مصالح ایجاد شد",
    )
    MATERIAL_ATTRIBUTE_VALUE_RECORDED = (
        "material_attribute.value_recorded",
        "مقدار ویژگی مصالح ثبت شد",
    )
    MATERIAL_ATTRIBUTE_IMPORT_RECORDED = (
        "material_attribute.import_recorded",
        "درون‌ریزی ویژگی مصالح ثبت شد",
    )
    MATERIAL_PRICE_OBSERVATION_RECORDED = (
        "material_price.observation_recorded",
        "مشاهده قیمت مصالح ثبت شد",
    )
    MATERIAL_TECHNICAL_STATUS_CHANGED = (
        "material_technical.status_changed",
        "وضعیت بررسی فنی مصالح تغییر کرد",
    )
    MATERIAL_DOCUMENT_LINKED = "material_document.linked", "سند فنی مصالح پیوند خورد"
    MATERIAL_RELATIONSHIP_RECORDED = (
        "material_relationship.recorded",
        "رابطه مصالح ثبت شد",
    )
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
    PROJECT_BASELINE_CREATED = "project_baseline.created", "مبنای تجاری پروژه ایجاد شد"
    PROJECT_BASELINE_UPDATED = "project_baseline.updated", "مبنای تجاری پروژه ویرایش شد"
    PROJECT_BASELINE_ITEM_ADDED = (
        "project_baseline.item_added",
        "ردیف مبنای تجاری پروژه افزوده شد",
    )
    PROJECT_BASELINE_APPROVED = (
        "project_baseline.approved",
        "مبنای تجاری پروژه تأیید شد",
    )
    PROJECT_BASELINE_WITHDRAWN = (
        "project_baseline.withdrawn",
        "مبنای تجاری پروژه مسترد شد",
    )
    PROGRESS_RECORDED = "progress.recorded", "پیشرفت ثبت شد"
    PROGRESS_CORRECTION_RECORDED = "progress.correction_recorded", "اصلاح پیشرفت ثبت شد"
    PROGRESS_VERIFIED = "progress.verified", "پیشرفت راستی‌آزمایی شد"
    PROGRESS_REJECTED = "progress.rejected", "پیشرفت رد شد"
    PROGRESS_CLAIM_SUBMITTED = "progress_claim.submitted", "صورت‌وضعیت ارسال شد"
    PROGRESS_CLAIM_APPROVED = "progress_claim.approved", "صورت‌وضعیت تأیید شد"
    PROGRESS_CLAIM_RETURNED = (
        "progress_claim.returned",
        "صورت‌وضعیت برای اصلاح بازگردانده شد",
    )
    PROGRESS_CLAIM_REVISION_CREATED = (
        "progress_claim.revision_created",
        "revision صورت‌وضعیت ایجاد شد",
    )
    CLAIM_SETTLEMENT_ALLOCATED = (
        "claim_settlement.allocated",
        "دریافت به صورت‌وضعیت تخصیص یافت",
    )
    CLAIM_SETTLEMENT_REVERSED = (
        "claim_settlement.reversed",
        "تسویه صورت‌وضعیت برگشت داده شد",
    )
    ESTIMATE_CREATED = "estimate.created", "برآورد ایجاد شد"
    ESTIMATE_ITEM_ADDED = "estimate.item_added", "ردیف برآورد افزوده شد"
    ESTIMATE_APPROVED = "estimate.approved", "برآورد تأیید شد"
    ESTIMATE_REVISION_CREATED = "estimate.revision_created", "بازنگری برآورد ایجاد شد"
    ESTIMATE_REVISION_APPROVED = (
        "estimate.revision_approved",
        "بازنگری برآورد تأیید شد",
    )
    BUDGET_DRAFT_CREATED = "budget.draft_created", "پیش‌نویس بودجه ایجاد شد"
    BUDGET_SUBMITTED = "budget.submitted", "بودجه ارسال شد"
    BUDGET_ACCEPTED = "budget.accepted", "مبنای بودجه پذیرفته شد"
    PROJECT_COST_SOURCE_DRAFTED = (
        "project_cost.source_drafted",
        "قرارداد منبع هزینه پروژه ایجاد شد",
    )
    PROJECT_COST_SOURCE_APPROVED = (
        "project_cost.source_approved",
        "قرارداد منبع هزینه پروژه تأیید شد",
    )
    PROJECT_COST_FACT_RECORDED = (
        "project_cost.fact_recorded",
        "برون‌داد هزینه پروژه ثبت شد",
    )
    PROJECT_COST_COVERAGE_CHANGED = (
        "project_cost.coverage_changed",
        "پوشش منبع هزینه پروژه تغییر کرد",
    )
    PROJECT_COST_FORECAST_DRAFTED = (
        "project_cost.forecast_drafted",
        "پیش‌نویس پیش‌بینی هزینه پروژه ایجاد شد",
    )
    PROJECT_COST_RECONCILIATION_VIEWED = (
        "project_cost.reconciliation_viewed",
        "تطبیق محدود شواهد هزینه پروژه مشاهده شد",
    )
    PROJECT_COST_RECONCILIATION_EXPORTED = (
        "project_cost.reconciliation_exported",
        "خروجی تطبیق محدود شواهد هزینه پروژه ایجاد شد",
    )
    PROJECT_SCHEDULE_DRAFTED = (
        "project_schedule.drafted",
        "پیش‌نویس برنامه زمان‌بندی پروژه ایجاد شد",
    )
    PROJECT_SCHEDULE_ITEM_ADDED = (
        "project_schedule.item_added",
        "فعالیت یا نقطه عطف برنامه زمان‌بندی افزوده شد",
    )
    PROJECT_SCHEDULE_DEPENDENCY_ADDED = (
        "project_schedule.dependency_added",
        "وابستگی برنامه زمان‌بندی افزوده شد",
    )
    PROJECT_CONTROL_ITEM_RECORDED = (
        "project_control.item_recorded",
        "مورد کنترل پروژه ثبت شد",
    )
    PROJECT_CONTROL_STATUS_RECORDED = (
        "project_control.status_recorded",
        "گذار وضعیت مورد کنترل پروژه ثبت شد",
    )
    PROJECT_CHANGE_PROPOSED = (
        "project_change.proposed",
        "پیشنهاد تغییر پروژه ثبت شد",
    )
    PROJECT_REBASELINE_PROPOSED = (
        "project_rebaseline.proposed",
        "پیشنهاد بازخط‌مبنا ثبت شد",
    )
    PROJECT_CONTROLS_EXPORTED = (
        "project_controls.exported",
        "خروجی ایمن کنترل پروژه ایجاد شد",
    )
    EXPENSE_RECORDED = "expense.recorded", "هزینه ثبت شد"
    EXPENSE_DRAFT_CREATED = "expense.draft_created", "پیش‌نویس هزینه ایجاد شد"
    EXPENSE_ALLOCATION_ADDED = "expense.allocation_added", "تخصیص هزینه ثبت شد"
    EXPENSE_SUBMITTED = "expense.submitted", "هزینه برای تأیید ارسال شد"
    EXPENSE_APPROVED = "expense.approved", "هزینه تأیید شد"
    EXPENSE_RETURNED = "expense.returned", "هزینه برای اصلاح بازگردانده شد"
    EXPENSE_RECURRENCE_PROPOSED = (
        "expense.recurrence_proposed",
        "پیشنهاد هزینه تکرارشونده ایجاد شد",
    )
    EXPENSE_VOIDED = "expense.voided", "هزینه باطل شد"
    EXPENSE_CATEGORY_CREATED = "expense_category.created", "دسته هزینه ایجاد شد"
    EXPENSE_CATEGORY_UPDATED = "expense_category.updated", "دسته هزینه ویرایش شد"
    EXPENSE_CATEGORY_ARCHIVED = "expense_category.archived", "دسته هزینه بایگانی شد"
    PLATFORM_EXPENSE_GROUP_CREATED = (
        "platform_expense_group.created",
        "گروه اصلی هزینه ایجاد شد",
    )
    PLATFORM_EXPENSE_GROUP_UPDATED = (
        "platform_expense_group.updated",
        "گروه اصلی هزینه ویرایش شد",
    )
    PLATFORM_EXPENSE_GROUP_ARCHIVED = (
        "platform_expense_group.archived",
        "گروه اصلی هزینه بایگانی شد",
    )
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
    DOCUMENT_CATEGORY_CREATED = (
        "document.category_created",
        "دسته‌بندی سند ایجاد شد",
    )
    DOCUMENT_PROCESSING_ASSESSED = (
        "document.processing_assessed",
        "ارزیابی پردازش سند ثبت شد",
    )
    DOCUMENT_SIGNATURE_EVIDENCE_RECORDED = (
        "document.signature_evidence_recorded",
        "شاهد امضای سند ثبت شد",
    )
    DOCUMENT_RETENTION_POLICY_CREATED = (
        "document.retention_policy_created",
        "سیاست نگهداری سند ایجاد شد",
    )
    DOCUMENT_RETENTION_POLICY_APPROVED = (
        "document.retention_policy_approved",
        "سیاست نگهداری سند تأیید شد",
    )
    DOCUMENT_RETENTION_APPLIED = (
        "document.retention_applied",
        "سیاست نگهداری به سند اعمال شد",
    )
    DOCUMENT_HOLD_PLACED = "document.hold_placed", "نگهداری حقوقی سند ثبت شد"
    DOCUMENT_HOLD_RELEASED = (
        "document.hold_released",
        "نگهداری حقوقی سند آزاد شد",
    )
    DOCUMENT_DISPOSAL_REQUESTED = (
        "document.disposal_requested",
        "قصد امحای سند درخواست شد",
    )
    DOCUMENT_DISPOSAL_REVIEWED = (
        "document.disposal_reviewed",
        "قصد امحای سند بررسی شد",
    )
    DOCUMENT_EXPORT_MANIFEST_CREATED = (
        "document.export_manifest_created",
        "مانیفست خروجی سند ایجاد شد",
    )
    DOCUMENT_KEY_CUSTODY_ATTESTED = (
        "document.key_custody_attested",
        "شاهد نگهداری کلید ثبت شد",
    )
    DOCUMENT_RECOVERY_RECONCILED = (
        "document.recovery_reconciled",
        "مرز بازیابی سند تطبیق شد",
    )
    DOCUMENT_RESTORE_EVIDENCE_APPROVED = (
        "document.restore_evidence_approved",
        "شاهد بازیابی سند تأیید شد",
    )
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
    MEMBERSHIP_ROLE_ASSIGNED = (
        "authorization.role_assigned",
        "نقش مستقل عضویت تخصیص یافت",
    )
    MEMBERSHIP_ROLE_REVOKED = (
        "authorization.role_revoked",
        "نقش مستقل عضویت لغو شد",
    )
    MEMBERSHIP_SCOPE_GRANTED = (
        "authorization.scope_granted",
        "دامنه دسترسی عضویت اعطا شد",
    )
    MEMBERSHIP_SCOPE_REVOKED = (
        "authorization.scope_revoked",
        "دامنه دسترسی عضویت لغو شد",
    )
    AUTHORIZATION_MIGRATION_ROLLED_BACK = (
        "authorization.migration_rolled_back",
        "خواندن نقش سازگار بازگردانی شد",
    )
    PLATFORM_ROLE_ASSIGNED = (
        "authorization.platform_role_assigned",
        "نقش پلتفرمی تخصیص یافت",
    )
    PLATFORM_ROLE_REVOKED = (
        "authorization.platform_role_revoked",
        "نقش پلتفرمی لغو شد",
    )
    PROTECTED_OPERATION_CLASSIFIED = (
        "authorization.protected_operation_classified",
        "عملیات حفاظت‌شده طبقه‌بندی شد",
    )
    PROTECTED_OPERATION_RETIRED = (
        "authorization.protected_operation_retired",
        "عملیات حفاظت‌شده بازنشسته شد",
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
    ROLE_ARCHIVED = "role.archived", "نقش شرکتی بایگانی شد"


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
    correlation_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    changes = models.JSONField("تغییرات", default=dict, blank=True)
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
