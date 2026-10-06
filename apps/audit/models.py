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
    PLATFORM_POLICY_VERSION_UPDATED = (
        "policy.version_updated",
        "نسخه پیش‌نویس سیاست پلتفرم به‌روزرسانی شد",
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
    CONTRACT_TERM_VERSION_CREATED = (
        "contract.term_version_created",
        "نسخه شرایط تجاری قرارداد ایجاد شد",
    )
    CONTRACT_TERM_VERSION_APPROVED = (
        "contract.term_version_approved",
        "نسخه شرایط تجاری قرارداد تأیید شد",
    )
    CONTRACTUAL_RECORD_CREATED = (
        "contractual_record.created",
        "نسخه رکورد قراردادی ایجاد شد",
    )
    CONTRACTUAL_RECORD_SUBMITTED = (
        "contractual_record.submitted",
        "رکورد قراردادی ارسال شد",
    )
    CONTRACTUAL_RECORD_APPROVED = (
        "contractual_record.approved",
        "نتیجه رکورد قراردادی تأیید شد",
    )
    CONTRACTUAL_RECORD_RETURNED = (
        "contractual_record.returned",
        "رکورد قراردادی بازگردانده شد",
    )
    CONTRACTUAL_RECORD_WITHDRAWN = (
        "contractual_record.withdrawn",
        "رکورد قراردادی مسترد شد",
    )
    CONTRACTUAL_RECORD_SUPERSEDED = (
        "contractual_record.superseded",
        "رکورد قراردادی جایگزین شد",
    )
    CONTRACTUAL_RECORD_CANCELLED = (
        "contractual_record.cancelled",
        "رکورد قراردادی با نسخه پیوندخورده باطل شد",
    )
    CONTRACTUAL_EVIDENCE_LINKED = (
        "contractual_record.evidence_linked",
        "شاهد به رکورد قراردادی پیوند خورد",
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
    PROGRESS_CLAIM_CORRECTION_CREATED = (
        "progress_claim.correction_created",
        "اصلاح پیوندخورده صورت‌وضعیت ایجاد شد",
    )
    PROGRESS_CLAIM_SUPERSEDED = (
        "progress_claim.superseded",
        "صورت‌وضعیت با اصلاح جایگزین شد",
    )
    PROGRESS_CLAIM_CANCELLED = (
        "progress_claim.cancelled",
        "صورت‌وضعیت با سند پیوندخورده باطل شد",
    )
    CLAIM_SETTLEMENT_ALLOCATED = (
        "claim_settlement.allocated",
        "دریافت به صورت‌وضعیت تخصیص یافت",
    )
    CLAIM_SETTLEMENT_REVERSED = (
        "claim_settlement.reversed",
        "تسویه صورت‌وضعیت برگشت داده شد",
    )
    PAYABLE_MEASUREMENT_RECORDED = (
        "payable_measurement.recorded",
        "اندازه‌گیری پیمان جزء ثبت شد",
    )
    PAYABLE_MEASUREMENT_SUBMITTED = (
        "payable_measurement.submitted",
        "اندازه‌گیری پیمان جزء ارسال شد",
    )
    PAYABLE_MEASUREMENT_VERIFIED = (
        "payable_measurement.verified",
        "اندازه‌گیری پیمان جزء راستی‌آزمایی شد",
    )
    PAYABLE_MEASUREMENT_REJECTED = (
        "payable_measurement.rejected",
        "اندازه‌گیری پیمان جزء رد شد",
    )
    PAYABLE_CERTIFICATE_CREATED = (
        "payable_certificate.created",
        "گواهی پرداخت ایجاد شد",
    )
    PAYABLE_CERTIFICATE_SUBMITTED = (
        "payable_certificate.submitted",
        "گواهی پرداخت ارسال شد",
    )
    PAYABLE_CERTIFICATE_APPROVED = (
        "payable_certificate.approved",
        "گواهی پرداخت تأیید شد",
    )
    PAYABLE_CERTIFICATE_RETURNED = (
        "payable_certificate.returned",
        "گواهی پرداخت بازگردانده شد",
    )
    PAYABLE_CERTIFICATE_CORRECTION_CREATED = (
        "payable_certificate.correction_created",
        "اصلاح پیوندخورده گواهی پرداخت ایجاد شد",
    )
    PAYABLE_CERTIFICATE_SUPERSEDED = (
        "payable_certificate.superseded",
        "گواهی پرداخت با اصلاح جایگزین شد",
    )
    PAYABLE_CERTIFICATE_CANCELLED = (
        "payable_certificate.cancelled",
        "گواهی پرداخت با سند پیوندخورده باطل شد",
    )
    GUARANTEE_CREATED = "guarantee.created", "نسخه ضمانت‌نامه ایجاد شد"
    GUARANTEE_SUBMITTED = "guarantee.submitted", "ضمانت‌نامه ارسال شد"
    GUARANTEE_APPROVED = "guarantee.approved", "ضمانت‌نامه تأیید شد"
    GUARANTEE_RETURNED = "guarantee.returned", "ضمانت‌نامه بازگردانده شد"
    GUARANTEE_SUPERSEDED = "guarantee.superseded", "ضمانت‌نامه جایگزین شد"
    GUARANTEE_EXPIRED = "guarantee.expired", "ضمانت‌نامه منقضی شد"
    GUARANTEE_RELEASED = "guarantee.released", "ضمانت‌نامه آزاد شد"
    COMPLIANCE_EVIDENCE_CREATED = (
        "compliance_evidence.created",
        "شاهد بیمه یا مفاصاحساب ایجاد شد",
    )
    COMPLIANCE_EVIDENCE_SUBMITTED = (
        "compliance_evidence.submitted",
        "شاهد بیمه یا مفاصاحساب ارسال شد",
    )
    COMPLIANCE_EVIDENCE_APPROVED = (
        "compliance_evidence.approved",
        "شاهد بیمه یا مفاصاحساب تأیید شد",
    )
    COMPLIANCE_EVIDENCE_RETURNED = (
        "compliance_evidence.returned",
        "شاهد بیمه یا مفاصاحساب بازگردانده شد",
    )
    COMPLIANCE_EVIDENCE_SUPERSEDED = (
        "compliance_evidence.superseded",
        "شاهد بیمه یا مفاصاحساب جایگزین شد",
    )
    COMPLIANCE_EVIDENCE_EXPIRED = (
        "compliance_evidence.expired",
        "شاهد بیمه یا مفاصاحساب منقضی شد",
    )
    RETENTION_RELEASE_CREATED = (
        "retention_release.created",
        "آزادسازی کسور تضمین ایجاد شد",
    )
    RETENTION_RELEASE_SUBMITTED = (
        "retention_release.submitted",
        "آزادسازی کسور تضمین ارسال شد",
    )
    RETENTION_RELEASE_APPROVED = (
        "retention_release.approved",
        "آزادسازی کسور تضمین تأیید شد",
    )
    RETENTION_RELEASE_RETURNED = (
        "retention_release.returned",
        "آزادسازی کسور تضمین بازگردانده شد",
    )
    RETENTION_RELEASE_SUPERSEDED = (
        "retention_release.superseded",
        "آزادسازی کسور تضمین جایگزین شد",
    )
    RETENTION_RELEASE_CANCELLED = (
        "retention_release.cancelled",
        "آزادسازی کسور تضمین باطل شد",
    )
    TAXPAYER_INVOICE_CREATED = (
        "taxpayer_invoice.created",
        "نسخه صورتحساب مؤدیان ایجاد شد",
    )
    TAXPAYER_INVOICE_SUBMITTED = (
        "taxpayer_invoice.submitted",
        "صورتحساب مؤدیان برای تأیید ارسال شد",
    )
    TAXPAYER_INVOICE_APPROVED = (
        "taxpayer_invoice.approved",
        "صورتحساب مؤدیان تأیید شد",
    )
    TAXPAYER_INVOICE_RETURNED = (
        "taxpayer_invoice.returned",
        "صورتحساب مؤدیان بازگردانده شد",
    )
    CONTRACTOR_COMPLIANCE_CREATED = (
        "contractor_compliance.created",
        "ارزیابی انطباق بیمه پیمانکار ایجاد شد",
    )
    CONTRACTOR_COMPLIANCE_SUBMITTED = (
        "contractor_compliance.submitted",
        "ارزیابی انطباق بیمه پیمانکار ارسال شد",
    )
    CONTRACTOR_COMPLIANCE_APPROVED = (
        "contractor_compliance.approved",
        "ارزیابی انطباق بیمه پیمانکار تأیید شد",
    )
    CONTRACTOR_COMPLIANCE_RETURNED = (
        "contractor_compliance.returned",
        "ارزیابی انطباق بیمه پیمانکار بازگردانده شد",
    )
    STATUTORY_SUBMISSION_RECORDED = (
        "statutory_submission.recorded",
        "شاهد خروجی یا ارسال مقرراتی ثبت شد",
    )
    STATUTORY_SUBMISSION_RESOLVED = (
        "statutory_submission.resolved",
        "شاهد حل انسانی ارسال مقرراتی ثبت شد",
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
    FIELD_OBSERVATION_CREATED = "field_observation.created", "مشاهده میدانی ایجاد شد"
    FIELD_OBSERVATION_SAVED = (
        "field_observation.saved",
        "پیش‌نویس مشاهده میدانی ذخیره شد",
    )
    FIELD_OBSERVATION_SUBMITTED = (
        "field_observation.submitted",
        "مشاهده میدانی ارسال شد",
    )
    FIELD_OBSERVATION_REVIEW_STARTED = (
        "field_observation.review_started",
        "بررسی مشاهده میدانی آغاز شد",
    )
    FIELD_OBSERVATION_ACCEPTED = (
        "field_observation.accepted",
        "مشاهده میدانی پذیرفته شد",
    )
    FIELD_OBSERVATION_REJECTED = "field_observation.rejected", "مشاهده میدانی رد شد"
    FIELD_OBSERVATION_CORRECTED = (
        "field_observation.corrected",
        "اصلاح مشاهده میدانی ایجاد شد",
    )
    FIELD_OBSERVATION_SUPERSEDED = (
        "field_observation.superseded",
        "مشاهده میدانی جایگزین شد",
    )
    FIELD_PROPOSAL_CREATED = "field_proposal.created", "پیشنهاد تحویل مشاهده ایجاد شد"
    FIELD_PROPOSAL_SUBMITTED = (
        "field_proposal.submitted",
        "پیشنهاد تحویل مشاهده ارسال شد",
    )
    FIELD_PROPOSAL_ACCEPTED = (
        "field_proposal.accepted",
        "پیشنهاد تحویل مشاهده پذیرفته شد",
    )
    FIELD_PROPOSAL_REJECTED = "field_proposal.rejected", "پیشنهاد تحویل مشاهده رد شد"
    COMPLIANCE_RECORD_CREATED = (
        "compliance.record_created",
        "رکورد کنترل HSE/QA ایجاد شد",
    )
    COMPLIANCE_TEMPLATE_PUBLISHED = (
        "compliance.template_published",
        "نسخه الگوی بازرسی منتشر شد",
    )
    COMPLIANCE_TRANSITIONED = "compliance.transitioned", "وضعیت کنترل HSE/QA تغییر کرد"
    COMPLIANCE_EVIDENCE_LINKED = (
        "compliance.evidence_linked",
        "نسخه شواهد HSE/QA پیوند شد",
    )
    COMPLIANCE_PROPOSAL_CREATED = (
        "compliance.proposal_created",
        "پیشنهاد پایین‌دستی HSE/QA ایجاد شد",
    )
    COMPLIANCE_EXPORTED = "compliance.exported", "خروجی کنترل‌شده HSE/QA ایجاد شد"
    COMPLIANCE_RECONCILED = "compliance.reconciled", "تطبیق HSE/QA اجرا شد"
    PARTNER_PROFILE_CREATED = "partner.profile_created", "پروفایل همکار ایجاد شد"
    PARTNER_REQUIREMENT_PUBLISHED = (
        "partner.requirement_published",
        "الزام همکار منتشر شد",
    )
    PARTNER_QUALIFICATION_CREATED = (
        "partner.qualification_created",
        "صلاحیت همکار ایجاد شد",
    )
    PARTNER_QUALIFICATION_TRANSITIONED = (
        "partner.qualification_transitioned",
        "وضعیت صلاحیت همکار تغییر کرد",
    )
    PARTNER_EVIDENCE_LINKED = "partner.evidence_linked", "شواهد همکار پیوند شد"
    PARTNER_CATEGORY_DECIDED = "partner.category_decided", "دسته همکار تصمیم‌گیری شد"
    PARTNER_EVALUATION_CREATED = "partner.evaluation_created", "ارزیابی همکار ایجاد شد"
    PARTNER_EVALUATION_TRANSITIONED = (
        "partner.evaluation_transitioned",
        "وضعیت ارزیابی همکار تغییر کرد",
    )
    PARTNER_EVALUATION_APPEALED = (
        "partner.evaluation_appealed",
        "اعتراض ارزیابی همکار ایجاد شد",
    )
    PARTNER_EVALUATION_APPEAL_DECIDED = (
        "partner.evaluation_appeal_decided",
        "اعتراض ارزیابی همکار تصمیم‌گیری شد",
    )
    PARTNER_PROPOSAL_CREATED = "partner.proposal_created", "پیشنهاد همکار ایجاد شد"
    SUPPORT_NOTIFICATION_CREATED = (
        "support.notification_created",
        "اعلان پشتیبانی ایجاد شد",
    )
    SUPPORT_NOTIFICATION_ACKNOWLEDGED = (
        "support.notification_acknowledged",
        "اعلان پشتیبانی تأیید شد",
    )
    SUPPORT_CASE_CREATED = "support.case_created", "مورد پشتیبانی ایجاد شد"
    SUPPORT_CASE_TRANSITIONED = (
        "support.case_transitioned",
        "وضعیت مورد پشتیبانی تغییر کرد",
    )
    SUPPORT_CASE_ASSIGNED = "support.case_assigned", "مورد پشتیبانی تخصیص یافت"
    SUPPORT_ACCESS_REQUESTED = "support.access_requested", "دسترسی پشتیبانی درخواست شد"
    SUPPORT_ACCESS_CONFIRMED = "support.access_confirmed", "دسترسی پشتیبانی تأیید شد"
    SUPPORT_ACCESS_APPROVED = "support.access_approved", "دسترسی پشتیبانی فعال شد"
    SUPPORT_ACCESS_REVOKED = "support.access_revoked", "دسترسی پشتیبانی ابطال شد"
    SUPPORT_ACCESS_USED = "support.access_used", "دسترسی پشتیبانی استفاده شد"
    SUPPORT_EVIDENCE_LINKED = "support.evidence_linked", "شواهد پشتیبانی پیوند شد"
    KNOWLEDGE_CANDIDATE_CREATED = "knowledge.candidate_created", "کاندید دانش ایجاد شد"
    KNOWLEDGE_CANDIDATE_SUBMITTED = (
        "knowledge.candidate_submitted",
        "کاندید دانش ارسال شد",
    )
    KNOWLEDGE_CANDIDATE_REVIEWED = (
        "knowledge.candidate_reviewed",
        "کاندید دانش بررسی شد",
    )
    KNOWLEDGE_CANDIDATE_APPROVED = (
        "knowledge.candidate_approved",
        "کاندید دانش تأیید شد",
    )
    KNOWLEDGE_PUBLICATION_PUBLISHED = (
        "knowledge.publication_published",
        "نسخه دانش منتشر شد",
    )
    KNOWLEDGE_PUBLICATION_SUPERSEDED = (
        "knowledge.publication_superseded",
        "نسخه دانش جایگزین شد",
    )
    KNOWLEDGE_PUBLICATION_WITHDRAWN = (
        "knowledge.publication_withdrawn",
        "نسخه دانش پس گرفته شد",
    )
    KNOWLEDGE_RECURRENCE_RECORDED = (
        "knowledge.recurrence_recorded",
        "شاهد تکرار دانش ثبت شد",
    )
    KNOWLEDGE_RECURRENCE_CORRECTED = (
        "knowledge.recurrence_corrected",
        "شاهد تکرار دانش اصلاح شد",
    )
    KNOWLEDGE_REUSE_RECORDED = (
        "knowledge.reuse_recorded",
        "شاهد استفاده مجدد دانش ثبت شد",
    )
    KNOWLEDGE_REUSE_CORRECTED = (
        "knowledge.reuse_corrected",
        "شاهد استفاده مجدد دانش اصلاح شد",
    )
    KNOWLEDGE_SENSITIVE_PROVENANCE_VIEWED = (
        "knowledge.sensitive_provenance_viewed",
        "منشأ حساس دانش مشاهده شد",
    )
    KNOWLEDGE_PROMOTION_REQUESTED = (
        "knowledge.promotion_requested",
        "ترویج دانش درخواست شد",
    )
    KNOWLEDGE_PROMOTION_REVIEWED = "knowledge.promotion_reviewed", "ترویج دانش بررسی شد"
    KNOWLEDGE_PROMOTION_APPROVED = "knowledge.promotion_approved", "ترویج دانش تأیید شد"
    KNOWLEDGE_PROMOTION_PUBLISHED = (
        "knowledge.promotion_published",
        "ترویج دانش منتشر شد",
    )
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
    WORKFORCE_SKILL_RECORDED = "workforce_skill.recorded", "مهارت نیروی انسانی ثبت شد"
    WORKFORCE_COMPETENCY_RECORDED = (
        "workforce_competency.recorded",
        "شایستگی نیروی انسانی ثبت شد",
    )
    EMPLOYEE_SKILL_RECORDED = "employee_skill.recorded", "سابقه مهارت کارمند ثبت شد"
    EMPLOYEE_QUALIFICATION_RECORDED = (
        "employee_qualification.recorded",
        "صلاحیت کارمند ثبت شد",
    )
    EMPLOYEE_QUALIFICATION_REVOKED = (
        "employee_qualification.revoked",
        "صلاحیت کارمند ابطال شد",
    )
    EMPLOYEE_QUALIFICATION_EVIDENCE_LINKED = (
        "employee_qualification.evidence_linked",
        "شاهد صلاحیت کارمند پیوند خورد",
    )
    TRAINING_REQUIREMENT_RECORDED = (
        "training_requirement.recorded",
        "الزام آموزشی ثبت شد",
    )
    EMPLOYEE_TRAINING_RECORDED = (
        "employee_training.recorded",
        "سابقه آموزش کارمند ثبت شد",
    )
    EMPLOYEE_TRAINING_EVIDENCE_LINKED = (
        "employee_training.evidence_linked",
        "شاهد آموزش کارمند پیوند خورد",
    )
    PERFORMANCE_EVALUATION_RECORDED = (
        "performance_evaluation.recorded",
        "ارزیابی عملکرد ثبت شد",
    )
    PERFORMANCE_EVALUATION_EVIDENCE_LINKED = (
        "performance_evaluation.evidence_linked",
        "شاهد ارزیابی عملکرد پیوند خورد",
    )
    LABOR_RATE_VERSION_RECORDED = (
        "labor_rate_version.recorded",
        "نسخه نرخ نیروی کار ثبت شد",
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
    PURCHASE_ORDER_CREATED_FROM_AWARD = (
        "purchase_order.created_from_award",
        "سفارش خرید از انتخاب منبع ایجاد شد",
    )
    PURCHASE_ORDER_CHANGE_REQUESTED = (
        "purchase_order.change_requested",
        "تغییر سفارش خرید درخواست شد",
    )
    PURCHASE_ORDER_CHANGE_DECIDED = (
        "purchase_order.change_decided",
        "تغییر سفارش خرید تعیین تکلیف شد",
    )
    RFQ_CREATED = "rfq.created", "استعلام خرید ایجاد شد"
    RFQ_LINE_ADDED = "rfq.line_added", "ردیف استعلام خرید افزوده شد"
    RFQ_SUBMITTED = "rfq.submitted", "استعلام خرید برای صدور ارسال شد"
    RFQ_ISSUED = "rfq.issued", "استعلام خرید صادر شد"
    RFQ_ADDENDUM_ISSUED = "rfq.addendum_issued", "الحاقیه استعلام خرید صادر شد"
    RFQ_CLOSED = "rfq.closed", "استعلام خرید بسته شد"
    RFQ_CANCELLED = "rfq.cancelled", "استعلام خرید لغو شد"
    RFQ_INVITATION_CREATED = "rfq.invitation_created", "دعوت‌نامه استعلام ایجاد شد"
    RFQ_INVITATION_UPDATED = (
        "rfq.invitation_updated",
        "وضعیت دعوت‌نامه استعلام تغییر کرد",
    )
    SUPPLIER_PORTAL_INVITATION_CREATED = (
        "supplier_portal.invitation_created",
        "دعوت‌نامه درگاه تأمین‌کننده ایجاد شد",
    )
    SUPPLIER_PORTAL_INVITATION_ACCEPTED = (
        "supplier_portal.invitation_accepted",
        "دعوت‌نامه درگاه تأمین‌کننده پذیرفته شد",
    )
    SUPPLIER_PORTAL_GRANT_REVOKED = (
        "supplier_portal.grant_revoked",
        "مجوز درگاه تأمین‌کننده لغو شد",
    )
    SUPPLIER_PORTAL_QUOTE_SUBMITTED = (
        "supplier_portal.quote_submitted",
        "پیشنهاد درگاه تأمین‌کننده ثبت شد",
    )
    RFQ_QUOTE_REVISION_CAPTURED = (
        "rfq.quote_revision_captured",
        "نسخه پیشنهاد مهروموم‌شده ثبت شد",
    )
    RFQ_QUOTE_REVISION_SUBMITTED = (
        "rfq.quote_revision_submitted",
        "نسخه پیشنهاد مهروموم‌شده نهایی شد",
    )
    RFQ_QUOTE_REVISION_WITHDRAWN = (
        "rfq.quote_revision_withdrawn",
        "نسخه پیشنهاد مهروموم‌شده بازپس‌گرفته شد",
    )
    RFQ_SEALED_EVIDENCE_CUSTODIED = (
        "rfq.sealed_evidence_custodied",
        "شاهد پیشنهاد در نگهداری مهروموم‌شده پذیرفته شد",
    )
    RFQ_SEALED_EVIDENCE_REJECTED = (
        "rfq.sealed_evidence_rejected",
        "تلاش نگهداری شاهد پیشنهاد رد شد",
    )
    RFQ_OPENING_REQUESTED = (
        "rfq.opening_requested",
        "درخواست گشایش پیشنهاد ثبت شد",
    )
    RFQ_OPENING_REQUEST_REJECTED = (
        "rfq.opening_request_rejected",
        "درخواست گشایش پیشنهاد رد شد",
    )
    RFQ_QUOTE_OPENED = "rfq.quote_opened", "پیشنهاد گشوده شد"
    RFQ_OPENING_APPROVAL_REJECTED = (
        "rfq.opening_approval_rejected",
        "تأیید گشایش پیشنهاد رد شد",
    )
    RFQ_CONFIDENTIAL_ACCESS_GRANTED = (
        "rfq.confidential_access_granted",
        "دسترسی محرمانه پیشنهاد اعطا شد",
    )
    RFQ_CONFIDENTIAL_ACCESS_REVOKED = (
        "rfq.confidential_access_revoked",
        "دسترسی محرمانه پیشنهاد لغو شد",
    )
    RFQ_CONFIDENTIAL_CONTENT_ACCESSED = (
        "rfq.confidential_content_accessed",
        "محتوای محرمانه پیشنهاد دریافت شد",
    )
    RFQ_CONFIDENTIAL_CONTENT_DENIED = (
        "rfq.confidential_content_denied",
        "دسترسی به محتوای محرمانه پیشنهاد رد شد",
    )
    RFQ_ADMISSIBILITY_PREPARED = (
        "rfq.admissibility_prepared",
        "آماده‌سازی پذیرش تجاری پیشنهاد ثبت شد",
    )
    RFQ_ADMISSIBILITY_WITHDRAWN = (
        "rfq.admissibility_withdrawn",
        "آماده‌سازی پذیرش تجاری پیشنهاد پس‌گرفته شد",
    )
    RFQ_ADMISSIBILITY_APPROVED = (
        "rfq.admissibility_approved",
        "تصمیم پذیرش تجاری پیشنهاد تأیید شد",
    )
    RFQ_ADMISSIBILITY_REJECTED = (
        "rfq.admissibility_rejected",
        "عملیات پذیرش تجاری پیشنهاد رد شد",
    )
    RFQ_COMPARISON_PREPARED = "rfq.comparison_prepared", "مقایسه تجاری آماده شد"
    RFQ_COMPARISON_EVALUATED = "rfq.comparison_evaluated", "مقایسه تجاری ارزیابی شد"
    RFQ_COMPARISON_FINALIZED = "rfq.comparison_finalized", "مقایسه تجاری نهایی شد"
    RFQ_EVALUATOR_CONFLICT_DECLARED = (
        "rfq.evaluator_conflict_declared",
        "تعارض ارزیاب اعلام شد",
    )
    RFQ_EVALUATOR_CONFLICT_DISPOSED = (
        "rfq.evaluator_conflict_disposed",
        "تعارض ارزیاب تعیین تکلیف شد",
    )
    RFQ_COMMERCIAL_EXCEPTION_DECIDED = (
        "rfq.commercial_exception_decided",
        "استثنای تجاری تعیین تکلیف شد",
    )
    RFQ_SOURCING_AWARD_PREPARED = (
        "rfq.sourcing_award_prepared",
        "انتخاب تأمین‌کننده آماده شد",
    )
    RFQ_SOURCING_AWARD_FINALIZED = (
        "rfq.sourcing_award_finalized",
        "انتخاب تأمین‌کننده نهایی شد",
    )
    GOODS_RECEIPT_CREATED = "goods_receipt.created", "رسید کالا ایجاد شد"
    GOODS_RECEIPT_ITEM_ADDED = "goods_receipt.item_added", "ردیف رسید کالا افزوده شد"
    GOODS_RECEIPT_POSTED = "goods_receipt.posted", "رسید کالا ثبت شد"
    GOODS_RECEIPT_VOIDED = "goods_receipt.voided", "رسید کالا باطل شد"
    SERVICE_ACCEPTANCE_ACCEPTED = (
        "service_acceptance.accepted",
        "پذیرش خدمت نهایی شد",
    )
    SUPPLIER_INVOICE_PREPARED = (
        "supplier_invoice.prepared",
        "صورتحساب تأمین‌کننده آماده شد",
    )
    SUPPLIER_INVOICE_DECIDED = (
        "supplier_invoice.decided",
        "صورتحساب تأمین‌کننده تعیین تکلیف شد",
    )
    SUPPLIER_INVOICE_MATCH_RETAINED = (
        "supplier_invoice.match_retained",
        "شاهد تطبیق صورتحساب نگهداری شد",
    )
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
    INVENTORY_TRACEABILITY_CONFIGURED = (
        "inventory.traceability_configured",
        "کنترل رهگیری موجودی پیکربندی شد",
    )
    INVENTORY_RESERVATION_TRANSITIONED = (
        "inventory.reservation_transitioned",
        "وضعیت رزرو موجودی تغییر کرد",
    )
    INVENTORY_COUNT_TRANSITIONED = (
        "inventory.count_transitioned",
        "وضعیت شمارش موجودی تغییر کرد",
    )
    INVENTORY_TRANSFER_TRANSITIONED = (
        "inventory.transfer_transitioned",
        "وضعیت انتقال امانی موجودی تغییر کرد",
    )
    EQUIPMENT_CREATED = "equipment.created", "تجهیز ایجاد شد"
    EQUIPMENT_STATUS_CHANGED = "equipment.status_changed", "وضعیت تجهیز تغییر کرد"
    EQUIPMENT_ARCHIVED = "equipment.archived", "تجهیز بایگانی شد"
    EQUIPMENT_OPERATION_RECORDED = "equipment.operation_recorded", "عملیات تجهیز ثبت شد"
    EQUIPMENT_OPERATION_CORRECTED = (
        "equipment.operation_corrected",
        "عملیات تجهیز اصلاح شد",
    )
    EQUIPMENT_WORK_ORDER_TRANSITIONED = (
        "equipment.work_order_transitioned",
        "وضعیت دستورکار تجهیز تغییر کرد",
    )
    EQUIPMENT_SPARE_PART_LINKED = (
        "equipment.spare_part_linked",
        "قطعه یدکی تجهیز پیوند شد",
    )
    EQUIPMENT_COST_POLICY_TRANSITIONED = (
        "equipment.cost_policy_transitioned",
        "سیاست هزینه تجهیز تغییر وضعیت داد",
    )
    EQUIPMENT_COST_ALLOCATION_TRANSITIONED = (
        "equipment.cost_allocation_transitioned",
        "تخصیص هزینه تجهیز تغییر وضعیت داد",
    )
    EQUIPMENT_COST_HANDOFF_TRANSITIONED = (
        "equipment.cost_handoff_transitioned",
        "پیشنهاد هزینه تجهیز تغییر وضعیت داد",
    )
    FIXED_ASSET_POLICY_TRANSITIONED = (
        "fixed_asset.policy_transitioned",
        "سیاست دارایی ثابت تغییر وضعیت داد",
    )
    FIXED_ASSET_TRANSITIONED = (
        "fixed_asset.transitioned",
        "دارایی ثابت تغییر وضعیت داد",
    )
    FIXED_ASSET_TRANSACTION_RECORDED = (
        "fixed_asset.transaction_recorded",
        "رویداد دارایی ثابت ثبت شد",
    )
    FIXED_ASSET_DEPRECIATION_TRANSITIONED = (
        "fixed_asset.depreciation_transitioned",
        "استهلاک دارایی ثابت تغییر وضعیت داد",
    )
    FIXED_ASSET_HANDOFF_TRANSITIONED = (
        "fixed_asset.handoff_transitioned",
        "پیشنهاد دارایی ثابت تغییر وضعیت داد",
    )
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
    TIME_CALENDAR_CONFIGURED = "time.calendar_configured", "تقویم یا شیفت ثبت شد"
    TIME_ATTENDANCE_CAPTURED = "time.attendance_captured", "حضور ثبت شد"
    TIME_ATTENDANCE_FINALIZED = "time.attendance_finalized", "حضور قطعی شد"
    TIME_ATTENDANCE_CORRECTED = "time.attendance_corrected", "حضور اصلاح یا برگشت شد"
    TIME_ATTENDANCE_IMPORTED = "time.attendance_imported", "ورودی حضور نگهداری شد"
    TIME_REQUEST_TRANSITIONED = (
        "time.request_transitioned",
        "درخواست زمانی تعیین تکلیف شد",
    )
    TIME_TIMESHEET_SUBMITTED = "time.timesheet_submitted", "کارکرد ارسال شد"
    TIME_TIMESHEET_REVIEWED = "time.timesheet_reviewed", "کارکرد بررسی شد"
    TIME_DISTRIBUTION_PREVIEWED = (
        "time.distribution_previewed",
        "پیش‌نمایش توزیع کار نگهداری شد",
    )
    PAYROLL_CONFIGURATION_RECORDED = (
        "payroll.configuration_recorded",
        "نسخه پیکربندی پرداخت ثبت شد",
    )
    PAYROLL_CONFIGURATION_ACTIVATED = (
        "payroll.configuration_activated",
        "نسخه پیکربندی پرداخت فعال شد",
    )
    PAYROLL_CONFIGURATION_RETIRED = (
        "payroll.configuration_retired",
        "نسخه پیکربندی پرداخت بازنشسته شد",
    )
    PAYROLL_COMPONENT_CONFIGURED = (
        "payroll.component_configured",
        "جزء حقوق پیکربندی شد",
    )
    PAYROLL_RULE_RECORDED = "payroll.rule_recorded", "نسخه قاعده حقوق ثبت شد"
    PAYROLL_RULE_ACTIVATED = "payroll.rule_activated", "نسخه قاعده حقوق فعال شد"
    PAYROLL_RULE_RETIRED = "payroll.rule_retired", "نسخه قاعده حقوق بازنشسته شد"
    PAYROLL_PERIOD_CREATED = "payroll.period_created", "دوره حقوق ایجاد شد"
    PAYROLL_RUN_CREATED = "payroll.run_created", "اجرای حقوق ایجاد شد"
    PAYROLL_INPUT_RECORDED = "payroll.input_recorded", "ورودی حقوق ثبت شد"
    PAYROLL_ADJUSTMENT_RECORDED = "payroll.adjustment_recorded", "تعدیل حقوق ثبت شد"
    PAYROLL_PREFLIGHT_FAILED = "payroll.preflight_failed", "پیش‌بررسی حقوق ناموفق بود"
    PAYROLL_INPUTS_LOCKED = "payroll.inputs_locked", "ورودی‌های حقوق قفل شد"
    PAYROLL_RUN_CALCULATED = "payroll.run_calculated", "اجرای حقوق محاسبه شد"
    PAYROLL_RUN_SUBMITTED = "payroll.run_submitted", "اجرای حقوق برای بررسی ارسال شد"
    PAYROLL_RUN_APPROVED = "payroll.run_approved", "اجرای حقوق تأیید شد"
    PAYROLL_RUN_FINALIZED = "payroll.run_finalized", "اجرای حقوق قطعی شد"
    PAYROLL_EXCEPTION_RESOLVED = "payroll.exception_resolved", "استثنای حقوق رفع شد"
    PAYROLL_RUN_REVERSED = "payroll.run_reversed", "اجرای حقوق برگشت و مرتبط شد"
    PAYROLL_STATUTORY_CALCULATED = (
        "payroll.statutory_calculated",
        "محاسبه مقرراتی حقوق ثبت شد",
    )
    PAYROLL_STATUTORY_REVIEWED = (
        "payroll.statutory_reviewed",
        "محاسبه مقرراتی حقوق بررسی شد",
    )
    PAYROLL_STATUTORY_IDENTITY_RECORDED = (
        "payroll.statutory_identity_recorded",
        "شاهد هویت مقرراتی حقوق ثبت شد",
    )
    PAYROLL_STATUTORY_OUTPUT_GENERATED = (
        "payroll.statutory_output_generated",
        "خروجی مقرراتی حقوق تولید شد",
    )
    PAYROLL_STATUTORY_EXPORT_RECORDED = (
        "payroll.statutory_export_recorded",
        "شاهد خروجی مقرراتی حقوق ثبت شد",
    )
    PAYROLL_STATUTORY_RESOLVED = (
        "payroll.statutory_resolved",
        "خطای خروجی مقرراتی حقوق تعیین تکلیف شد",
    )
    PAYROLL_FINANCIAL_HANDOFF_PREPARED = (
        "payroll.financial_handoff_prepared",
        "پیشنهاد تحویل مالی حقوق تهیه شد",
    )
    PAYROLL_FINANCIAL_HANDOFF_REVIEWED = (
        "payroll.financial_handoff_reviewed",
        "پیشنهاد تحویل مالی حقوق بررسی شد",
    )
    PAYROLL_FINANCIAL_HANDOFF_ACKNOWLEDGED = (
        "payroll.financial_handoff_acknowledged",
        "شاهد دریافت تحویل مالی حقوق ثبت شد",
    )
    PAYROLL_FINANCIAL_HANDOFF_RECONCILED = (
        "payroll.financial_handoff_reconciled",
        "تطبیق تحویل مالی حقوق ثبت شد",
    )
    PAYSLIP_VIEWED = "payroll.payslip_viewed", "فیش حقوق مشاهده شد"
    PAYSLIP_EXPORTED = "payroll.payslip_exported", "فیش حقوق خروجی گرفته شد"
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
    REPORTING_METRIC_REFRESHED = (
        "reporting.metric_refreshed",
        "شاخص حاکم‌شده بازسازی شد",
    )
    REPORTING_EXPORTED = "reporting.exported", "خروجی شاخص ایجاد شد"


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
