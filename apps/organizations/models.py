import calendar
import uuid
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone

from core.identifiers import (
    canonicalize_lower_identifier,
    canonicalize_upper_identifier,
)
from core.models import TimeStampedModel, UUIDModel

MAX_ORGANIZATION_LOGO_SIZE = 2 * 1024 * 1024
SUPPORTED_BASE_CURRENCY = "IRR"
ORGANIZATION_LOGO_SIGNATURES = {
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".webp": (b"RIFF",),
}
ORGANIZATION_LOGO_CONTENT_TYPES = {
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
    ".webp": {"image/webp"},
}


def organization_logo_upload_path(
    instance: "OrganizationSettings", filename: str
) -> str:
    """Store tenant logos under a tenant-owned, non-user-controlled name."""

    extension = Path(filename).suffix.lower()
    return f"organization-logos/{instance.organization_id}/{uuid.uuid4()}{extension}"


def validate_organization_logo(value: object) -> None:
    """Validate logo size, declared type, extension, and file signature."""

    filename = Path(str(getattr(value, "name", ""))).name
    extension = Path(filename).suffix.lower()
    if extension not in ORGANIZATION_LOGO_SIGNATURES:
        raise ValidationError("لوگو باید فایل PNG، JPEG یا WebP باشد.")

    size = getattr(value, "size", 0)
    if size <= 0:
        raise ValidationError("فایل لوگو خالی است.")
    if size > MAX_ORGANIZATION_LOGO_SIZE:
        raise ValidationError("حجم لوگو نباید بیشتر از ۲ مگابایت باشد.")

    content_type = getattr(value, "content_type", "")
    if content_type and content_type not in ORGANIZATION_LOGO_CONTENT_TYPES[extension]:
        raise ValidationError("نوع محتوای لوگو با پسوند آن مطابقت ندارد.")

    try:
        position = value.tell()
        header = value.read(12)
        value.seek(position)
    except (AttributeError, OSError):
        return
    valid_signature = any(
        header.startswith(signature)
        for signature in ORGANIZATION_LOGO_SIGNATURES[extension]
    )
    if extension == ".webp":
        valid_signature = valid_signature and header[8:12] == b"WEBP"
    if not valid_signature:
        raise ValidationError("محتوای فایل لوگو معتبر نیست.")


def validate_timezone_name(value: str) -> None:
    """Require an IANA timezone identifier understood by the runtime."""

    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValidationError("منطقه زمانی معتبر نیست.") from exc


def validate_supported_base_currency(value: str) -> None:
    """Fail closed until a later accepted design enables another base currency."""

    if canonicalize_upper_identifier(value) != SUPPORTED_BASE_CURRENCY:
        raise ValidationError("در محدوده فعلی فقط واحد پول پایه IRR پشتیبانی می‌شود.")


class OrganizationLanguage(models.TextChoices):
    PERSIAN = "fa", "فارسی"
    ENGLISH = "en", "English"


class OrganizationStatus(models.TextChoices):
    ACTIVE = "active", "فعال"
    SUSPENDED = "suspended", "تعلیق‌شده"
    CANCELLED = "cancelled", "لغوشده"
    ARCHIVED = "archived", "بایگانی‌شده"


class MembershipRole(models.TextChoices):
    """Stable codes for the protected roles shipped with the product."""

    COMPANY_OWNER = "company_owner", "Company Owner"
    COMPANY_MANAGER = "company_manager", "Company Manager"
    OPERATIONS_MANAGER = "operations_manager", "Operations Manager"
    MEMBER = "member", "Member"
    VIEWER = "viewer", "Viewer"

    TENANT_OWNER = "tenant_owner", "Tenant Owner"
    TENANT_ADMIN = "tenant_admin", "Tenant Admin"
    TENANT_MANAGER = "tenant_manager", "Tenant Manager"
    PROJECT_MANAGER = "project_manager", "Project Manager"
    ACCOUNTANT = "accountant", "Accountant"
    SUPERVISOR = "supervisor", "Supervisor"


class MembershipStatus(models.TextChoices):
    PENDING_ROLE = "pending_role", "در انتظار تعیین نقش"
    ACTIVE = "active", "فعال"
    SUSPENDED = "suspended", "تعلیق‌شده"
    REVOKED = "revoked", "لغوشده"


class AuthorizationScopeType(models.TextChoices):
    ORGANIZATION = "organization", "کل سازمان"
    PROJECT = "project", "پروژه"
    SITE = "site", "کارگاه"


class PlatformRoleCode(models.TextChoices):
    PLATFORM_ADMIN = "platform_admin", "Platform Admin"
    PLATFORM_OPERATIONS = "platform_operations", "Platform Operations"
    PLATFORM_SECURITY = "platform_security", "Platform Security"
    RESTORE_EVIDENCE_APPROVER = (
        "restore_evidence_approver",
        "Restore Evidence Approver",
    )


class ProtectedOperationCode(models.TextChoices):
    SELF_GRANT = "authorization.self_grant", "افزایش دسترسی خود"
    OWN_PRIVILEGED_ROLE = (
        "authorization.own_privileged_role",
        "تخصیص یا تأیید نقش ممتاز خود",
    )
    OWN_SUPPORT_ACCESS = (
        "authorization.own_support_access",
        "دسترسی پشتیبانی یا اضطراری خود",
    )
    AUTHORIZATION_POLICY_WEAKEN = (
        "authorization.policy_weaken",
        "تضعیف سیاست امنیت یا مجوز",
    )
    AUDIT_CONTROL_WEAKEN = (
        "authorization.audit_control_weaken",
        "تضعیف کنترل ممیزی یا امنیت",
    )
    PROTECTED_CLASSIFICATION_CHANGE = (
        "authorization.protected_classification_change",
        "تغییر طبقه‌بندی عملیات حفاظت‌شده",
    )
    DOCUMENT_HOLD_RELEASE = (
        "documents.hold_release",
        "آزادسازی نگهداری حقوقی سند",
    )
    DOCUMENT_DISPOSAL_APPROVAL = (
        "documents.disposal_approval",
        "تأیید قصد امحای سند",
    )
    ACCOUNTING_JOURNAL_POST = "accounting.journal_post", "ثبت قطعی سند حسابداری"
    ACCOUNTING_OPENING_ACCEPT = "accounting.opening_accept", "پذیرش مانده افتتاحیه"
    ACCOUNTING_JOURNAL_REVERSE = "accounting.journal_reverse", "برگشت سند حسابداری"
    ACCOUNTING_PERIOD_CLOSE = "accounting.period_close", "بستن دوره مالی"
    ACCOUNTING_PERIOD_REOPEN = "accounting.period_reopen", "بازگشایی دوره مالی"
    ACCOUNTING_RECONCILIATION_SIGN_OFF = (
        "accounting.reconciliation_sign_off",
        "تأیید نهایی تطبیق حسابداری",
    )
    RFQ_QUOTE_REVEAL = (
        "rfq_quotes.reveal",
        "گشایش و افشای حفاظت‌شده پیشنهاد",
    )


class AccountConnectionRequestStatus(models.TextChoices):
    PENDING = "pending", "در انتظار پاسخ"
    ACCEPTED = "accepted", "پذیرفته‌شده"
    REJECTED = "rejected", "ردشده"


class PolicyCategory(models.TextChoices):
    BASE_CURRENCY = "base_currency", "ارز پایه"
    DISPLAY_CALENDAR = "display_calendar", "تقویم نمایشی"
    FISCAL_CALENDAR = "fiscal_calendar", "تقویم مالی"
    PRECISION = "precision", "دقت محاسبات"
    ROUNDING = "rounding", "گرد کردن"
    REGULATORY_RULE_SET = "regulatory_rule_set", "مجموعه قواعد مقرراتی"
    FILING_EXPORT = "filing_export", "ارسال یا خروجی مقرراتی"
    INSURANCE_REGULATORY = "insurance_regulatory", "بیمه و مقررات"
    OTHER = "other", "سایر"


class PolicySensitivity(models.TextChoices):
    OPERATIONAL = "operational", "عملیاتی"
    ACCOUNTING = "accounting", "حسابداری"
    REGULATORY = "regulatory", "مقرراتی"


class PolicySourceBasis(models.TextChoices):
    PRODUCT_DEFINED = "product_defined", "سیاست فنی/کسب‌وکاری محصول"
    EXTERNAL_AUTHORITY = "external_authority", "مرجع بیرونی قانونی/مقرراتی/حسابداری"


class PolicyVersionStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    PUBLISHED = "published", "منتشرشده"
    RETIRED = "retired", "بازنشسته"


class TenantPolicySelectionStatus(models.TextChoices):
    APPROVED = "approved", "انتخاب‌شده توسط مدیر Tenant"
    ACTIVE = "active", "اعمال‌شده توسط مدیر Tenant"
    SUPERSEDED = "superseded", "جایگزین‌شده"


class PolicyReviewDisposition(models.TextChoices):
    ACCEPTED = "accepted", "پذیرفته‌شده"
    ACCEPTED_WITH_CONDITIONS = "accepted_with_conditions", "پذیرفته‌شده مشروط"
    REVISION_REQUIRED = "revision_required", "نیازمند بازنگری"
    REJECTED = "rejected", "ردشده"


class BusinessPermissionCode(models.TextChoices):
    """Business capabilities implemented and enforced by application services."""

    MEMBERSHIP_VIEW = "membership.view", "مشاهده اعضای شرکت"
    MEMBERSHIP_CHANGE_ROLE = "membership.change_role", "تغییر نقش اعضای شرکت"
    MEMBERSHIP_CHANGE_STATUS = "membership.change_status", "تغییر وضعیت اعضای شرکت"
    AUTHORIZATION_ROLES_VIEW = (
        "authorization_roles.view",
        "مشاهده نقش‌های عضویت",
    )
    AUTHORIZATION_ROLES_ASSIGN = (
        "authorization_roles.assign",
        "تخصیص نقش عضویت",
    )
    AUTHORIZATION_ROLES_REVOKE = (
        "authorization_roles.revoke",
        "لغو نقش عضویت",
    )
    AUTHORIZATION_GRANTS_VIEW = (
        "authorization_grants.view",
        "مشاهده دامنه‌های دسترسی",
    )
    AUTHORIZATION_GRANTS_CREATE = (
        "authorization_grants.create",
        "ایجاد دامنه دسترسی",
    )
    AUTHORIZATION_GRANTS_REVOKE = (
        "authorization_grants.revoke",
        "لغو دامنه دسترسی",
    )
    AUTHORIZATION_UNRESOLVED_RECOVER = (
        "authorization_unresolved.recover",
        "بازیابی کار حل‌نشده",
    )
    ACCOUNTS_CREATE = "accounts.create", "ایجاد حساب کاربری شرکت"
    ACCOUNTS_RESET_PASSWORD = (
        "accounts.reset_password",
        "بازنشانی گذرواژه اعضای شرکت",
    )
    COMPANY_SETTINGS_VIEW = "company.settings.view", "مشاهده تنظیمات شرکت"
    COMPANY_SETTINGS_CHANGE = "company.settings.change", "ویرایش تنظیمات شرکت"
    TENANT_POLICIES_VIEW = "tenant_policies.view", "مشاهده سیاست‌های Tenant"
    TENANT_POLICIES_APPROVE = (
        "tenant_policies.approve",
        "منسوخ — تأیید انتخاب سیاست‌های Tenant (بدون مسیر اجرایی)",
    )
    TENANT_POLICIES_APPLY = (
        "tenant_policies.apply",
        "اعمال سیاست‌های تأییدشده Tenant",
    )

    ACCOUNTING_VIEW = "accounting.view", "مشاهده حسابداری"
    ACCOUNTING_ACCOUNTS_MANAGE = "accounting.accounts_manage", "مدیریت کدینگ حساب‌ها"
    ACCOUNTING_PERIODS_MANAGE = "accounting.periods_manage", "مدیریت سال و دوره مالی"
    ACCOUNTING_JOURNALS_PREPARE = "accounting.journals_prepare", "تهیه سند حسابداری"
    ACCOUNTING_JOURNALS_SUBMIT = "accounting.journals_submit", "ارسال سند حسابداری"
    ACCOUNTING_JOURNALS_APPROVE = (
        "accounting.journals_approve",
        "تأیید مستقل سند حسابداری",
    )
    ACCOUNTING_JOURNALS_POST = "accounting.journals_post", "ثبت قطعی سند حسابداری"
    ACCOUNTING_RECONCILIATIONS_RUN = (
        "accounting.reconciliations_run",
        "اجرای تطبیق حسابداری",
    )
    ACCOUNTING_RECONCILIATIONS_DISPOSE = (
        "accounting.reconciliations_dispose",
        "ثبت تعیین تکلیف استثنای تطبیق حسابداری",
    )
    ACCOUNTING_RECONCILIATIONS_SIGN_OFF = (
        "accounting.reconciliations_sign_off",
        "بررسی و تأیید مستقل تطبیق حسابداری",
    )
    ACCOUNTING_REPORTS_VIEW = (
        "accounting.reports_view",
        "مشاهده گزارش‌ها و صورت‌های مالی حسابداری",
    )
    ACCOUNTING_STATEMENTS_RUN = (
        "accounting.statements_run",
        "نگهداری اجرای صورت مالی",
    )
    ACCOUNTING_ADJUSTMENTS_PREPARE = (
        "accounting.adjustments_prepare",
        "تهیه تعدیل کنترل‌شده",
    )
    ACCOUNTING_PERIODS_CLOSE = "accounting.periods_close", "بستن دوره مالی"
    ACCOUNTING_PERIODS_REOPEN = "accounting.periods_reopen", "بازگشایی دوره مالی"

    TREASURY_VIEW = "treasury.view", "مشاهده خزانه‌داری"
    TREASURY_ACCOUNTS_MANAGE = (
        "treasury.accounts_manage",
        "مدیریت حساب‌های خزانه‌داری",
    )
    TREASURY_SENSITIVE_VIEW = (
        "treasury.sensitive_view",
        "مشاهده شناسه‌های ماسک‌شده حساس خزانه‌داری",
    )
    TREASURY_MAPPINGS_MANAGE = (
        "treasury.mappings_manage",
        "مدیریت نگاشت حسابداری خزانه‌داری",
    )
    TREASURY_MOVEMENTS_CREATE = (
        "treasury.movements_create",
        "ایجاد حرکت خزانه‌داری",
    )
    TREASURY_MOVEMENTS_SUBMIT = (
        "treasury.movements_submit",
        "ارسال حرکت خزانه‌داری",
    )
    TREASURY_MOVEMENTS_APPROVE = (
        "treasury.movements_approve",
        "تأیید حرکت خزانه‌داری",
    )
    TREASURY_MOVEMENTS_POST = (
        "treasury.movements_post",
        "ثبت قطعی حرکت خزانه‌داری",
    )
    TREASURY_MOVEMENTS_REVERSE = (
        "treasury.movements_reverse",
        "برگشت حرکت خزانه‌داری",
    )
    TREASURY_CHEQUES_MANAGE = (
        "treasury.cheques_manage",
        "مدیریت چک‌های خزانه‌داری",
    )
    TREASURY_CHEQUES_CLEAR = (
        "treasury.cheques_clear",
        "ثبت وصول قطعی چک",
    )
    TREASURY_RECONCILIATIONS_RUN = (
        "treasury.reconciliations_run",
        "اجرای تطبیق خزانه‌داری با دفترکل",
    )
    TREASURY_RECONCILIATIONS_REVIEW = (
        "treasury.reconciliations_review",
        "بررسی مستقل تطبیق خزانه‌داری با دفترکل",
    )
    TREASURY_PAYMENT_REQUESTS_CREATE = (
        "treasury.payment_requests_create",
        "ایجاد درخواست پرداخت خزانه‌داری",
    )
    TREASURY_PAYMENT_REQUESTS_SUBMIT = (
        "treasury.payment_requests_submit",
        "ارسال درخواست پرداخت خزانه‌داری",
    )
    TREASURY_PAYMENT_REQUESTS_APPROVE = (
        "treasury.payment_requests_approve",
        "تأیید درخواست پرداخت خزانه‌داری",
    )
    TREASURY_PAYMENT_REQUESTS_RELEASE = (
        "treasury.payment_requests_release",
        "تخصیص پرداخت قطعی به درخواست",
    )
    TREASURY_ADVANCES_MANAGE = (
        "treasury.advances_manage",
        "مدیریت تنخواه کارمند و تأمین‌کننده",
    )
    TREASURY_ADVANCES_SETTLE = (
        "treasury.advances_settle",
        "ثبت و تأیید تسویه نقدی تنخواه",
    )
    TREASURY_ADVANCES_REVERSE = (
        "treasury.advances_reverse",
        "برگشت کنترل‌شده تنخواه یا تسویه",
    )
    TREASURY_STATEMENTS_IMPORT = (
        "treasury.statements_import",
        "پیش‌نمایش و لغو ورود صورتحساب بانکی",
    )
    TREASURY_STATEMENTS_ACCEPT = (
        "treasury.statements_accept",
        "پذیرش صورتحساب بانکی",
    )
    TREASURY_STATEMENT_MATCHES_MANAGE = (
        "treasury.statement_matches_manage",
        "مدیریت پیشنهاد و اصلاح تطبیق بانکی",
    )
    TREASURY_STATEMENT_MATCHES_CLEAR = (
        "treasury.statement_matches_clear",
        "تأیید تطبیق و تسویه بانکی",
    )
    TREASURY_BANK_RECONCILIATIONS_RUN = (
        "treasury.bank_reconciliations_run",
        "اجرای تطبیق بانکی",
    )

    SUBLEDGERS_VIEW = "subledgers.view", "مشاهده تعهدات AP/AR"
    SUBLEDGERS_OBLIGATIONS_RECOGNIZE = (
        "subledgers.obligations_recognize",
        "شناسایی تعهد AP/AR از منبع ثبت‌شده",
    )
    SUBLEDGERS_SETTLEMENTS_ALLOCATE = (
        "subledgers.settlements_allocate",
        "تخصیص تسویه خزانه‌داری به تعهد AP/AR",
    )
    SUBLEDGERS_SETTLEMENTS_REVERSE = (
        "subledgers.settlements_reverse",
        "برگشت تخصیص تسویه AP/AR",
    )
    SUBLEDGERS_AGING_RUN = "subledgers.aging_run", "اجرای aging دقیق AP/AR"
    SUBLEDGERS_RECONCILIATIONS_RUN = (
        "subledgers.reconciliations_run",
        "اجرای تطبیق زیر‌دفتر AP/AR",
    )
    SUBLEDGERS_RECONCILIATIONS_REVIEW = (
        "subledgers.reconciliations_review",
        "بررسی مستقل تطبیق زیر‌دفتر AP/AR",
    )
    SUBLEDGERS_WRITEOFFS_PROPOSE = (
        "subledgers.writeoffs_propose",
        "پیشنهاد سوخت مانده AP/AR",
    )
    SUBLEDGERS_WRITEOFFS_APPROVE = (
        "subledgers.writeoffs_approve",
        "تأیید سوخت مانده AP/AR (در انتظار سیاست)",
    )
    SUBLEDGERS_WRITEOFFS_REVERSE = (
        "subledgers.writeoffs_reverse",
        "برگشت سوخت AP/AR (در انتظار سیاست)",
    )

    PARTIES_VIEW = "parties.view", "مشاهده طرف‌های تجاری"
    PARTIES_CREATE = "parties.create", "ایجاد طرف تجاری"
    PARTIES_CHANGE = "parties.change", "ویرایش طرف تجاری"
    PARTIES_ARCHIVE = "parties.archive", "بایگانی طرف تجاری"
    PARTIES_MERGE = "parties.merge", "ثبت ادغام طرف تجاری"
    PARTY_RESTRICTIONS_MANAGE = (
        "party_restrictions.manage",
        "مدیریت محدودیت‌های طرف تجاری",
    )
    PARTY_GOVERNANCE_MANAGE = (
        "party_governance.manage",
        "مدیریت شواهد و دسته‌بندی طرف تجاری",
    )
    PARTY_ROLES_ASSIGN = "party_roles.assign", "تخصیص نقش به طرف تجاری"
    PARTY_CONTACTS_ADD = "party_contacts.add", "افزودن راه ارتباطی طرف تجاری"

    UNITS_VIEW = "units.view", "مشاهده واحدهای اندازه‌گیری"
    UNITS_CREATE = "units.create", "ایجاد واحد اندازه‌گیری"
    UNITS_ARCHIVE = "units.archive", "بایگانی واحد اندازه‌گیری"
    UOM_CONVERSIONS_MANAGE = (
        "units.conversions_manage",
        "مدیریت تبدیل نسخه‌دار واحدها",
    )
    UOM_ROUNDING_MANAGE = "units.rounding_manage", "مدیریت سیاست گرد کردن کمیت"
    UOM_CONVERT = "units.convert", "اجرای تبدیل کمیت"
    MATERIAL_CATEGORIES_VIEW = (
        "material_categories.view",
        "مشاهده دسته‌بندی‌های مصالح",
    )
    MATERIAL_CATEGORIES_CREATE = (
        "material_categories.create",
        "ایجاد دسته‌بندی مصالح",
    )
    MATERIAL_CATEGORIES_CHANGE = (
        "material_categories.change",
        "ویرایش دسته‌بندی مصالح",
    )
    MATERIAL_CATEGORIES_ARCHIVE = (
        "material_categories.archive",
        "بایگانی دسته‌بندی مصالح",
    )
    MATERIALS_VIEW = "materials.view", "مشاهده مصالح"
    MATERIALS_CREATE = "materials.create", "ایجاد مصالح"
    MATERIALS_CHANGE = "materials.change", "ویرایش مصالح"
    MATERIALS_ARCHIVE = "materials.archive", "بایگانی مصالح"
    MATERIALS_STEWARD = "materials.steward", "راهبری هویت مصالح"
    MATERIALS_MERGE = "materials.merge", "ادغام غیرمخرب مصالح"
    MATERIAL_ATTRIBUTE_DEFINITIONS_MANAGE = (
        "material_attributes.definitions_manage",
        "مدیریت تعریف نسخه‌دار ویژگی مصالح",
    )
    MATERIAL_ATTRIBUTES_APPLY = "material_attributes.apply", "اعمال ویژگی مصالح"
    MATERIAL_ATTRIBUTES_IMPORT = "material_attributes.import", "درون‌ریزی ویژگی مصالح"
    MATERIAL_PRICE_OBSERVATIONS_RECORD = (
        "material_prices.observations_record",
        "ثبت مشاهده قیمت مصالح",
    )
    MATERIAL_RELATIONSHIPS_MANAGE = (
        "material_relationships.manage",
        "مدیریت هم‌ارز/جایگزین مصالح",
    )
    MATERIAL_TECHNICAL_SUBMIT = "material_technical.submit", "ارسال بررسی فنی مصالح"
    MATERIAL_TECHNICAL_REVIEW = "material_technical.review", "بازبینی فنی مصالح"
    MATERIAL_TECHNICAL_APPROVE = "material_technical.approve", "تأیید فنی مصالح"
    MATERIAL_DOCUMENTS_LINK = "material_documents.link", "پیوند سند فنی مصالح"

    PROJECTS_VIEW = "projects.view", "مشاهده پروژه‌ها"
    PROJECTS_CREATE = "projects.create", "ایجاد پروژه"
    PROJECTS_ARCHIVE = "projects.archive", "بایگانی پروژه"
    PROJECT_SITES_VIEW = "project_sites.view", "مشاهده کارگاه‌های پروژه"
    PROJECT_SITES_CREATE = "project_sites.create", "ایجاد کارگاه پروژه"
    PROJECT_PHASES_VIEW = "project_phases.view", "مشاهده فازهای پروژه"
    PROJECT_PHASES_CREATE = "project_phases.create", "ایجاد فاز پروژه"
    PROJECT_PHASES_TRANSITION = (
        "project_phases.transition",
        "تغییر وضعیت فاز پروژه",
    )
    PROJECT_CONTROLS_VIEW = "project_controls.view", "مشاهده کنترل پروژه"
    PROJECT_CONTROLS_COMPARE = (
        "project_controls.compare",
        "مقایسه بودجه پذیرفته‌شده و شواهد هزینه پروژه",
    )
    PROJECT_CONTROLS_EXCEPTIONS_VIEW = (
        "project_controls.exceptions_view",
        "مشاهده استثناهای محدود کنترل پروژه",
    )
    PROJECT_CONTROLS_EXPORT = (
        "project_controls.export",
        "خروجی ایمن کنترل پروژه",
    )
    WBS_NODES_VIEW = "wbs_nodes.view", "مشاهده ساختار شکست"
    WBS_NODES_CREATE = "wbs_nodes.create", "ایجاد گره ساختار شکست"
    WBS_NODES_CHANGE = "wbs_nodes.change", "ویرایش گره ساختار شکست"
    WBS_NODES_ARCHIVE = "wbs_nodes.archive", "بایگانی گره ساختار شکست"
    ACTIVITIES_VIEW = "activities.view", "مشاهده فعالیت‌های پروژه"
    ACTIVITIES_CREATE = "activities.create", "ایجاد فعالیت پروژه"
    ACTIVITIES_TRANSITION = "activities.transition", "تغییر وضعیت فعالیت پروژه"
    ACTIVITIES_ARCHIVE = "activities.archive", "بایگانی فعالیت پروژه"

    CONTRACTS_VIEW = "contracts.view", "مشاهده قراردادها"
    CONTRACTS_CREATE = "contracts.create", "ایجاد قرارداد"
    CONTRACTS_CHANGE = "contracts.change", "ویرایش قرارداد"
    CONTRACTS_TRANSITION = "contracts.transition", "تغییر وضعیت قرارداد"
    CONTRACT_ITEMS_ADD = "contract_items.add", "افزودن ردیف قرارداد"
    CONTRACT_AMENDMENTS_APPROVE = (
        "contract_amendments.approve",
        "تأیید الحاقیه قرارداد",
    )

    BASELINES_VIEW = "baselines.view", "مشاهده مبناهای تجاری"
    BASELINES_MANAGE = "baselines.manage", "مدیریت مبناهای تجاری"
    BASELINES_APPROVE = "baselines.approve", "تأیید مبناهای تجاری"
    PROGRESS_VIEW = "progress.view", "مشاهده پیشرفت"
    PROGRESS_RECORD = "progress.record", "ثبت پیشرفت"
    PROGRESS_VERIFY = "progress.verify", "راستی‌آزمایی پیشرفت"
    CLAIMS_VIEW = "claims.view", "مشاهده صورت‌وضعیت‌ها"
    CLAIMS_CREATE = "claims.create", "ایجاد صورت‌وضعیت پیش‌نویس"
    CLAIMS_REVISE = "claims.revise", "بازنگری صورت‌وضعیت پیش‌نویس"
    CLAIMS_SUBMIT = "claims.submit", "ارسال صورت‌وضعیت"
    CLAIMS_APPROVE = "claims.approve", "تأیید یا بازگردانی صورت‌وضعیت"
    CLAIM_SETTLEMENTS_VIEW = "claim_settlements.view", "مشاهده تسویه صورت‌وضعیت"
    CLAIM_SETTLEMENTS_ALLOCATE = (
        "claim_settlements.allocate",
        "تخصیص دریافت به صورت‌وضعیت",
    )
    CLAIM_SETTLEMENTS_REVERSE = (
        "claim_settlements.reverse",
        "برگشت تسویه صورت‌وضعیت",
    )

    ESTIMATES_VIEW = "estimates.view", "مشاهده برآوردها"
    ESTIMATES_CREATE = "estimates.create", "ایجاد برآورد"
    ESTIMATE_ITEMS_ADD = "estimate_items.add", "افزودن ردیف برآورد"
    ESTIMATES_APPROVE = "estimates.approve", "تأیید برآوردها"
    ESTIMATES_REVISE = "estimates.revise", "ایجاد بازنگری برآورد"
    ESTIMATES_COMPARE = "estimates.compare", "مقایسه بازنگری‌های برآورد"
    ESTIMATE_COMPOSITION_MANAGE = (
        "estimate_composition.manage",
        "مدیریت ترکیب منابع برآورد",
    )
    ESTIMATE_ASSUMPTIONS_MANAGE = (
        "estimate_assumptions.manage",
        "مدیریت فرض‌ها و ضرایب برآورد",
    )
    ESTIMATE_RATE_SOURCES_MANAGE = (
        "estimate_rate_sources.manage",
        "مدیریت منبع و نرخ برآورد",
    )
    ESTIMATE_IMPORTS_PREVIEW = (
        "estimate_imports.preview",
        "پیش‌نمایش ورود برآورد",
    )
    COST_STRUCTURES_MANAGE = (
        "cost_structures.manage",
        "مدیریت نسخه‌های CBS و مرکز هزینه",
    )
    BUDGETS_VIEW = "budgets.view", "مشاهده بودجه‌های پروژه"
    BUDGETS_PREPARE = "budgets.prepare", "آماده‌سازی بودجه پروژه"
    BUDGETS_SUBMIT = "budgets.submit", "ارسال بودجه پروژه"
    BUDGETS_ACCEPT = "budgets.accept", "پذیرش مستقل مبنای بودجه"
    PROJECT_COST_SOURCES_MANAGE = (
        "project_cost.sources_manage",
        "مدیریت قراردادهای منبع هزینه پروژه",
    )
    PROJECT_COST_SOURCES_APPROVE = (
        "project_cost.sources_approve",
        "تأیید مستقل قراردادهای منبع هزینه پروژه",
    )
    PROJECT_COST_FACTS_RECORD = (
        "project_cost.facts_record",
        "ثبت برون‌داد طبقه‌بندی‌شده هزینه پروژه",
    )
    PROJECT_COSTS_VIEW = "project_cost.view", "مشاهده هزینه یکپارچه پروژه"
    PROJECT_COST_RECONCILIATIONS_VIEW = (
        "project_cost.reconciliations_view",
        "مشاهده تطبیق محدود شواهد هزینه پروژه",
    )
    PROJECT_COST_RECONCILIATIONS_EXPORT = (
        "project_cost.reconciliations_export",
        "خروجی تطبیق محدود شواهد هزینه پروژه",
    )
    PROJECT_FORECASTS_PREPARE = (
        "project_cost.forecasts_prepare",
        "آماده‌سازی پیش‌نویس پیش‌بینی هزینه پروژه",
    )
    PROJECT_SCHEDULES_VIEW = (
        "project_schedules.view",
        "مشاهده برنامه زمان‌بندی و کنترل تغییر پروژه",
    )
    PROJECT_SCHEDULES_PREPARE = (
        "project_schedules.prepare",
        "آماده‌سازی نسخه برنامه زمان‌بندی پروژه",
    )
    PROJECT_CONTROL_REGISTERS_MANAGE = (
        "project_control_registers.manage",
        "مدیریت ثبت محدودیت، مسئله، ریسک و تأخیر پروژه",
    )
    PROJECT_CONTROL_REGISTERS_VIEW = (
        "project_control_registers.view",
        "مشاهده ثبت محدودیت، مسئله، ریسک و تأخیر پروژه",
    )
    PROJECT_CHANGES_PROPOSE = (
        "project_changes.propose",
        "ثبت پیشنهاد تغییر پروژه بدون اثر قراردادی یا مالی",
    )
    PROJECT_CHANGES_VIEW = (
        "project_changes.view",
        "مشاهده پیشنهادهای تغییر پروژه",
    )
    PROJECT_REBASELINES_PROPOSE = (
        "project_rebaselines.propose",
        "ثبت پیشنهاد بازخط‌مبنا بدون پذیرش",
    )
    PROJECT_REBASELINES_VIEW = (
        "project_rebaselines.view",
        "مشاهده پیشنهادهای بازخط‌مبنا",
    )
    PROJECT_SCHEDULE_BASELINES_ACCEPT = (
        "project_schedules.accept",
        "پذیرش مبنای زمان‌بندی (غیرفعال تا تصمیم مالک محصول)",
    )
    PROJECT_CHANGES_APPROVE = (
        "project_changes.approve",
        "تأیید تغییر پروژه (غیرفعال تا تصمیم مالک محصول)",
    )
    PROJECT_REBASELINES_ACCEPT = (
        "project_rebaselines.accept",
        "پذیرش بازخط‌مبنا (غیرفعال تا تصمیم مالک محصول)",
    )

    EXPENSES_VIEW = "expenses.view", "مشاهده هزینه‌ها"
    EXPENSES_CREATE = "expenses.create", "ثبت هزینه"
    EXPENSES_SUBMIT = "expenses.submit", "ارسال هزینه برای تأیید"
    EXPENSES_APPROVE = "expenses.approve", "تأیید مستقل هزینه"
    EXPENSES_RETURN = "expenses.return", "بازگردانی هزینه برای اصلاح"
    EXPENSES_ALLOCATE = "expenses.allocate", "کدگذاری و تخصیص هزینه"
    EXPENSE_RECURRENCES_MANAGE = (
        "expenses.recurrences_manage",
        "مدیریت پیشنهادهای هزینه تکرارشونده",
    )
    EXPENSES_VOID = "expenses.void", "ابطال هزینه"
    EXPENSE_CATEGORIES_VIEW = "expense_categories.view", "مشاهده دسته‌های هزینه"
    EXPENSE_CATEGORIES_CREATE = "expense_categories.create", "ایجاد دسته هزینه"
    EXPENSE_CATEGORIES_CHANGE = "expense_categories.change", "ویرایش دسته هزینه"
    EXPENSE_CATEGORIES_ARCHIVE = (
        "expense_categories.archive",
        "بایگانی دسته هزینه",
    )

    PAYMENTS_VIEW = "payments.view", "مشاهده پرداخت‌ها"
    PAYMENTS_CREATE = "payments.create", "ثبت پرداخت"
    PAYMENTS_VOID = "payments.void", "ابطال پرداخت"
    PAYMENTS_ALLOCATE = "payments.allocate", "تخصیص پرداخت"

    DOCUMENTS_VIEW = "documents.view", "مشاهده اسناد"
    DOCUMENTS_UPLOAD = "documents.upload", "بارگذاری و نسخه‌بندی اسناد"
    DOCUMENTS_DOWNLOAD = "documents.download", "دانلود اسناد"
    DOCUMENTS_ARCHIVE = "documents.archive", "بایگانی اسناد"
    DOCUMENT_RETENTION_MANAGE = (
        "documents.retention_manage",
        "مدیریت پیش‌نویس سیاست نگهداری اسناد",
    )
    DOCUMENT_RETENTION_APPROVE = (
        "documents.retention_approve",
        "تأیید سیاست نگهداری اسناد",
    )
    DOCUMENT_HOLDS_PLACE = "documents.holds_place", "ثبت نگهداری حقوقی سند"
    DOCUMENT_HOLDS_RELEASE = "documents.holds_release", "آزادسازی نگهداری حقوقی سند"
    DOCUMENT_DISPOSALS_REQUEST = (
        "documents.disposals_request",
        "درخواست قصد امحای سند",
    )
    DOCUMENT_DISPOSALS_APPROVE = (
        "documents.disposals_approve",
        "تأیید قصد امحای سند",
    )
    DOCUMENTS_EXPORT = "documents.export", "خروجی کنترل‌شده اسناد"
    DOCUMENT_CATEGORIES_MANAGE = (
        "document_categories.manage",
        "مدیریت دسته‌بندی اسناد",
    )

    DAILY_REPORTS_VIEW = "daily_reports.view", "مشاهده گزارش‌های روزانه"
    DAILY_REPORTS_CREATE = "daily_reports.create", "ثبت گزارش روزانه"
    DAILY_REPORTS_ADD_LABOR = (
        "daily_reports.add_labor",
        "افزودن نیروی کار به گزارش روزانه",
    )
    DAILY_REPORTS_ADD_EQUIPMENT = (
        "daily_reports.add_equipment",
        "افزودن تجهیز به گزارش روزانه",
    )
    DAILY_REPORTS_ADD_MATERIAL = (
        "daily_reports.add_material",
        "افزودن مصالح به گزارش روزانه",
    )
    DAILY_REPORTS_ADD_ACTIVITY = (
        "daily_reports.add_activity",
        "افزودن فعالیت به گزارش روزانه",
    )
    DAILY_REPORTS_ADD_DELAY = (
        "daily_reports.add_delay",
        "افزودن رویداد تأخیر به گزارش روزانه",
    )
    DAILY_REPORTS_SUBMIT = "daily_reports.submit", "ارسال گزارش روزانه"
    DAILY_REPORTS_APPROVE = "daily_reports.approve", "تأیید گزارش روزانه"

    DEPARTMENTS_VIEW = "departments.view", "مشاهده دپارتمان‌ها"
    DEPARTMENTS_CREATE = "departments.create", "ایجاد دپارتمان"
    DEPARTMENTS_CHANGE = "departments.change", "ویرایش دپارتمان"
    DEPARTMENTS_ARCHIVE = "departments.archive", "بایگانی دپارتمان"
    POSITIONS_VIEW = "positions.view", "مشاهده سمت‌های شغلی"
    POSITIONS_CREATE = "positions.create", "ایجاد سمت شغلی"
    POSITIONS_CHANGE = "positions.change", "ویرایش سمت شغلی"
    POSITIONS_ARCHIVE = "positions.archive", "بایگانی سمت شغلی"
    WORK_TEAMS_VIEW = "work_teams.view", "مشاهده تیم‌های کاری"
    WORK_TEAMS_CREATE = "work_teams.create", "ایجاد تیم کاری"
    WORK_TEAMS_ARCHIVE = "work_teams.archive", "بایگانی تیم کاری"
    EMPLOYEES_VIEW = "employees.view", "مشاهده کارکنان"
    EMPLOYEES_CREATE = "employees.create", "ایجاد پرونده کارمند"
    EMPLOYEES_CHANGE_PROFILE_IMAGE = (
        "employees.change_profile_image",
        "تغییر عکس پرسنلی کارمند",
    )
    EMPLOYEE_POSITIONS_ASSIGN = (
        "employee_positions.assign",
        "تخصیص سمت شغلی به کارمند",
    )
    EMPLOYEE_POSITIONS_END = (
        "employee_positions.end",
        "پایان تخصیص سمت شغلی کارمند",
    )
    EMPLOYEES_CHANGE_STATUS = "employees.change_status", "تغییر وضعیت کارمند"
    EMPLOYEES_ARCHIVE = "employees.archive", "بایگانی کارمند"
    EMPLOYEES_LINK_ACCOUNT = (
        "employees.link_account",
        "اتصال یا قطع حساب کاربری کارمند",
    )
    PROJECT_ASSIGNMENTS_VIEW = (
        "project_assignments.view",
        "مشاهده تخصیص نیروی پروژه",
    )
    PROJECT_ASSIGNMENTS_CREATE = (
        "project_assignments.create",
        "تخصیص نیرو به پروژه",
    )
    PROJECT_ASSIGNMENTS_CHANGE_STATUS = (
        "project_assignments.change_status",
        "تغییر وضعیت تخصیص نیروی پروژه",
    )

    PURCHASE_REQUESTS_VIEW = "purchase_requests.view", "مشاهده درخواست‌های خرید"
    PURCHASE_REQUESTS_CREATE = "purchase_requests.create", "ایجاد درخواست خرید"
    PURCHASE_REQUEST_ITEMS_ADD = (
        "purchase_request_items.add",
        "افزودن ردیف درخواست خرید",
    )
    PURCHASE_REQUESTS_SUBMIT = "purchase_requests.submit", "ارسال درخواست خرید"
    PURCHASE_REQUESTS_APPROVE = "purchase_requests.approve", "تأیید درخواست خرید"
    PURCHASE_REQUESTS_REJECT = "purchase_requests.reject", "رد درخواست خرید"
    PURCHASE_REQUESTS_CANCEL = "purchase_requests.cancel", "لغو درخواست خرید"
    PURCHASE_ORDERS_VIEW = "purchase_orders.view", "مشاهده سفارش‌های خرید"
    PURCHASE_ORDERS_CREATE = "purchase_orders.create", "ایجاد سفارش خرید"
    PURCHASE_ORDER_ITEMS_ADD = (
        "purchase_order_items.add",
        "افزودن ردیف سفارش خرید",
    )
    PURCHASE_ORDERS_ISSUE = "purchase_orders.issue", "صدور سفارش خرید"
    PURCHASE_ORDERS_CANCEL = "purchase_orders.cancel", "لغو سفارش خرید"
    GOODS_RECEIPTS_VIEW = "goods_receipts.view", "مشاهده رسیدهای کالا"
    GOODS_RECEIPTS_CREATE = "goods_receipts.create", "ایجاد رسید کالا"
    GOODS_RECEIPT_ITEMS_ADD = "goods_receipt_items.add", "افزودن ردیف رسید کالا"
    GOODS_RECEIPTS_POST = "goods_receipts.post", "ثبت نهایی رسید کالا"
    GOODS_RECEIPTS_VOID = "goods_receipts.void", "ابطال رسید کالا"
    RFQS_VIEW = "rfqs.view", "مشاهده استعلام‌ها"
    RFQS_CREATE = "rfqs.create", "ایجاد استعلام"
    RFQS_CHANGE = "rfqs.change", "ویرایش استعلام"
    RFQS_SUBMIT = "rfqs.submit", "ارسال استعلام برای صدور"
    RFQS_ISSUE = "rfqs.issue", "صدور استعلام"
    RFQS_ADDENDUM = "rfqs.addendum", "افزودن الحاقیه استعلام"
    RFQS_CANCEL = "rfqs.cancel", "لغو استعلام"
    RFQS_CLOSE_CUSTODY = "rfqs.close_custody", "بستن ثبتی استعلام"
    RFQS_CUSTODY_SEALED_EVIDENCE = (
        "rfqs.custody_sealed_evidence",
        "نگهداری شاهد مهروموم‌شده پیشنهاد",
    )
    RFQ_INVITATIONS_MANAGE = "rfq_invitations.manage", "مدیریت دعوت‌نامه‌های استعلام"
    RFQ_QUOTES_VIEW_METADATA = "rfq_quotes.view_metadata", "مشاهده فراداده پیشنهادها"
    RFQ_QUOTES_CAPTURE = "rfq_quotes.capture", "ثبت پیشنهادهای مهروموم‌شده"
    RFQ_QUOTES_SUBMIT = "rfq_quotes.submit", "ثبت نهایی پیشنهاد مهروموم‌شده"
    RFQ_QUOTES_WITHDRAW = "rfq_quotes.withdraw", "بازپس‌گیری پیشنهاد مهروموم‌شده"
    RFQ_QUOTES_OPEN = "rfq_quotes.open", "گشایش حفاظت‌شده پیشنهاد"
    RFQ_QUOTES_APPROVE_OPEN = (
        "rfq_quotes.approve_open",
        "تأیید مستقل گشایش پیشنهاد",
    )
    RFQ_QUOTES_VIEW_CONFIDENTIAL = (
        "rfq_quotes.view_confidential",
        "مشاهده محتوای محرمانه پیشنهاد گشوده‌شده",
    )
    RFQ_QUOTES_MANAGE_CONFIDENTIAL_ACCESS = (
        "rfq_quotes.manage_confidential_access",
        "مدیریت دسترسی محرمانه پیشنهاد",
    )

    WAREHOUSES_VIEW = "warehouses.view", "مشاهده انبارها"
    WAREHOUSES_CREATE = "warehouses.create", "ایجاد انبار"
    WAREHOUSES_ARCHIVE = "warehouses.archive", "بایگانی انبار"
    STOCK_TRANSACTIONS_VIEW = "stock_transactions.view", "مشاهده تراکنش‌های انبار"
    STOCK_TRANSACTIONS_CREATE = "stock_transactions.create", "ایجاد تراکنش انبار"
    STOCK_TRANSACTIONS_POST = "stock_transactions.post", "ثبت نهایی تراکنش انبار"
    STOCK_TRANSACTIONS_REVERSE = "stock_transactions.reverse", "برگشت تراکنش انبار"
    STOCK_BALANCES_VIEW = "stock_balances.view", "مشاهده موجودی انبار"

    EQUIPMENT_VIEW = "equipment.view", "مشاهده تجهیزات"
    EQUIPMENT_CREATE = "equipment.create", "ایجاد تجهیز"
    EQUIPMENT_CHANGE_STATUS = "equipment.change_status", "تغییر وضعیت تجهیز"
    EQUIPMENT_ARCHIVE = "equipment.archive", "بایگانی تجهیز"
    EQUIPMENT_ASSIGNMENTS_VIEW = (
        "equipment_assignments.view",
        "مشاهده تخصیص‌های تجهیزات",
    )
    EQUIPMENT_ASSIGNMENTS_CREATE = (
        "equipment_assignments.create",
        "تخصیص تجهیز به پروژه",
    )
    EQUIPMENT_ASSIGNMENTS_TRANSITION = (
        "equipment_assignments.transition",
        "تغییر وضعیت تخصیص تجهیز",
    )
    MAINTENANCE_RECORDS_VIEW = (
        "maintenance_records.view",
        "مشاهده سوابق سرویس و تعمیر",
    )
    MAINTENANCE_RECORDS_CREATE = (
        "maintenance_records.create",
        "ایجاد سابقه سرویس و تعمیر",
    )
    MAINTENANCE_RECORDS_TRANSITION = (
        "maintenance_records.transition",
        "تغییر وضعیت سرویس و تعمیر",
    )

    SAFETY_INCIDENTS_VIEW = "safety_incidents.view", "مشاهده حوادث ایمنی"
    SAFETY_INCIDENTS_CREATE = "safety_incidents.create", "ثبت حادثه ایمنی"
    SAFETY_INCIDENTS_REVIEW = "safety_incidents.review", "بررسی و تخصیص حادثه ایمنی"
    SAFETY_INCIDENTS_MANAGE = "safety_incidents.manage", "مدیریت اقدام اصلاحی ایمنی"
    SAFETY_INCIDENTS_CLOSE = "safety_incidents.close", "بستن حادثه ایمنی"

    QUALITY_ISSUES_VIEW = "quality_issues.view", "مشاهده مسائل کیفیت"
    QUALITY_ISSUES_CREATE = "quality_issues.create", "ثبت مسئله کیفیت"
    QUALITY_ISSUES_REVIEW = "quality_issues.review", "بررسی و تخصیص مسئله کیفیت"
    QUALITY_ISSUES_MANAGE = "quality_issues.manage", "مدیریت اقدام اصلاحی کیفیت"
    QUALITY_ISSUES_VERIFY = "quality_issues.verify", "راستی‌آزمایی مسئله کیفیت"
    QUALITY_ISSUES_CLOSE = "quality_issues.close", "بستن مسئله کیفیت"

    FINANCIALS_VIEW = "financials.view", "مشاهده داشبورد و گزارش‌های مالی"
    AUDIT_VIEW = "audit.view", "مشاهده گزارش رویدادها"
    WORKFLOWS_VIEW = "workflows.view", "مشاهده تعریف‌های گردش‌کار"
    WORKFLOWS_CREATE = "workflows.create", "ایجاد تعریف گردش‌کار"
    WORKFLOWS_CHANGE_DRAFT = "workflows.change_draft", "ویرایش پیش‌نویس گردش‌کار"
    WORKFLOWS_PUBLISH = "workflows.publish", "انتشار نسخه گردش‌کار"
    WORKFLOWS_RETIRE = "workflows.retire", "بازنشسته‌کردن نسخه گردش‌کار"
    WORKFLOWS_REASSIGN = "workflows.reassign", "تخصیص مجدد کار گردش‌کار"
    WORKFLOWS_DELEGATE = "workflows.delegate", "واگذاری مسئولیت گردش‌کار"
    WORKFLOWS_MIGRATE_INSTANCES = (
        "workflows.migrate_instances",
        "مهاجرت اجرای باز گردش‌کار",
    )
    WORK_ITEMS_VIEW = "work_items.view", "مشاهده کارهای گردش‌کار"
    WORK_ITEMS_CLAIM = "work_items.claim", "اخذ کار گردش‌کار"
    WORK_ITEMS_ACT = "work_items.act", "انجام اقدام گردش‌کار"


class BusinessPermission(UUIDModel, TimeStampedModel):
    """A code-owned business capability that can be attached to global roles."""

    code = models.CharField("کد مجوز", max_length=100, unique=True)
    name = models.CharField("عنوان فارسی", max_length=255)
    description = models.TextField("توضیحات", blank=True)
    is_active = models.BooleanField("فعال", default=True)

    class Meta:
        verbose_name = "مجوز کسب‌وکار"
        verbose_name_plural = "مجوزهای کسب‌وکار"
        ordering = ["code"]  # noqa: RUF012

    def __str__(self) -> str:
        return self.name


class OrganizationRole(UUIDModel, TimeStampedModel):
    """A system, global-custom, or tenant-custom role using code-owned permissions."""

    organization = models.ForeignKey(
        "Organization",
        verbose_name="شرکت",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="custom_roles",
    )
    code = models.SlugField("کد نقش", max_length=64)
    name = models.CharField("عنوان نقش", max_length=255)
    description = models.TextField("توضیحات", blank=True)
    permissions = models.ManyToManyField(
        BusinessPermission,
        verbose_name="مجوزهای کسب‌وکار",
        related_name="roles",
        blank=True,
    )
    is_active = models.BooleanField("فعال", default=True, db_index=True)
    is_system = models.BooleanField("نقش سیستمی", default=False)
    is_owner = models.BooleanField("نقش مالک شرکت", default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organization_roles_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organization_roles_updated",
    )
    archived_at = models.DateTimeField("زمان بایگانی", null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="بایگانی‌کننده",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="organization_roles_archived",
    )
    archive_reason = models.TextField("دلیل بایگانی", blank=True)

    class Meta:
        verbose_name = "نقش شرکتی"
        verbose_name_plural = "نقش‌های شرکتی"
        ordering = ["name"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["is_owner"],
                condition=Q(is_owner=True),
                name="unique_company_owner_role",
            ),
            models.UniqueConstraint(
                fields=["code"],
                condition=Q(organization__isnull=True),
                name="unique_global_organization_role_code",
            ),
            models.UniqueConstraint(
                fields=["organization", "code"],
                condition=Q(organization__isnull=False),
                name="unique_tenant_organization_role_code",
            ),
            models.CheckConstraint(
                condition=Q(is_system=False) | Q(organization__isnull=True),
                name="system_organization_role_is_global",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        self.code = canonicalize_lower_identifier(self.code)
        if self.is_owner and (not self.is_system or not self.is_active):
            raise ValidationError("نقش مالک شرکت باید یک نقش سیستمی و فعال باقی بماند.")
        if self.is_owner and self.organization_id:
            raise ValidationError("نقش مالک شرکت نمی‌تواند اختصاصی یک شرکت باشد.")
        if self.is_system and self.organization_id:
            raise ValidationError("نقش سیستمی باید سراسری باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        self.code = canonicalize_lower_identifier(self.code)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Organization(UUIDModel, TimeStampedModel):
    """A construction company tenant."""

    name = models.CharField("نام شرکت", max_length=255)
    legal_name = models.CharField("نام ثبتی/قانونی", max_length=255, blank=True)
    slug = models.SlugField("شناسه URL", max_length=255, unique=True)
    registration_number = models.CharField("شماره ثبت", max_length=64, blank=True)
    national_id = models.CharField(
        "شناسه ملی",
        max_length=32,
        blank=True,
        validators=[
            RegexValidator(
                regex=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$",
                message="شناسه ملی فقط می‌تواند شامل حروف لاتین، عدد و . _ / - باشد.",
            )
        ],
    )
    economic_code = models.CharField(
        "کد اقتصادی",
        max_length=32,
        blank=True,
        validators=[
            RegexValidator(
                regex=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$",
                message="کد اقتصادی فقط می‌تواند شامل حروف لاتین، عدد و . _ / - باشد.",
            )
        ],
    )
    phone = models.CharField(
        "تلفن",
        max_length=16,
        blank=True,
        validators=[
            RegexValidator(
                regex=r"^\+?[0-9]{7,15}$",
                message="شماره تلفن باید بین ۷ تا ۱۵ رقم و در صورت نیاز با + آغاز شود.",
            )
        ],
    )
    email = models.EmailField("ایمیل", blank=True)
    website = models.URLField("وب‌سایت", blank=True)
    province = models.CharField("استان", max_length=100, blank=True)
    city = models.CharField("شهر", max_length=100, blank=True)
    address = models.TextField("نشانی", blank=True)
    postal_code = models.CharField(
        "کد پستی",
        max_length=20,
        blank=True,
        validators=[
            RegexValidator(
                regex=r"^[A-Za-z0-9][A-Za-z0-9 -]{2,19}$",
                message="کد پستی باید بین ۳ تا ۲۰ نویسه و بدون علامت نامعتبر باشد.",
            )
        ],
    )
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=OrganizationStatus.choices,
        default=OrganizationStatus.ACTIVE,
        db_index=True,
    )
    timezone = models.CharField("منطقه زمانی", max_length=64, default="UTC")
    currency = models.CharField("واحد پول", max_length=3, default="USD")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organizations_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organizations_updated",
    )
    deleted_at = models.DateTimeField("زمان حذف", null=True, blank=True)
    archived_at = models.DateTimeField("زمان بایگانی", null=True, blank=True)

    class Meta:
        verbose_name = "شرکت"
        verbose_name_plural = "شرکت‌ها"
        ordering = ["name"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                Lower("national_id"),
                condition=~Q(national_id=""),
                name="unique_nonblank_organization_national_id",
            ),
            models.UniqueConstraint(
                Lower("economic_code"),
                condition=~Q(economic_code=""),
                name="unique_nonblank_organization_economic_code",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status=OrganizationStatus.ARCHIVED, archived_at__isnull=False)
                    | (
                        ~Q(status=OrganizationStatus.ARCHIVED)
                        & Q(archived_at__isnull=True)
                    )
                ),
                name="organization_archive_state_consistent",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        self.slug = canonicalize_lower_identifier(self.slug)
        self.national_id = canonicalize_upper_identifier(self.national_id)
        self.economic_code = canonicalize_upper_identifier(self.economic_code)
        if (self.status == OrganizationStatus.ARCHIVED) != bool(self.archived_at):
            raise ValidationError(
                {"archived_at": "وضعیت بایگانی و زمان بایگانی باید با هم سازگار باشند."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        self.slug = canonicalize_lower_identifier(self.slug)
        self.national_id = canonicalize_upper_identifier(self.national_id)
        self.economic_code = canonicalize_upper_identifier(self.economic_code)
        super().save(*args, **kwargs)

    @property
    def is_active(self) -> bool:
        """Expose active state without duplicating the lifecycle status in storage."""

        return (
            self.status == OrganizationStatus.ACTIVE
            and self.deleted_at is None
            and self.archived_at is None
        )

    def __str__(self) -> str:
        return self.name


class OrganizationSettings(UUIDModel, TimeStampedModel):
    """Authoritative organization-level configuration for exactly one Tenant.

    The timezone and currency fields on :class:`Organization` remain inert legacy
    compatibility data until the separately authorized contract stage.
    """

    organization = models.OneToOneField(
        Organization,
        verbose_name="شرکت",
        on_delete=models.CASCADE,
        related_name="settings",
    )
    logo = models.FileField(
        "لوگو",
        upload_to=organization_logo_upload_path,
        validators=[validate_organization_logo],
        blank=True,
        max_length=255,
    )
    language = models.CharField(
        "زبان پیش‌فرض",
        max_length=10,
        choices=OrganizationLanguage.choices,
        default=OrganizationLanguage.PERSIAN,
    )
    timezone = models.CharField(
        "منطقه زمانی",
        max_length=64,
        default="UTC",
        validators=[validate_timezone_name],
    )
    currency = models.CharField(
        "واحد پول پیش‌فرض",
        max_length=3,
        default=SUPPORTED_BASE_CURRENCY,
        validators=[
            RegexValidator(
                regex=r"^[A-Z]{3}$",
                message="واحد پول باید یک کد سه‌حرفی با حروف بزرگ لاتین باشد.",
            ),
            validate_supported_base_currency,
        ],
    )
    fiscal_year_start_month = models.PositiveSmallIntegerField(
        "ماه شروع سال مالی",
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    fiscal_year_start_day = models.PositiveSmallIntegerField(
        "روز شروع سال مالی",
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(31)],
    )
    project_code_prefix = models.CharField(
        "پیشوند کد پروژه",
        max_length=16,
        default="PRJ",
        validators=[
            RegexValidator(
                regex=r"^[A-Z0-9][A-Z0-9-]{0,15}$",
                message="پیشوند پروژه فقط می‌تواند شامل حروف بزرگ لاتین، عدد و - باشد.",
            )
        ],
    )
    contract_code_prefix = models.CharField(
        "پیشوند کد قرارداد",
        max_length=16,
        default="CTR",
        validators=[
            RegexValidator(
                regex=r"^[A-Z0-9][A-Z0-9-]{0,15}$",
                message="پیشوند قرارداد فقط می‌تواند شامل حروف بزرگ لاتین، عدد و - باشد.",
            )
        ],
    )
    site_code_prefix = models.CharField(
        "پیشوند کد کارگاه",
        max_length=16,
        default="SITE",
        validators=[
            RegexValidator(
                regex=r"^[A-Z0-9][A-Z0-9-]{0,15}$",
                message="پیشوند کارگاه فقط می‌تواند شامل حروف بزرگ لاتین، عدد و - باشد.",
            )
        ],
    )
    document_code_prefix = models.CharField(
        "پیشوند کد اسناد",
        max_length=16,
        default="DOC",
        validators=[
            RegexValidator(
                regex=r"^[A-Z0-9][A-Z0-9-]{0,15}$",
                message="پیشوند اسناد فقط می‌تواند شامل حروف بزرگ لاتین، عدد و - باشد.",
            )
        ],
    )

    class Meta:
        verbose_name = "تنظیمات شرکت"
        verbose_name_plural = "تنظیمات شرکت‌ها"

    def clean(self) -> None:
        super().clean()
        self.currency = canonicalize_upper_identifier(self.currency)
        self.project_code_prefix = canonicalize_upper_identifier(
            self.project_code_prefix
        )
        self.contract_code_prefix = canonicalize_upper_identifier(
            self.contract_code_prefix
        )
        self.site_code_prefix = canonicalize_upper_identifier(self.site_code_prefix)
        self.document_code_prefix = canonicalize_upper_identifier(
            self.document_code_prefix
        )
        max_day = calendar.monthrange(2001, self.fiscal_year_start_month)[1]
        if self.fiscal_year_start_day > max_day:
            raise ValidationError(
                {"fiscal_year_start_day": "روز شروع برای ماه انتخاب‌شده معتبر نیست."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        self.currency = canonicalize_upper_identifier(self.currency)
        self.project_code_prefix = canonicalize_upper_identifier(
            self.project_code_prefix
        )
        self.contract_code_prefix = canonicalize_upper_identifier(
            self.contract_code_prefix
        )
        self.site_code_prefix = canonicalize_upper_identifier(self.site_code_prefix)
        self.document_code_prefix = canonicalize_upper_identifier(
            self.document_code_prefix
        )
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"تنظیمات {self.organization.name}"


class OrganizationMembership(UUIDModel, TimeStampedModel):
    """A user's membership and role within an organization."""

    organization = models.ForeignKey(
        Organization,
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="کاربر",
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )
    role = models.CharField(
        "کد نقش سازگار",
        max_length=64,
        blank=True,
        default="",
        editable=False,
    )
    role_definition = models.ForeignKey(
        OrganizationRole,
        verbose_name="نقش",
        on_delete=models.PROTECT,
        related_name="memberships",
        null=True,
        blank=True,
    )
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=MembershipStatus.choices,
        default=MembershipStatus.PENDING_ROLE,
    )
    joined_at = models.DateTimeField("زمان عضویت", null=True, blank=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="تخصیص‌دهنده اولیه",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organization_memberships_assigned",
    )
    authorization_migrated_at = models.DateTimeField(
        "زمان انتقال به مجوزدهی دامنه‌دار",
        null=True,
        blank=True,
        editable=False,
    )
    authorization_quarantined_at = models.DateTimeField(
        "زمان قرنطینه مجوزدهی",
        null=True,
        blank=True,
        editable=False,
    )

    class Meta:
        verbose_name = "عضویت سازمان"
        verbose_name_plural = "عضویت‌های سازمان"
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["user", "organization"],
                name="unique_user_organization_membership",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status=MembershipStatus.PENDING_ROLE,
                        role="",
                        role_definition__isnull=True,
                    )
                    | (
                        ~Q(status=MembershipStatus.PENDING_ROLE)
                        & ~Q(role="")
                        & Q(role_definition__isnull=False)
                    )
                ),
                name="membership_role_matches_status",
            ),
        ]
        ordering = ["organization__name", "user__username"]  # noqa: RUF012

    @property
    def role_label(self) -> str:
        if self.role_definition_id is None:
            return str(MembershipStatus.PENDING_ROLE.label)
        return self.role_definition.name

    def clean(self) -> None:
        super().clean()
        if self.status == MembershipStatus.PENDING_ROLE:
            if self.role_definition_id is not None or self.role:
                raise ValidationError("عضویت در انتظار نباید نقش داشته باشد.")
        elif self.role_definition_id is None and not self.role:
            raise ValidationError("عضویت فعال یا بسته‌شده باید نقش داشته باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.status == MembershipStatus.PENDING_ROLE:
            self.role_definition = None
            self.role = ""
        elif self.role_definition_id is None:
            self.role_definition = OrganizationRole.objects.get(code=self.role)
        if self.role_definition_id is not None:
            self.role = self.role_definition.code
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"role", "role_definition"}
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.user.username} - {self.organization.name}"


class MembershipRoleAssignment(UUIDModel, TimeStampedModel):
    """Effective-dated, independently auditable role on one tenant membership."""

    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="membership_role_assignments",
    )
    membership = models.ForeignKey(
        OrganizationMembership,
        on_delete=models.PROTECT,
        related_name="role_assignments",
    )
    role = models.ForeignKey(
        OrganizationRole,
        on_delete=models.PROTECT,
        related_name="membership_assignments",
    )
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)
    assigned_by = models.ForeignKey(
        OrganizationMembership,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="role_assignments_created",
    )
    approved_by = models.ForeignKey(
        OrganizationMembership,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="role_assignments_approved",
    )
    reason = models.TextField()
    source = models.CharField(max_length=32, default="manual")
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        OrganizationMembership,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="role_assignments_revoked",
    )
    revocation_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["membership_id", "starts_at", "pk"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["membership", "role"],
                condition=Q(revoked_at__isnull=True),
                name="membership_one_unrevoked_role",
            ),
            models.CheckConstraint(
                condition=Q(ends_at__isnull=True)
                | Q(ends_at__gt=models.F("starts_at")),
                name="membership_role_assignment_dates",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "membership", "revoked_at", "ends_at"],
                name="membership_role_effective_idx",
            )
        ]

    @property
    def is_effective(self) -> bool:
        now = timezone.now()
        return (
            self.revoked_at is None
            and self.starts_at <= now
            and (self.ends_at is None or self.ends_at > now)
        )

    def clean(self) -> None:
        super().clean()
        if (
            self.membership_id
            and self.membership.organization_id != self.organization_id
        ):
            raise ValidationError({"membership": "عضویت متعلق به این سازمان نیست."})
        for field_name in ("assigned_by", "approved_by", "revoked_by"):
            value = getattr(self, field_name, None)
            if value is not None and value.organization_id != self.organization_id:
                raise ValidationError({field_name: "عامل متعلق به این سازمان نیست."})
        if self.assigned_by_id and self.approved_by_id == self.assigned_by_id:
            raise ValidationError(
                {"approved_by": "تخصیص‌دهنده نمی‌تواند تأییدکننده باشد."}
            )
        if self.approved_by_id and self.approved_by_id == self.membership_id:
            raise ValidationError(
                {"approved_by": "گیرنده نقش نمی‌تواند نقش خود را تأیید کند."}
            )

    def __str__(self) -> str:
        return f"{self.membership} · {self.role.code}"


class MembershipScopeGrant(UUIDModel, TimeStampedModel):
    """Explicit organization, project, or site scope for one membership."""

    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="membership_scope_grants",
    )
    membership = models.ForeignKey(
        OrganizationMembership,
        on_delete=models.PROTECT,
        related_name="scope_grants",
    )
    scope_type = models.CharField(max_length=20, choices=AuthorizationScopeType.choices)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="authorization_grants",
    )
    site = models.ForeignKey(
        "projects.ProjectSite",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="authorization_grants",
    )
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)
    granted_by = models.ForeignKey(
        OrganizationMembership,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="scope_grants_created",
    )
    approved_by = models.ForeignKey(
        OrganizationMembership,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="scope_grants_approved",
    )
    reason = models.TextField()
    source = models.CharField(max_length=32, default="manual")
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        OrganizationMembership,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="scope_grants_revoked",
    )
    revocation_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["membership_id", "scope_type", "starts_at", "pk"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=(
                    Q(
                        scope_type=AuthorizationScopeType.ORGANIZATION,
                        project__isnull=True,
                        site__isnull=True,
                    )
                    | Q(
                        scope_type=AuthorizationScopeType.PROJECT,
                        project__isnull=False,
                        site__isnull=True,
                    )
                    | Q(
                        scope_type=AuthorizationScopeType.SITE,
                        project__isnull=False,
                        site__isnull=False,
                    )
                ),
                name="membership_scope_grant_shape",
            ),
            models.CheckConstraint(
                condition=Q(ends_at__isnull=True)
                | Q(ends_at__gt=models.F("starts_at")),
                name="membership_scope_grant_dates",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "membership", "scope_type", "revoked_at"],
                name="membership_scope_effective_idx",
            ),
            models.Index(
                fields=["organization", "project", "site", "revoked_at"],
                name="membership_scope_object_idx",
            ),
        ]

    @property
    def is_effective(self) -> bool:
        now = timezone.now()
        return (
            self.revoked_at is None
            and self.starts_at <= now
            and (self.ends_at is None or self.ends_at > now)
        )

    def clean(self) -> None:
        super().clean()
        if (
            self.membership_id
            and self.membership.organization_id != self.organization_id
        ):
            raise ValidationError({"membership": "عضویت متعلق به این سازمان نیست."})
        if self.project_id and self.project.organization_id != self.organization_id:
            raise ValidationError({"project": "پروژه متعلق به این سازمان نیست."})
        if self.site_id:
            if self.site.organization_id != self.organization_id:
                raise ValidationError({"site": "کارگاه متعلق به این سازمان نیست."})
            if self.project_id != self.site.project_id:
                raise ValidationError({"site": "کارگاه متعلق به پروژه انتخاب‌شده نیست."})
        for field_name in ("granted_by", "approved_by", "revoked_by"):
            value = getattr(self, field_name, None)
            if value is not None and value.organization_id != self.organization_id:
                raise ValidationError({field_name: "عامل متعلق به این سازمان نیست."})
        if self.granted_by_id and self.granted_by_id == self.membership_id:
            raise ValidationError({"granted_by": "خودافزایی دامنه دسترسی ممنوع است."})
        if self.granted_by_id and self.approved_by_id == self.granted_by_id:
            raise ValidationError(
                {"approved_by": "اعطاکننده نمی‌تواند تأییدکننده باشد."}
            )
        if self.approved_by_id and self.approved_by_id == self.membership_id:
            raise ValidationError(
                {"approved_by": "گیرنده نمی‌تواند دسترسی خود را تأیید کند."}
            )

    def __str__(self) -> str:
        return f"{self.membership} · {self.scope_type}"


class AuthorizationMigrationIssue(UUIDModel, TimeStampedModel):
    """A tenant-scoped quarantine record for ambiguous legacy authorization."""

    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="authorization_migration_issues",
    )
    membership = models.ForeignKey(
        OrganizationMembership,
        on_delete=models.PROTECT,
        related_name="authorization_migration_issues",
    )
    issue_code = models.CharField(max_length=64)
    detail = models.TextField()
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        OrganizationMembership,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="authorization_migration_issues_resolved",
    )
    resolution = models.TextField(blank=True)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["membership", "issue_code"],
                condition=Q(resolved_at__isnull=True),
                name="membership_open_auth_migration_issue",
            )
        ]


class PlatformRoleAssignment(UUIDModel, TimeStampedModel):
    """Independent platform role; it never grants ordinary tenant-data access."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="platform_role_assignments",
    )
    role = models.CharField(max_length=32, choices=PlatformRoleCode.choices)
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="platform_roles_assigned",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="platform_roles_approved",
    )
    reason = models.TextField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="platform_roles_revoked",
    )
    revocation_reason = models.TextField(blank=True)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["user", "role"],
                condition=Q(revoked_at__isnull=True),
                name="user_one_unrevoked_platform_role",
            ),
            models.CheckConstraint(
                condition=Q(ends_at__isnull=True)
                | Q(ends_at__gt=models.F("starts_at")),
                name="platform_role_dates",
            ),
        ]


class ProtectedOperation(UUIDModel, TimeStampedModel):
    """Immutable, platform-owned version of one non-overridable operation class."""

    code = models.CharField(max_length=100, choices=ProtectedOperationCode.choices)
    version = models.PositiveIntegerField()
    name = models.CharField(max_length=255)
    description = models.TextField()
    effective_at = models.DateTimeField(default=timezone.now)
    supersedes = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="superseded_by",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="protected_operations_created",
    )
    reason = models.TextField()
    retired_at = models.DateTimeField(null=True, blank=True)
    retired_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="protected_operations_retired",
    )
    retirement_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["code", "-version"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["code", "version"],
                name="protected_operation_code_version",
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("طبقه‌بندی عملیات حفاظت‌شده تغییرناپذیر است.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("طبقه‌بندی عملیات حفاظت‌شده قابل حذف نیست.")


class AuthorizationPolicyVersion(UUIDModel, TimeStampedModel):
    """Immutable versioned policy, including the site parent-context field set."""

    code = models.CharField(max_length=64)
    version = models.PositiveIntegerField()
    policy = models.JSONField(default=dict)
    effective_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="authorization_policy_versions_created",
    )
    reason = models.TextField()

    class Meta:
        ordering = ["code", "-version"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["code", "version"],
                name="authorization_policy_code_version",
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("نسخه سیاست مجوزدهی تغییرناپذیر است.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("نسخه سیاست مجوزدهی قابل حذف نیست.")


class OrganizationAccountConnectionRequest(UUIDModel, TimeStampedModel):
    """An owner request that an existing global identity join one tenant."""

    organization = models.ForeignKey(
        Organization,
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="account_connection_requests",
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="کاربر مقصد",
        on_delete=models.CASCADE,
        related_name="organization_connection_requests",
    )
    role_definition = models.ForeignKey(
        OrganizationRole,
        verbose_name="نقش پیشنهادی",
        on_delete=models.PROTECT,
        related_name="account_connection_requests",
    )
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=AccountConnectionRequestStatus.choices,
        default=AccountConnectionRequestStatus.PENDING,
        db_index=True,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="درخواست‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        related_name="organization_connection_requests_created",
    )
    responded_at = models.DateTimeField("زمان پاسخ", null=True, blank=True)

    class Meta:
        verbose_name = "درخواست اتصال حساب به شرکت"
        verbose_name_plural = "درخواست‌های اتصال حساب به شرکت"
        ordering = ["-created_at"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "target_user"],
                condition=Q(status=AccountConnectionRequestStatus.PENDING),
                name="unique_pending_account_connection_request",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status=AccountConnectionRequestStatus.PENDING,
                        responded_at__isnull=True,
                    )
                    | (
                        ~Q(status=AccountConnectionRequestStatus.PENDING)
                        & Q(responded_at__isnull=False)
                    )
                ),
                name="account_connection_response_state_consistent",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.target_user.username} - {self.organization.name}"


class PolicySource(UUIDModel, TimeStampedModel):
    """External provenance metadata; the issuer is never an application actor."""

    issuer = models.CharField("مرجع صادرکننده", max_length=255)
    title = models.CharField("عنوان منبع", max_length=500)
    source_identifier = models.CharField("شناسه منبع", max_length=255)
    source_location = models.CharField("محل دسترسی", max_length=500, blank=True)
    version = models.CharField("نسخه", max_length=100)
    publication_date = models.DateField("تاریخ انتشار", null=True, blank=True)
    effective_from = models.DateField("شروع اعتبار", null=True, blank=True)
    effective_to = models.DateField("پایان اعتبار", null=True, blank=True)
    applicability = models.TextField("دامنه کاربرد")
    reason = models.TextField("دلیل ثبت منبع", blank=True)
    supersedes = models.ForeignKey(
        "self",
        verbose_name="جایگزین منبع",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="superseded_by_sources",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ثبت‌کننده Platform",
        on_delete=models.PROTECT,
        related_name="policy_sources_created",
    )

    class Meta:
        verbose_name = "منبع سیاست"
        verbose_name_plural = "منابع سیاست"
        ordering = ["issuer", "source_identifier", "version"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["source_identifier", "version"],
                name="unique_policy_source_version",
            ),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True)
                | Q(effective_from__isnull=True)
                | Q(effective_to__gt=models.F("effective_from")),
                name="policy_source_effective_interval",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        for field_name in (
            "issuer",
            "title",
            "source_identifier",
            "version",
            "reason",
        ):
            if not str(getattr(self, field_name)).strip():
                raise ValidationError({field_name: "این مقدار الزامی است."})
        if self.supersedes_id and self.supersedes_id == self.pk:
            raise ValidationError({"supersedes": "منبع نمی‌تواند جایگزین خود باشد."})

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError(
                "رکورد منبع سیاست تغییرناپذیر است؛ نسخه جدید ثبت کنید."
            )
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("رکورد منبع سیاست قابل حذف نیست.")

    def __str__(self) -> str:
        return f"{self.issuer} · {self.source_identifier} · {self.version}"


class PlatformPolicy(UUIDModel, TimeStampedModel):
    """Platform-owned definition of a bounded policy/localization option."""

    code = models.SlugField("کد سیاست", max_length=100, unique=True)
    name = models.CharField("عنوان سیاست", max_length=255)
    category = models.CharField(
        "دسته سیاست", max_length=40, choices=PolicyCategory.choices
    )
    sensitivity = models.CharField(
        "حساسیت",
        max_length=20,
        choices=PolicySensitivity.choices,
        default=PolicySensitivity.OPERATIONAL,
    )
    tenant_selectable = models.BooleanField("قابل انتخاب توسط Tenant", default=True)
    requires_source_provenance = models.BooleanField(
        "نیازمند منبع برای انتشار و اعمال", default=False
    )
    is_active = models.BooleanField("فعال", default=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="platform_policies_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="platform_policies_updated",
    )

    class Meta:
        verbose_name = "سیاست پلتفرم"
        verbose_name_plural = "سیاست‌های پلتفرم"
        ordering = ["code"]  # noqa: RUF012

    def save(self, *args: object, **kwargs: object) -> None:
        self.code = canonicalize_lower_identifier(self.code)
        from apps.organizations.policy_specs import get_platform_policy_spec

        spec = get_platform_policy_spec(self.code)
        if (
            self.name != spec.name
            or self.category != spec.category
            or self.sensitivity != spec.sensitivity
            or self.tenant_selectable != spec.tenant_selectable
            or self.requires_source_provenance
        ):
            raise ValidationError(
                "تعریف سیاست باید دقیقاً با کاتالوگ کد-محور هم‌خوان باشد."
            )
        if not self._state.adding and self.versions.exists():
            original = PlatformPolicy.objects.get(pk=self.pk)
            stable_fields = (
                "code",
                "category",
                "sensitivity",
                "tenant_selectable",
                "requires_source_provenance",
            )
            if any(
                getattr(original, field) != getattr(self, field)
                for field in stable_fields
            ):
                raise ValidationError(
                    "مرز سیاست دارای نسخه تغییرناپذیر است؛ سیاست جدید ایجاد کنید."
                )
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.code


def validate_policy_parameters(value: object) -> None:
    """Keep policy data declarative and reject imprecise floating-point values."""

    def walk(item: object) -> None:
        if isinstance(item, float):
            raise ValidationError("مقادیر اعشاری سیاست باید به‌صورت رشته ثبت شوند.")
        if isinstance(item, dict):
            for key, nested in item.items():
                if not isinstance(key, str):
                    raise ValidationError("کلیدهای پارامتر سیاست باید رشته باشند.")
                if key.casefold() in {"python", "sql", "script", "executable"}:
                    raise ValidationError("کد اجرایی در پارامتر سیاست مجاز نیست.")
                walk(nested)
        elif isinstance(item, list):
            for nested in item:
                walk(nested)
        elif item is not None and not isinstance(item, (str, int, bool)):
            raise ValidationError("نوع مقدار پارامتر سیاست پشتیبانی نمی‌شود.")

    if not isinstance(value, dict):
        raise ValidationError("پارامترهای سیاست باید یک شیء JSON باشند.")
    walk(value)


class PlatformPolicyVersion(UUIDModel, TimeStampedModel):
    """Immutable-after-publication platform policy version with provenance."""

    policy = models.ForeignKey(
        PlatformPolicy, on_delete=models.PROTECT, related_name="versions"
    )
    version = models.PositiveIntegerField("شماره نسخه")
    parameters = models.JSONField(
        "پارامترهای کنترل‌شده",
        default=dict,
        blank=True,
        validators=[validate_policy_parameters],
    )
    effective_from = models.DateField("شروع اعتبار")
    effective_to = models.DateField("پایان اعتبار", null=True, blank=True)
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=PolicyVersionStatus.choices,
        default=PolicyVersionStatus.DRAFT,
        db_index=True,
    )
    source_basis = models.CharField(
        "مبنای مقدار سیاست",
        max_length=30,
        choices=PolicySourceBasis.choices,
        null=True,
        blank=True,
    )
    sources = models.ManyToManyField(
        PolicySource,
        verbose_name="منابع",
        related_name="policy_versions",
        through="PlatformPolicyVersionSource",
        blank=True,
    )
    supersedes = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="superseded_by_versions",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="policy_versions_created",
    )
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="policy_versions_published",
    )
    published_at = models.DateTimeField(null=True, blank=True)
    retired_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="policy_versions_retired",
    )
    retired_at = models.DateTimeField(null=True, blank=True)
    retirement_reason = models.TextField("دلیل بازنشستگی", blank=True)
    reason = models.TextField("دلیل نسخه")

    class Meta:
        verbose_name = "نسخه سیاست پلتفرم"
        verbose_name_plural = "نسخه‌های سیاست پلتفرم"
        ordering = ["policy__code", "-version"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["policy", "version"], name="unique_platform_policy_version"
            ),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True)
                | Q(effective_to__gt=models.F("effective_from")),
                name="platform_policy_effective_interval",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status=PolicyVersionStatus.DRAFT,
                        published_at__isnull=True,
                        published_by__isnull=True,
                    )
                    | Q(
                        status__in=[
                            PolicyVersionStatus.PUBLISHED,
                            PolicyVersionStatus.RETIRED,
                        ],
                        published_at__isnull=False,
                        published_by__isnull=False,
                    )
                ),
                name="platform_policy_publication_state",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        validate_policy_parameters(self.parameters)
        if self.supersedes_id:
            if self.supersedes_id == self.pk:
                raise ValidationError({"supersedes": "نسخه نمی‌تواند جایگزین خود باشد."})
            if self.supersedes.policy_id != self.policy_id:
                raise ValidationError(
                    {"supersedes": "نسخه جایگزین متعلق به سیاست دیگری است."}
                )
        if not self.reason.strip():
            raise ValidationError({"reason": "دلیل ایجاد نسخه الزامی است."})
        if self.status == PolicyVersionStatus.RETIRED:
            if (
                not self.retired_by_id
                or not self.retired_at
                or not self.retirement_reason.strip()
            ):
                raise ValidationError("بازنشستگی نسخه به عامل، زمان و دلیل نیاز دارد.")
        elif self.retired_by_id or self.retired_at or self.retirement_reason:
            raise ValidationError("جزئیات بازنشستگی فقط برای نسخه بازنشسته مجاز است.")
        if not self._state.adding:
            original = PlatformPolicyVersion.objects.get(pk=self.pk)
            if (
                original.status == PolicyVersionStatus.RETIRED
                and self.status != original.status
            ):
                raise ValidationError("نسخه بازنشسته قابل فعال‌سازی مجدد نیست.")
            if original.status == PolicyVersionStatus.PUBLISHED and self.status not in {
                PolicyVersionStatus.PUBLISHED,
                PolicyVersionStatus.RETIRED,
            }:
                raise ValidationError("نسخه منتشرشده فقط می‌تواند بازنشسته شود.")

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            original = PlatformPolicyVersion.objects.get(pk=self.pk)
            if original.status != PolicyVersionStatus.DRAFT:
                immutable_fields = (
                    "policy_id",
                    "version",
                    "parameters",
                    "effective_from",
                    "effective_to",
                    "supersedes_id",
                    "source_basis",
                    "reason",
                    "published_by_id",
                    "published_at",
                )
                if any(
                    getattr(original, field) != getattr(self, field)
                    for field in immutable_fields
                ):
                    raise ValidationError("نسخه منتشرشده سیاست تغییرناپذیر است.")
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.policy.code} v{self.version}"


class PlatformPolicyVersionSource(UUIDModel, TimeStampedModel):
    """Append-only source linkage; published policy provenance never changes in place."""

    policy_version = models.ForeignKey(
        PlatformPolicyVersion,
        on_delete=models.PROTECT,
        related_name="source_links",
    )
    source = models.ForeignKey(
        PolicySource,
        on_delete=models.PROTECT,
        related_name="policy_version_links",
    )
    linked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="policy_version_sources_linked",
    )
    reason = models.TextField("دلیل پیوند منبع")

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["policy_version", "source"],
                name="unique_platform_policy_version_source",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if (
            self.policy_version_id
            and self.policy_version.status != PolicyVersionStatus.DRAFT
        ):
            raise ValidationError("منبع فقط به نسخه پیش‌نویس قابل پیوند است.")
        if not self.reason.strip():
            raise ValidationError({"reason": "دلیل پیوند منبع الزامی است."})

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("پیوند منبع سیاست تغییرناپذیر است.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("پیوند منبع سیاست قابل حذف نیست.")


class PolicyReviewEvidence(UUIDModel, TimeStampedModel):
    """Optional external professional evidence; never a role or approval actor."""

    policy_version = models.ForeignKey(
        PlatformPolicyVersion,
        on_delete=models.PROTECT,
        related_name="review_evidence",
    )
    reviewer_identity = models.CharField("هویت بازبین", max_length=255)
    qualification_summary = models.TextField("خلاصه صلاحیت")
    independence_statement = models.TextField("اظهار استقلال")
    evidence_reference = models.CharField("مرجع مدرک", max_length=500)
    reviewed_on = models.DateField("تاریخ بررسی")
    review_scope = models.TextField("دامنه بررسی")
    disposition = models.CharField(
        "نتیجه", max_length=40, choices=PolicyReviewDisposition.choices
    )
    conditions = models.TextField("شرایط و محدودیت‌ها", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="policy_review_evidence_created",
    )

    class Meta:
        verbose_name = "مدرک اختیاری بررسی سیاست"
        verbose_name_plural = "مدارک اختیاری بررسی سیاست"
        ordering = ["-reviewed_on", "policy_version"]  # noqa: RUF012

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("مدرک بررسی سیاست تغییرناپذیر است.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("مدرک بررسی سیاست قابل حذف نیست.")


class TenantPolicySelection(UUIDModel, TimeStampedModel):
    """Tenant selection of one published platform option, without overrides."""

    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="policy_selections"
    )
    policy = models.ForeignKey(
        PlatformPolicy, on_delete=models.PROTECT, related_name="tenant_selections"
    )
    policy_version = models.ForeignKey(
        PlatformPolicyVersion,
        on_delete=models.PROTECT,
        related_name="tenant_selections",
    )
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=TenantPolicySelectionStatus.choices,
        default=TenantPolicySelectionStatus.APPROVED,
        db_index=True,
    )
    approved_by = models.ForeignKey(
        OrganizationMembership,
        on_delete=models.PROTECT,
        related_name="policy_selections_approved",
    )
    approved_at = models.DateTimeField()
    applied_by = models.ForeignKey(
        OrganizationMembership,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="policy_selections_applied",
    )
    applied_at = models.DateTimeField(null=True, blank=True)
    supersedes = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="superseded_by_selections",
    )
    reason = models.TextField("دلیل انتخاب")

    class Meta:
        verbose_name = "انتخاب سیاست Tenant"
        verbose_name_plural = "انتخاب‌های سیاست Tenant"
        ordering = ["organization", "policy", "-created_at"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "policy"],
                condition=Q(status=TenantPolicySelectionStatus.ACTIVE),
                name="unique_active_tenant_policy_selection",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status=TenantPolicySelectionStatus.APPROVED,
                        applied_by__isnull=True,
                        applied_at__isnull=True,
                    )
                    | Q(
                        status__in=[
                            TenantPolicySelectionStatus.ACTIVE,
                            TenantPolicySelectionStatus.SUPERSEDED,
                        ],
                        applied_by__isnull=False,
                        applied_at__isnull=False,
                    )
                ),
                name="tenant_policy_application_state",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.policy_version_id and self.policy_id != self.policy_version.policy_id:
            raise ValidationError({"policy_version": "نسخه متعلق به این سیاست نیست."})
        if self.policy_id and not self.policy.tenant_selectable:
            raise ValidationError({"policy": "این سیاست توسط Tenant قابل انتخاب نیست."})
        for field_name in ("approved_by", "applied_by"):
            membership = getattr(self, field_name, None)
            if (
                membership is not None
                and membership.organization_id != self.organization_id
            ):
                raise ValidationError({field_name: "عضویت متعلق به این Tenant نیست."})
        if (
            self.supersedes_id
            and self.supersedes.organization_id != self.organization_id
        ):
            raise ValidationError(
                {"supersedes": "انتخاب قبلی متعلق به Tenant دیگری است."}
            )
        if not self.reason.strip():
            raise ValidationError({"reason": "دلیل انتخاب سیاست الزامی است."})

    def __str__(self) -> str:
        return f"{self.organization} · {self.policy.code} · {self.status}"

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)
