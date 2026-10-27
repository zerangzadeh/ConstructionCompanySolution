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
    ACCOUNTING_YEAR_END_VIEW = "accounting.year_end_view", "مشاهده بستن سال مالی"
    ACCOUNTING_YEAR_END_CONFIGURE = "accounting.year_end_configure", "تنظیم حساب‌های بستن سال"
    ACCOUNTING_YEAR_END_PREPARE = "accounting.year_end_prepare", "تهیه بستن سال مالی"
    ACCOUNTING_YEAR_END_APPROVE = "accounting.year_end_approve", "تأیید بستن سال و افتتاحیه"
    ACCOUNTING_YEAR_END_REOPEN = "accounting.year_end_reopen", "بازگشایی سال مالی"

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
    ACCOUNTING_CONTROL_ACCOUNT_MAPPINGS_MANAGE = (
        "accounting.control_account_mappings_manage",
        "مدیریت نگاشت حساب کنترل AP/AR",
    )

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

    SUBLEDGERS_SOURCES_REVERSE = (
        "subledgers.sources_reverse", "برگشت کنترل‌شده منبع تعهد AP"
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
    CONTRACT_TERMS_MANAGE = "contract_terms.manage", "تهیه نسخه شرایط تجاری قرارداد"
    INDEXATION_RULES_MANAGE = "indexation_rules.manage", "تهیه نسخه قانون تعدیل"
    INDEXATION_CALCULATE = "indexation.calculate", "محاسبه تعدیل با سیاست مجاز"
    INDEXATION_CORRECT = "indexation.correct", "اصلاح و برگشت تعدیل با سیاست مجاز"
    LEAVE_POLICIES_MANAGE = "leave_policies.manage", "ثبت نسخه سیاست مرخصی"
    LEAVE_BALANCES_MANAGE = "leave_balances.manage", "ثبت منبع مانده مرخصی"
    LEAVE_BALANCES_VIEW = "leave_balances.view", "مشاهده مانده مجاز مرخصی"
    EMPLOYMENT_RECORDS_MANAGE = "employment_records.manage", "ثبت نسخه سابقه استخدام"
    EMPLOYMENT_RECORDS_VIEW_OWN = "employment_records.view_own", "مشاهده سوابق استخدام شخصی"
    OFFBOARDING_START = "offboarding.start", "آغاز بررسی تسویه همکاری"
    OFFBOARDING_VIEW = "offboarding.view", "مشاهده پرونده مجاز پایان همکاری"
    OFFBOARDING_REVIEW = "offboarding.review", "ثبت بررسی تخصیص‌یافته پایان همکاری"
    ROSTERS_MANAGE = "rosters.manage", "ثبت نسخه برنامه شیفت"
    ROSTERS_VIEW = "rosters.view", "مشاهده برنامه شیفت مجاز"
    CONTRACT_TERMS_APPROVE = (
        "contract_terms.approve",
        "تأیید مستقل نسخه شرایط تجاری قرارداد",
    )
    CONTRACTUAL_RECORDS_VIEW = (
        "contractual_records.view",
        "مشاهده دستورها، تغییرات، ادعاها و تمدید مدت قراردادی",
    )
    CONTRACTUAL_RECORDS_PREPARE = (
        "contractual_records.prepare",
        "تهیه و اصلاح رکورد قراردادی",
    )
    CONTRACTUAL_RECORDS_SUBMIT = (
        "contractual_records.submit",
        "ارسال رکورد قراردادی برای تأیید",
    )
    CONTRACTUAL_RECORDS_APPROVE = (
        "contractual_records.approve",
        "تأیید یا بازگرداندن رکورد قراردادی",
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
    PAYABLE_MEASUREMENTS_VIEW = (
        "payable_measurements.view",
        "مشاهده اندازه‌گیری پیمان جزء",
    )
    PAYABLE_MEASUREMENTS_RECORD = (
        "payable_measurements.record",
        "ثبت و ارسال اندازه‌گیری پیمان جزء",
    )
    PAYABLE_MEASUREMENTS_VERIFY = (
        "payable_measurements.verify",
        "راستی‌آزمایی اندازه‌گیری پیمان جزء",
    )
    PAYABLE_CERTIFICATES_VIEW = (
        "payable_certificates.view",
        "مشاهده گواهی‌های پرداخت پیمان جزء",
    )
    PAYABLE_CERTIFICATES_CREATE = (
        "payable_certificates.create",
        "تهیه گواهی پرداخت پیمان جزء",
    )
    PAYABLE_CERTIFICATES_REVISE = (
        "payable_certificates.revise",
        "بازنگری و اصلاح گواهی پرداخت",
    )
    PAYABLE_CERTIFICATES_SUBMIT = (
        "payable_certificates.submit",
        "ارسال گواهی پرداخت",
    )
    PAYABLE_CERTIFICATES_APPROVE = (
        "payable_certificates.approve",
        "تأیید یا بازگرداندن گواهی پرداخت",
    )
    GUARANTEES_VIEW = "guarantees.view", "مشاهده ضمانت‌نامه‌ها و مواجهه"
    GUARANTEES_MANAGE = "guarantees.manage", "ثبت و اصلاح ضمانت‌نامه"
    GUARANTEES_SUBMIT = "guarantees.submit", "ارسال ضمانت‌نامه"
    GUARANTEES_APPROVE = "guarantees.approve", "تأیید ضمانت‌نامه یا آزادسازی"
    COMPLIANCE_EVIDENCE_VIEW = (
        "compliance_evidence.view",
        "مشاهده شواهد بیمه و مفاصاحساب",
    )
    COMPLIANCE_EVIDENCE_MANAGE = (
        "compliance_evidence.manage",
        "ثبت و اصلاح شواهد بیمه و مفاصاحساب",
    )
    COMPLIANCE_EVIDENCE_SUBMIT = (
        "compliance_evidence.submit",
        "ارسال شواهد بیمه و مفاصاحساب",
    )
    COMPLIANCE_EVIDENCE_APPROVE = (
        "compliance_evidence.approve",
        "تأیید شواهد بیمه و مفاصاحساب",
    )
    RETENTION_RELEASES_VIEW = (
        "retention_releases.view",
        "مشاهده آزادسازی کسور تضمین",
    )
    RETENTION_RELEASES_CREATE = (
        "retention_releases.create",
        "تهیه آزادسازی کسور تضمین",
    )
    RETENTION_RELEASES_SUBMIT = (
        "retention_releases.submit",
        "ارسال آزادسازی کسور تضمین",
    )
    RETENTION_RELEASES_APPROVE = (
        "retention_releases.approve",
        "تأیید یا بازگرداندن آزادسازی کسور تضمین",
    )
    TAXPAYER_INVOICES_VIEW = (
        "taxpayer_invoices.view",
        "مشاهده صورتحساب‌های مؤدیان",
    )
    TAXPAYER_INVOICES_PREPARE = (
        "taxpayer_invoices.prepare",
        "تهیه و اصلاح صورتحساب مؤدیان",
    )
    TAXPAYER_INVOICES_SUBMIT = (
        "taxpayer_invoices.submit",
        "ارسال صورتحساب مؤدیان برای تأیید",
    )
    TAXPAYER_INVOICES_APPROVE = (
        "taxpayer_invoices.approve",
        "تأیید یا بازگرداندن صورتحساب مؤدیان",
    )
    CONTRACTOR_COMPLIANCE_VIEW = (
        "contractor_compliance.view",
        "مشاهده ارزیابی انطباق بیمه پیمانکار",
    )
    CONTRACTOR_COMPLIANCE_PREPARE = (
        "contractor_compliance.prepare",
        "تهیه ارزیابی انطباق بیمه پیمانکار",
    )
    CONTRACTOR_COMPLIANCE_SUBMIT = (
        "contractor_compliance.submit",
        "ارسال ارزیابی انطباق بیمه پیمانکار",
    )
    CONTRACTOR_COMPLIANCE_APPROVE = (
        "contractor_compliance.approve",
        "تأیید ارزیابی انطباق بیمه پیمانکار",
    )
    STATUTORY_SUBMISSIONS_EXECUTE = (
        "statutory_submissions.execute",
        "ثبت خروجی یا اجرای adapter آزمون مقرراتی",
    )
    STATUTORY_SUBMISSIONS_RESOLVE = (
        "statutory_submissions.resolve",
        "ثبت حل انسانی خطای ارسال مقرراتی",
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
    SUBLEDGERS_PAYROLL_ENROLLMENTS_MANAGE = "subledgers_payroll.enrollments_manage", "تهیه ثبت بدهی حقوق در AP"
    SUBLEDGERS_PAYROLL_ENROLLMENTS_APPROVE = "subledgers_payroll.enrollments_approve", "فعال‌سازی و توقف ثبت بدهی حقوق در AP"
    SUBLEDGERS_PAYROLL_PREPARE = "subledgers_payroll.prepare", "تهیه پیش‌نویس و اصلاح بدهی حقوق در AP"
    SUBLEDGERS_PAYROLL_VIEW = "subledgers_payroll.view", "مشاهده و تطبیق بدهی حقوق در AP"
    ACCOUNTING_RECOGNITION_MAPPINGS_MANAGE = "accounting_recognition.mappings_manage", "تهیه نگاشت شناسایی حسابداری"
    ACCOUNTING_RECOGNITION_MAPPINGS_APPROVE = "accounting_recognition.mappings_approve", "پذیرش مستقل نگاشت شناسایی"
    ACCOUNTING_RECOGNITION_PREPARE = "accounting_recognition.prepare", "تهیه و تلاش مجدد پیش‌نویس شناسایی"
    ACCOUNTING_RECOGNITION_VIEW = "accounting_recognition.view", "مشاهده و تطبیق شناسایی حسابداری"
    BILLING_VARIATION_ELIGIBILITY_VIEW = "billing_variation_eligibility.view", "مشاهده اهلیت منبع تغییر"
    BILLING_VARIATION_ELIGIBILITY_RETRY = "billing_variation_eligibility.retry", "تلاش مجدد پذیرش منبع تغییر"
    PRICE_BOOKS_MANAGE = "price_books.manage", "مدیریت منابع فهرست‌بها"
    PRICE_BOOKS_ACTIVATE = "price_books.activate", "تأیید مستند منبع فهرست‌بها"
    PRICE_BOOK_MAPPINGS_MANAGE = "price_book_mappings.manage", "نگاشت نسخه‌دار فهرست‌بها"
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
    PROJECT_FORECASTS_REVIEW = (
        "project_cost.forecasts_review",
        "بررسی مستقل پیش‌بینی هزینه پروژه",
    )
    PROJECT_BUDGET_OVERRIDES_APPROVE = (
        "project_cost.budget_overrides_approve",
        "تأیید عبور ثبت‌شده از کنترل بودجه",
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

    FIELD_OBSERVATIONS_VIEW = "field_observations.view", "مشاهده مشاهدات میدانی"
    FIELD_OBSERVATIONS_CAPTURE = (
        "field_observations.capture",
        "ثبت و ویرایش مشاهده میدانی",
    )
    FIELD_OBSERVATIONS_SUBMIT = "field_observations.submit", "ارسال مشاهده میدانی"
    FIELD_OBSERVATIONS_REVIEW = "field_observations.review", "بررسی مشاهده میدانی"
    FIELD_OBSERVATIONS_LOCATION_VIEW = (
        "field_observations.location_view",
        "مشاهده مکان دقیق مشاهده",
    )
    FIELD_PROPOSALS_PREPARE = "field_proposals.prepare", "تهیه پیشنهاد تحویل مشاهده"
    FIELD_PROPOSALS_REVIEW = "field_proposals.review", "بررسی پیشنهاد تحویل مشاهده"

    COMPLIANCE_VIEW = "compliance.view", "مشاهده بازرسی و کنترل HSE/QA"
    COMPLIANCE_TEMPLATES_MANAGE = (
        "compliance.templates_manage",
        "مدیریت پیش‌نویس الگوی بازرسی",
    )
    COMPLIANCE_TEMPLATES_PUBLISH = (
        "compliance.templates_publish",
        "بررسی و انتشار الگوی بازرسی",
    )
    COMPLIANCE_INSPECTIONS_CREATE = (
        "compliance.inspections_create",
        "ایجاد و برنامه‌ریزی بازرسی",
    )
    COMPLIANCE_INSPECTIONS_EXECUTE = "compliance.inspections_execute", "اجرای بازرسی"
    COMPLIANCE_INSPECTIONS_SUBMIT = "compliance.inspections_submit", "ارسال بازرسی"
    COMPLIANCE_INSPECTIONS_REVIEW = (
        "compliance.inspections_review",
        "بررسی و نتیجه‌دهی بازرسی",
    )
    COMPLIANCE_FINDINGS_CREATE = (
        "compliance.findings_create",
        "ثبت یافته بازرسی یا آزمون",
    )
    COMPLIANCE_FINDINGS_CLASSIFY = "compliance.findings_classify", "طبقه‌بندی یافته"
    COMPLIANCE_FINDINGS_MANAGE = "compliance.findings_manage", "تخصیص و مدیریت یافته"
    COMPLIANCE_PERMITS_PREPARE = "compliance.permits_prepare", "تهیه و ارسال مجوز HSE"
    COMPLIANCE_PERMITS_ISSUE = "compliance.permits_issue", "بررسی و صدور مجوز HSE"
    COMPLIANCE_PERMITS_CONTROL = (
        "compliance.permits_control",
        "تعلیق، اعاده و ابطال مجوز HSE",
    )
    COMPLIANCE_TESTS_REQUEST = "compliance.tests_request", "درخواست آزمون QA/QC"
    COMPLIANCE_TESTS_EXECUTE = "compliance.tests_execute", "اجرا و ثبت نتیجه آزمون"
    COMPLIANCE_TESTS_REVIEW = (
        "compliance.tests_review",
        "بررسی، پذیرش یا بی‌اعتبارسازی نتیجه آزمون",
    )
    COMPLIANCE_NCR_MANAGE = "compliance.ncr_manage", "صدور و مدیریت عدم انطباق رسمی"
    COMPLIANCE_CAPA_ASSIGN = "compliance.capa_assign", "تأیید و تخصیص CAPA"
    COMPLIANCE_CAPA_EXECUTE = "compliance.capa_execute", "اجرای CAPA"
    COMPLIANCE_VERIFY = "compliance.verify", "راستی‌آزمایی مستقل اقدام"
    COMPLIANCE_EFFECTIVENESS_REVIEW = (
        "compliance.effectiveness_review",
        "ارزیابی اثربخشی CAPA",
    )
    COMPLIANCE_CLOSE = "compliance.close", "بستن یافته، NCR یا CAPA"
    COMPLIANCE_REOPEN = "compliance.reopen", "بازگشایی کنترل‌شده یافته، NCR یا CAPA"
    COMPLIANCE_EVIDENCE_LINK = "compliance.evidence_link", "پیوند نسخه شواهد HSE/QA"
    COMPLIANCE_SENSITIVE_EVIDENCE_VIEW = (
        "compliance.sensitive_evidence_view",
        "مشاهده شواهد حساس HSE/QA",
    )
    COMPLIANCE_EXPORT = "compliance.export", "خروجی کنترل‌شده HSE/QA"
    COMPLIANCE_AUDIT_RECONCILE = "compliance.audit_reconcile", "ممیزی و تطبیق HSE/QA"
    PARTNER_VIEW = "partner.view", "مشاهده صلاحیت و عملکرد همکار"
    PARTNER_PROFILE_MANAGE = "partner.profile_manage", "مدیریت پروفایل همکار"
    PARTNER_REQUIREMENTS_MANAGE = "partner.requirements_manage", "انتشار الزام صلاحیت"
    PARTNER_QUALIFICATIONS_PREPARE = (
        "partner.qualifications_prepare",
        "تهیه صلاحیت همکار",
    )
    PARTNER_QUALIFICATIONS_SUBMIT = (
        "partner.qualifications_submit",
        "ارسال صلاحیت همکار",
    )
    PARTNER_QUALIFICATIONS_REVIEW = (
        "partner.qualifications_review",
        "بررسی صلاحیت همکار",
    )
    PARTNER_QUALIFICATIONS_CONTROL = (
        "partner.qualifications_control",
        "کنترل صلاحیت همکار",
    )
    PARTNER_CATEGORY_DECIDE = "partner.category_decide", "تصمیم صلاحیت دسته همکار"
    PARTNER_EVIDENCE_LINK = "partner.evidence_link", "پیوند شواهد صلاحیت همکار"
    PARTNER_SENSITIVE_EVIDENCE_VIEW = (
        "partner.sensitive_evidence_view",
        "مشاهده شواهد حساس همکار",
    )
    PARTNER_EVALUATIONS_PREPARE = (
        "partner.evaluations_prepare",
        "تهیه ارزیابی عملکرد همکار",
    )
    PARTNER_EVALUATIONS_SUBMIT = (
        "partner.evaluations_submit",
        "ارسال ارزیابی عملکرد همکار",
    )
    PARTNER_EVALUATIONS_PUBLISH = (
        "partner.evaluations_publish",
        "انتشار ارزیابی عملکرد همکار",
    )
    PARTNER_EVALUATIONS_APPEAL = (
        "partner.evaluations_appeal",
        "اعتراض و تصمیم ارزیابی همکار",
    )
    PARTNER_PROPOSALS_CREATE = "partner.proposals_create", "ایجاد پیشنهاد صلاحیت همکار"
    PARTNER_EXPORT = "partner.export", "خروجی کنترل‌شده همکار"
    PARTNER_AUDIT_RECONCILE = "partner.audit_reconcile", "ممیزی و تطبیق همکار"
    SUPPORT_NOTIFICATIONS_VIEW = "support.notifications_view", "مشاهده اعلان‌ها"
    SUPPORT_NOTIFICATIONS_ACKNOWLEDGE = (
        "support.notifications_acknowledge",
        "تأیید اعلان‌ها",
    )
    SUPPORT_CALENDAR_VIEW = "support.calendar_view", "مشاهده تقویم نظارتی"
    SUPPORT_CASE_CREATE = "support.case_create", "ایجاد مورد پشتیبانی"
    SUPPORT_CASE_VIEW = "support.case_view", "مشاهده مورد پشتیبانی"
    SUPPORT_CASE_UPDATE = "support.case_update", "به‌روزرسانی مورد پشتیبانی"
    SUPPORT_CASE_ASSIGN = "support.case_assign", "تخصیص مورد پشتیبانی"
    SUPPORT_CASE_RESOLVE = "support.case_resolve", "حل و بستن مورد پشتیبانی"
    SUPPORT_CASE_REOPEN = "support.case_reopen", "بازگشایی مورد پشتیبانی"
    SUPPORT_EVIDENCE_LINK = "support.evidence_link", "پیوند شواهد پشتیبانی"
    SUPPORT_EVIDENCE_SENSITIVE_VIEW = (
        "support.evidence_sensitive_view",
        "مشاهده شواهد حساس پشتیبانی",
    )
    SUPPORT_ACCESS_REQUEST = "support.access_request", "درخواست دسترسی پشتیبانی"
    SUPPORT_ACCESS_TENANT_CONFIRM = (
        "support.access_tenant_confirm",
        "تأیید Tenant دسترسی پشتیبانی",
    )
    SUPPORT_ACCESS_PLATFORM_APPROVE = (
        "support.access_platform_approve",
        "تأیید پلتفرم دسترسی پشتیبانی",
    )
    SUPPORT_ACCESS_USE = "support.access_use", "استفاده از دسترسی پشتیبانی"
    SUPPORT_ACCESS_REVOKE = "support.access_revoke", "ابطال دسترسی پشتیبانی"
    SUPPORT_AUDIT_RECONCILE = "support.audit_reconcile", "ممیزی و تطبیق پشتیبانی"
    KNOWLEDGE_CANDIDATES_CREATE = "knowledge.candidates_create", "ایجاد پیش‌نویس دانش"
    KNOWLEDGE_CANDIDATES_SUBMIT = "knowledge.candidates_submit", "ارسال کاندید دانش"
    KNOWLEDGE_CANDIDATES_REVIEW = "knowledge.candidates_review", "بررسی کاندید دانش"
    KNOWLEDGE_PUBLICATIONS_APPROVE = (
        "knowledge.publications_approve",
        "تأیید انتشار دانش",
    )
    KNOWLEDGE_PUBLICATIONS_PUBLISH = "knowledge.publications_publish", "انتشار دانش"
    KNOWLEDGE_PUBLICATIONS_VIEW = "knowledge.publications_view", "مشاهده دانش منتشرشده"
    KNOWLEDGE_UNPUBLISHED_VIEW = "knowledge.unpublished_view", "مشاهده کاندیدهای دانش"
    KNOWLEDGE_PUBLICATIONS_SUPERSEDE = (
        "knowledge.publications_supersede",
        "جایگزینی انتشار دانش",
    )
    KNOWLEDGE_PUBLICATIONS_WITHDRAW = (
        "knowledge.publications_withdraw",
        "پس‌گرفتن انتشار دانش",
    )
    KNOWLEDGE_HISTORY_VIEW = "knowledge.history_view", "مشاهده تاریخچه دانش"
    KNOWLEDGE_SENSITIVE_PROVENANCE_VIEW = (
        "knowledge.sensitive_provenance_view",
        "مشاهده منبع حساس دانش",
    )
    KNOWLEDGE_RECURRENCE_RECORD = "knowledge.recurrence_record", "ثبت شواهد تکرار"
    KNOWLEDGE_REUSE_RECORD = "knowledge.reuse_record", "ثبت استفاده مجدد دانش"
    KNOWLEDGE_TAXONOMY_MANAGE = "knowledge.taxonomy_manage", "مدیریت طبقه‌بندی دانش"
    KNOWLEDGE_EXPORT = "knowledge.export", "خروجی کنترل‌شده دانش"
    KNOWLEDGE_AUDIT_RECONCILE = "knowledge.audit_reconcile", "ممیزی و تطبیق دانش"

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
    ESS_EVIDENCE_VIEW = "ess_evidence.view_own", "مشاهده سوابق و شواهد شخصی"
    HR_CERTIFICATES_VIEW = "hr_certificates.view", "مشاهده درخواست گواهی مجاز"
    HR_CERTIFICATES_REQUEST = "hr_certificates.request", "درخواست گواهی شخصی"
    HR_CERTIFICATES_REVIEW = "hr_certificates.review", "بررسی گواهی تخصیص‌یافته"
    HR_CERTIFICATES_GENERATE = "hr_certificates.generate", "تولید گواهی با سیاست مجاز"
    HR_CERTIFICATES_CONFIGURE = "hr_certificates.configure", "پیکربندی چارچوب گواهی"
    HR_CERTIFICATES_CANCEL = "hr_certificates.cancel", "لغو گواهی طبق سیاست منبع"
    PERSONAL_DATA_VIEW = "personal_data.view", "مشاهده درخواست تغییر اطلاعات مجاز"
    PERSONAL_DATA_REQUEST = "personal_data.request", "درخواست تغییر اطلاعات شخصی"
    PERSONAL_DATA_REVIEW = "personal_data.review", "تصمیم تغییر اطلاعات تخصیص‌یافته"
    PERSONAL_DATA_CONFIGURE = "personal_data.configure", "پیکربندی ثبت تغییر اطلاعات"
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
    WORKFORCE_SKILLS_VIEW = "workforce_skills.view", "مشاهده مهارت‌ها و شایستگی‌ها"
    WORKFORCE_SKILLS_MANAGE = "workforce_skills.manage", "مدیریت مهارت‌ها و شایستگی‌ها"
    WORKFORCE_QUALIFICATIONS_VIEW = (
        "workforce_qualifications.view",
        "مشاهده صلاحیت‌ها و آموزش کارکنان",
    )
    WORKFORCE_QUALIFICATIONS_MANAGE = (
        "workforce_qualifications.manage",
        "مدیریت صلاحیت‌ها و آموزش کارکنان",
    )
    WORKFORCE_QUALIFICATIONS_REVOKE = (
        "workforce_qualifications.revoke",
        "ابطال یا جایگزینی صلاحیت کارکنان",
    )
    WORKFORCE_PERFORMANCE_VIEW = (
        "workforce_performance.view",
        "مشاهده ارزیابی عملکرد حساس",
    )
    WORKFORCE_PERFORMANCE_MANAGE = (
        "workforce_performance.manage",
        "ثبت ارزیابی عملکرد حساس",
    )
    WORKFORCE_LABOR_RATES_VIEW = (
        "workforce_labor_rates.view",
        "مشاهده نرخ حساس نیروی کار",
    )
    WORKFORCE_LABOR_RATES_MANAGE = (
        "workforce_labor_rates.manage",
        "ثبت نسخه نرخ حساس نیروی کار",
    )
    TIME_CALENDARS_VIEW = "time_calendars.view", "مشاهده تقویم و شیفت"
    TIME_CALENDARS_MANAGE = "time_calendars.manage", "مدیریت تقویم و شیفت"
    ATTENDANCE_VIEW = "attendance.view", "مشاهده حضور"
    ATTENDANCE_CAPTURE = "attendance.capture", "ثبت دستی حضور"
    ATTENDANCE_REVIEW = "attendance.review", "قطعی‌سازی و رسیدگی حضور"
    ATTENDANCE_CORRECT = "attendance.correct", "اصلاح مستقل حضور قطعی"
    ATTENDANCE_IMPORT = "attendance.import", "درون‌ریزی حضور"
    LEAVE_MISSION_VIEW = "leave_mission.view", "مشاهده مرخصی و مأموریت"
    LEAVE_MISSION_REQUEST = "leave_mission.request", "ثبت مرخصی و مأموریت"
    LEAVE_MISSION_REVIEW = "leave_mission.review", "بررسی مرخصی و مأموریت"
    OVERTIME_VIEW = "overtime.view", "مشاهده اضافه‌کاری"
    OVERTIME_REQUEST = "overtime.request", "ثبت درخواست اضافه‌کاری"
    OVERTIME_REVIEW = "overtime.review", "بررسی اضافه‌کاری"
    TIMESHEETS_VIEW = "timesheets.view", "مشاهده کارکرد"
    TIMESHEETS_PREPARE = "timesheets.prepare", "تهیه و ارسال کارکرد"
    TIMESHEETS_REVIEW = "timesheets.review", "بررسی مستقل کارکرد"
    TIMESHEETS_PREVIEW = "timesheets.preview", "پیش‌نمایش غیرمالی توزیع کار"
    PAYROLL_CONFIGURATION_VIEW = (
        "payroll_configuration.view",
        "مشاهده پیکربندی و قواعد حقوق",
    )
    PAYROLL_CONFIGURATION_MANAGE = (
        "payroll_configuration.manage",
        "مدیریت پیکربندی و قواعد حقوق",
    )
    PAYROLL_PREPARE = "payroll.prepare", "تهیه ورودی و محاسبه حقوق"
    PAYROLL_REVIEW = "payroll.review", "بررسی اجرای حقوق"
    PAYROLL_FINALIZE = "payroll.finalize", "قطعی‌سازی اجرای حقوق"
    PAYROLL_ADJUST = "payroll.adjust", "تعدیل، برگشت و جایگزینی حقوق"
    PAYROLL_RESULTS_VIEW = "payroll_results.view", "مشاهده نتایج حساس حقوق"
    PAYSLIPS_VIEW = "payslips.view", "مشاهده فیش حقوق"
    PAYSLIPS_EXPORT = "payslips.export", "خروجی فیش حقوق"
    PAYROLL_ESS_VIEW = "payroll_ess.view_own", "مشاهده حقوق قطعی شخصی"
    PAYROLL_ESS_EXPORT = "payroll_ess.export_own", "دریافت فیش قطعی شخصی"
    PAYROLL_INQUIRIES_VIEW = "payroll_inquiries.view", "مشاهده پرسش مجاز حقوق"
    PAYROLL_INQUIRIES_REQUEST = "payroll_inquiries.request", "ثبت پرسش حقوق شخصی"
    PAYROLL_INQUIRIES_RESPOND = "payroll_inquiries.respond", "پاسخ به پرسش تخصیص‌یافته حقوق"
    PAYROLL_AUDIT_VIEW = "payroll_audit.view", "مشاهده ممیزی حساس حقوق"
    PAYROLL_STATUTORY_CONFIGURATION_VIEW = (
        "payroll_statutory_configuration.view",
        "مشاهده قواعد مقرراتی حقوق",
    )
    PAYROLL_STATUTORY_PREPARE = (
        "payroll_statutory.prepare",
        "تهیه محاسبات مقرراتی حقوق",
    )
    PAYROLL_STATUTORY_REVIEW = (
        "payroll_statutory.review",
        "بررسی محاسبات مقرراتی حقوق",
    )
    PAYROLL_STATUTORY_OUTPUT_GENERATE = (
        "payroll_statutory_outputs.generate",
        "تولید خروجی مقرراتی حقوق",
    )
    PAYROLL_STATUTORY_EXPORT = (
        "payroll_statutory_outputs.export",
        "ثبت خروجی و شاهد ارسال مقرراتی حقوق",
    )
    PAYROLL_STATUTORY_CORRECT = (
        "payroll_statutory.correct",
        "اصلاح و جایگزینی سابقه مقرراتی حقوق",
    )
    PAYROLL_STATUTORY_AUDIT_VIEW = (
        "payroll_statutory_audit.view",
        "مشاهده ممیزی حساس مقرراتی حقوق",
    )
    PAYROLL_LIABILITY_HANDOFF_PREPARE = (
        "payroll_liability_handoff.prepare",
        "تهیه پیشنهاد بدهی حقوق",
    )
    PAYROLL_LIABILITY_HANDOFF_REVIEW = (
        "payroll_liability_handoff.review",
        "بررسی پیشنهاد بدهی حقوق",
    )
    PAYROLL_ACCOUNTING_HANDOFF_PREPARE = (
        "payroll_accounting_handoff.prepare",
        "تهیه پیشنهاد حسابداری حقوق",
    )
    PAYROLL_ACCOUNTING_HANDOFF_REVIEW = (
        "payroll_accounting_handoff.review",
        "بررسی پیشنهاد حسابداری حقوق",
    )
    PAYROLL_PAYMENT_HANDOFF_PREPARE = (
        "payroll_payment_handoff.prepare",
        "تهیه پیشنهاد پرداخت حقوق",
    )
    PAYROLL_PAYMENT_HANDOFF_REVIEW = (
        "payroll_payment_handoff.review",
        "بررسی پیشنهاد پرداخت حقوق",
    )
    PAYROLL_PROJECT_COST_HANDOFF_PREPARE = (
        "payroll_project_cost_handoff.prepare",
        "تهیه پیشنهاد هزینه کار حقوق",
    )
    PAYROLL_PROJECT_COST_HANDOFF_REVIEW = (
        "payroll_project_cost_handoff.review",
        "بررسی پیشنهاد هزینه کار حقوق",
    )
    PAYROLL_HANDOFF_RECONCILIATION_PREPARE = (
        "payroll_handoff_reconciliation.prepare",
        "تهیه تطبیق تحویل مالی حقوق",
    )
    PAYROLL_HANDOFF_RECONCILIATION_REVIEW = (
        "payroll_handoff_reconciliation.review",
        "بررسی تطبیق تحویل مالی حقوق",
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
    PURCHASE_ORDER_CHANGES_REQUEST = (
        "purchase_order_changes.request",
        "درخواست تغییر سفارش خرید",
    )
    PURCHASE_ORDER_CHANGES_APPROVE = (
        "purchase_order_changes.approve",
        "تأیید مستقل تغییر سفارش خرید",
    )
    GOODS_RECEIPTS_VIEW = "goods_receipts.view", "مشاهده رسیدهای کالا"
    GOODS_RECEIPTS_CREATE = "goods_receipts.create", "ایجاد رسید کالا"
    GOODS_RECEIPT_ITEMS_ADD = "goods_receipt_items.add", "افزودن ردیف رسید کالا"
    GOODS_RECEIPTS_POST = "goods_receipts.post", "ثبت نهایی رسید کالا"
    GOODS_RECEIPTS_VOID = "goods_receipts.void", "ابطال رسید کالا"
    SERVICE_ACCEPTANCES_VIEW = "service_acceptances.view", "مشاهده پذیرش خدمت"
    SERVICE_ACCEPTANCES_CREATE = "service_acceptances.create", "ایجاد پذیرش خدمت"
    SERVICE_ACCEPTANCES_ACCEPT = (
        "service_acceptances.accept",
        "نهایی‌سازی پذیرش خدمت",
    )
    SERVICE_ACCEPTANCES_VOID = "service_acceptances.void", "ابطال پذیرش خدمت"
    SUPPLIER_INVOICES_VIEW = "supplier_invoices.view", "مشاهده صورتحساب تأمین‌کننده"
    SUPPLIER_INVOICES_PREPARE = (
        "supplier_invoices.prepare",
        "آماده‌سازی صورتحساب تأمین‌کننده",
    )
    SUPPLIER_INVOICES_APPROVE = (
        "supplier_invoices.approve",
        "تأیید مستقل صورتحساب تأمین‌کننده",
    )
    INVOICE_MATCH_POLICIES_MANAGE = (
        "invoice_match_policies.manage",
        "آماده‌سازی سیاست رواداری تطبیق",
    )
    INVOICE_MATCH_POLICIES_APPROVE = (
        "invoice_match_policies.approve",
        "تأیید مستقل سیاست رواداری تطبیق",
    )
    INVOICE_MATCHES_VIEW = "invoice_matches.view", "مشاهده تطبیق صورتحساب"
    INVOICE_MATCHES_RUN = "invoice_matches.run", "اجرای تطبیق صورتحساب"
    RFQS_VIEW = "rfqs.view", "مشاهده استعلام‌ها"
    TENDER_BIDS_VIEW = "tender_bids.view", "مشاهده مناقصه‌های پیمانکار"
    TENDER_BIDS_PREPARE = "tender_bids.prepare", "تهیه و بازنگری مناقصه پیمانکار"
    TENDER_BIDS_TRANSITION = "tender_bids.transition", "ثبت تغییر وضعیت مناقصه پیمانکار"
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
    SUPPLIER_PORTAL_INVITATIONS_MANAGE = (
        "supplier_portal.invitations_manage",
        "مدیریت دعوت و لغو دسترسی درگاه تأمین‌کننده",
    )
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
    RFQ_QUOTES_PREPARE_ADMISSIBILITY = (
        "rfq_quotes.prepare_admissibility",
        "آماده‌سازی پذیرش تجاری پیشنهاد",
    )
    RFQ_QUOTES_APPROVE_ADMISSIBILITY = (
        "rfq_quotes.approve_admissibility",
        "تأیید پذیرش تجاری پیشنهاد",
    )
    RFQ_QUOTES_PREPARE_COMPARISON = (
        "rfq_quotes.prepare_comparison",
        "آماده‌سازی مقایسه تجاری پیشنهاد",
    )
    RFQ_QUOTES_EVALUATE_COMPARISON = (
        "rfq_quotes.evaluate_comparison",
        "ارزیابی مقایسه تجاری پیشنهاد",
    )
    RFQ_QUOTES_APPROVE_EXCEPTION = (
        "rfq_quotes.approve_exception",
        "تأیید استثنای غیرمادی پیشنهاد",
    )
    RFQ_QUOTES_FINALIZE_COMPARISON = (
        "rfq_quotes.finalize_comparison",
        "نهایی‌سازی مقایسه تجاری پیشنهاد",
    )
    RFQ_QUOTES_DISPOSE_CONFLICT = (
        "rfq_quotes.dispose_conflict",
        "تعیین تکلیف تعارض ارزیاب پیشنهاد",
    )
    RFQ_QUOTES_PREPARE_SOURCING_AWARD = (
        "rfq_quotes.prepare_sourcing_award",
        "آماده‌سازی انتخاب تأمین‌کننده",
    )
    RFQ_QUOTES_FINALIZE_SOURCING_AWARD = (
        "rfq_quotes.finalize_sourcing_award",
        "نهایی‌سازی انتخاب تأمین‌کننده",
    )

    WAREHOUSES_VIEW = "warehouses.view", "مشاهده انبارها"
    WAREHOUSES_CREATE = "warehouses.create", "ایجاد انبار"
    WAREHOUSES_ARCHIVE = "warehouses.archive", "بایگانی انبار"
    STOCK_TRANSACTIONS_VIEW = "stock_transactions.view", "مشاهده تراکنش‌های انبار"
    STOCK_TRANSACTIONS_CREATE = "stock_transactions.create", "ایجاد تراکنش انبار"
    STOCK_TRANSACTIONS_POST = "stock_transactions.post", "ثبت نهایی تراکنش انبار"
    STOCK_TRANSACTIONS_REVERSE = "stock_transactions.reverse", "برگشت تراکنش انبار"
    STOCK_BALANCES_VIEW = "stock_balances.view", "مشاهده موجودی انبار"
    INVENTORY_RESERVATIONS_VIEW = (
        "inventory_reservations.view",
        "مشاهده رزروهای موجودی",
    )
    INVENTORY_RESERVATIONS_MANAGE = (
        "inventory_reservations.manage",
        "ایجاد و تخصیص رزرو موجودی",
    )
    INVENTORY_RESERVATIONS_RELEASE = (
        "inventory_reservations.release",
        "آزادسازی یا لغو رزرو موجودی",
    )
    INVENTORY_TRACEABILITY_VIEW = (
        "inventory_traceability.view",
        "مشاهده رهگیری موجودی",
    )
    INVENTORY_TRACEABILITY_MANAGE = (
        "inventory_traceability.manage",
        "مدیریت مکان و رهگیری موجودی",
    )
    INVENTORY_TRACEABILITY_DISPOSE = (
        "inventory_traceability.dispose",
        "تعیین تکلیف قرنطینه یا انقضای موجودی",
    )
    INVENTORY_COUNTS_VIEW = "inventory_counts.view", "مشاهده شمارش موجودی"
    INVENTORY_COUNTS_PREPARE = (
        "inventory_counts.prepare",
        "آماده‌سازی و ثبت شمارش موجودی",
    )
    INVENTORY_COUNTS_APPROVE = (
        "inventory_counts.approve",
        "تأیید مستقل شمارش موجودی",
    )
    INVENTORY_COUNTS_POST = (
        "inventory_counts.post",
        "ثبت تعدیل شمارش موجودی",
    )
    INVENTORY_TRANSFERS_VIEW = (
        "inventory_transfers.view",
        "مشاهده انتقال‌های امانی موجودی",
    )
    INVENTORY_TRANSFERS_PREPARE = (
        "inventory_transfers.prepare",
        "آماده‌سازی انتقال امانی موجودی",
    )
    INVENTORY_TRANSFERS_DISPATCH = (
        "inventory_transfers.dispatch",
        "ارسال انتقال امانی موجودی",
    )
    INVENTORY_TRANSFERS_ACCEPT = (
        "inventory_transfers.accept",
        "پذیرش مستقل انتقال امانی موجودی",
    )
    INVENTORY_TRANSFERS_RESOLVE = (
        "inventory_transfers.resolve",
        "تعیین تکلیف مغایرت انتقال موجودی",
    )
    INVENTORY_RECONCILIATIONS_VIEW = (
        "inventory_reconciliations.view",
        "مشاهده تطبیق مقدار و امانت موجودی",
    )
    INVENTORY_VALUATION_VIEW = "inventory_valuation.view", "مشاهده ارزش‌گذاری موجودی"
    INVENTORY_VALUATION_PREPARE = "inventory_valuation.prepare", "تهیه ارزش‌گذاری موجودی"
    INVENTORY_VALUATION_REVERSE = (
        "inventory_valuation.reverse",
        "برگشت ارزش‌گذاری موجودی",
    )
    INVENTORY_VALUATION_RECONCILE = (
        "inventory_valuation.reconcile",
        "تطبیق ارزش‌گذاری موجودی",
    )
    INVENTORY_VALUATION_SUPPLY = (
        "inventory_valuation.supply",
        "ارسال پیشنهاد هزینه موجودی",
    )

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
    EQUIPMENT_OPERATIONS_VIEW = "equipment_operations.view", "مشاهده عملیات تجهیز"
    EQUIPMENT_METERS_RECORD = "equipment_meters.record", "ثبت قرائت تجهیز"
    EQUIPMENT_METERS_CORRECT = "equipment_meters.correct", "اصلاح قرائت تجهیز"
    EQUIPMENT_USAGE_RECORD = "equipment_usage.record", "ثبت کارکرد تجهیز"
    EQUIPMENT_FUEL_RECORD = "equipment_fuel.record", "ثبت سوخت تجهیز"
    EQUIPMENT_DOWNTIME_MANAGE = "equipment_downtime.manage", "مدیریت توقف تجهیز"
    EQUIPMENT_QUALIFICATIONS_MANAGE = (
        "equipment_qualifications.manage",
        "مدیریت صلاحیت اپراتور تجهیز",
    )
    EQUIPMENT_MAINTENANCE_PLANS_MANAGE = (
        "equipment_maintenance_plans.manage",
        "مدیریت برنامه نگهداری",
    )
    EQUIPMENT_WORK_ORDERS_MANAGE = (
        "equipment_work_orders.manage",
        "مدیریت دستورکار نگهداری",
    )
    EQUIPMENT_WORK_ORDERS_COMPLETE = (
        "equipment_work_orders.complete",
        "تکمیل دستورکار نگهداری",
    )
    EQUIPMENT_WORK_ORDERS_REOPEN = (
        "equipment_work_orders.reopen",
        "بازگشایی دستورکار نگهداری",
    )
    EQUIPMENT_SPARE_LINKS_MANAGE = (
        "equipment_spare_links.manage",
        "پیوند قطعات یدکی تجهیز",
    )
    EQUIPMENT_SPARE_LINKS_RECONCILE = (
        "equipment_spare_links.reconcile",
        "تطبیق قطعات یدکی تجهیز",
    )
    EQUIPMENT_COST_POLICY_VIEW = (
        "equipment_cost_policy.view",
        "مشاهده سیاست هزینه تجهیز",
    )
    EQUIPMENT_COST_POLICY_MANAGE = (
        "equipment_cost_policy.manage",
        "تهیه سیاست هزینه تجهیز",
    )
    EQUIPMENT_COST_POLICY_PUBLISH = (
        "equipment_cost_policy.publish",
        "انتشار سیاست هزینه تجهیز",
    )
    EQUIPMENT_COST_ALLOCATION_VIEW = (
        "equipment_cost_allocation.view",
        "مشاهده تخصیص هزینه تجهیز",
    )
    EQUIPMENT_COST_ALLOCATION_PREPARE = (
        "equipment_cost_allocation.prepare",
        "تهیه تخصیص هزینه تجهیز",
    )
    EQUIPMENT_COST_ALLOCATION_REVIEW = (
        "equipment_cost_allocation.review",
        "بررسی تخصیص هزینه تجهیز",
    )
    EQUIPMENT_COST_ALLOCATION_REVERSE = (
        "equipment_cost_allocation.reverse",
        "برگشت تخصیص هزینه تجهیز",
    )
    EQUIPMENT_COST_HANDOFF_PREPARE = (
        "equipment_cost_handoff.prepare",
        "تهیه پیشنهاد هزینه تجهیز",
    )
    EQUIPMENT_COST_HANDOFF_REVIEW = (
        "equipment_cost_handoff.review",
        "بررسی پیشنهاد هزینه تجهیز",
    )
    EQUIPMENT_COST_HANDOFF_RECONCILE = (
        "equipment_cost_handoff.reconcile",
        "تطبیق پیشنهاد هزینه تجهیز",
    )

    FIXED_ASSETS_VIEW = "fixed_assets.view", "مشاهده دارایی‌های ثابت"
    FIXED_ASSET_CANDIDATE_PREPARE = (
        "fixed_assets.candidate_prepare",
        "تهیه نامزد دارایی ثابت",
    )
    FIXED_ASSET_CANDIDATE_REVIEW = (
        "fixed_assets.candidate_review",
        "بررسی نامزد دارایی ثابت",
    )
    FIXED_ASSETS_MANAGE = "fixed_assets.manage", "مدیریت دارایی ثابت"
    FIXED_ASSET_CLASS_POLICY_MANAGE = (
        "fixed_assets.class_policy_manage",
        "تهیه طبقه و سیاست دارایی",
    )
    FIXED_ASSET_CLASS_POLICY_PUBLISH = (
        "fixed_assets.class_policy_publish",
        "انتشار طبقه و سیاست دارایی",
    )
    FIXED_ASSET_CAPITALIZE = "fixed_assets.capitalize", "سرمایه‌ای‌کردن دارایی"
    FIXED_ASSET_TRANSACTION_PREPARE = (
        "fixed_assets.transaction_prepare",
        "تهیه رویداد دارایی",
    )
    FIXED_ASSET_TRANSACTION_REVIEW = (
        "fixed_assets.transaction_review",
        "بررسی رویداد دارایی",
    )
    FIXED_ASSET_TRANSACTION_REVERSE = (
        "fixed_assets.transaction_reverse",
        "برگشت رویداد دارایی",
    )
    FIXED_ASSET_DEPRECIATION_PREVIEW = (
        "fixed_assets.depreciation_preview",
        "پیش‌نمایش استهلاک",
    )
    FIXED_ASSET_DEPRECIATION_FINALIZE = (
        "fixed_assets.depreciation_finalize",
        "نهایی‌سازی استهلاک",
    )
    FIXED_ASSET_DEPRECIATION_REVERSE = (
        "fixed_assets.depreciation_reverse",
        "برگشت استهلاک",
    )
    FIXED_ASSET_TRANSFER = "fixed_assets.transfer", "انتقال دارایی ثابت"
    FIXED_ASSET_IMPAIR = "fixed_assets.impair", "کاهش ارزش دارایی ثابت"
    FIXED_ASSET_DISPOSE = "fixed_assets.dispose", "واگذاری یا خروج دارایی ثابت"
    FIXED_ASSET_HANDOFF_PREPARE = (
        "fixed_assets.handoff_prepare",
        "تهیه پیشنهاد دارایی ثابت",
    )
    FIXED_ASSET_HANDOFF_REVIEW = (
        "fixed_assets.handoff_review",
        "بررسی پیشنهاد دارایی ثابت",
    )
    FIXED_ASSET_HANDOFF_RECONCILE = (
        "fixed_assets.handoff_reconcile",
        "تطبیق پیشنهاد دارایی ثابت",
    )
    FIXED_ASSET_AUDIT_VIEW = "fixed_assets.audit_view", "مشاهده ممیزی دارایی ثابت"

    SAFETY_INCIDENTS_VIEW = "safety_incidents.view", "مشاهده حوادث ایمنی"
    SAFETY_INCIDENTS_CREATE = "safety_incidents.create", "ثبت حادثه ایمنی"
    SAFETY_INCIDENTS_REVIEW = "safety_incidents.review", "بررسی و تخصیص حادثه ایمنی"
    SAFETY_INCIDENTS_MANAGE = "safety_incidents.manage", "مدیریت اقدام اصلاحی ایمنی"
    SAFETY_INCIDENTS_CLOSE = "safety_incidents.close", "بستن حادثه ایمنی"
    SAFETY_INCIDENTS_RECORD_SUBMIT = (
        "safety_incidents.record_submit",
        "ارسال و اصلاح رکورد ایمنی",
    )
    SAFETY_INCIDENTS_RECORD_DECIDE = (
        "safety_incidents.record_decide",
        "تصمیم بررسی رکورد ایمنی",
    )

    QUALITY_ISSUES_VIEW = "quality_issues.view", "مشاهده مسائل کیفیت"
    QUALITY_ISSUES_CREATE = "quality_issues.create", "ثبت مسئله کیفیت"
    QUALITY_ISSUES_REVIEW = "quality_issues.review", "بررسی و تخصیص مسئله کیفیت"
    QUALITY_ISSUES_MANAGE = "quality_issues.manage", "مدیریت اقدام اصلاحی کیفیت"
    QUALITY_ISSUES_VERIFY = "quality_issues.verify", "راستی‌آزمایی مسئله کیفیت"
    QUALITY_ISSUES_CLOSE = "quality_issues.close", "بستن مسئله کیفیت"
    QUALITY_ISSUES_RECORD_SUBMIT = (
        "quality_issues.record_submit",
        "ارسال و اصلاح رکورد کیفیت",
    )
    QUALITY_ISSUES_RECORD_DECIDE = (
        "quality_issues.record_decide",
        "تصمیم بررسی رکورد کیفیت",
    )

    FINANCIALS_VIEW = "financials.view", "مشاهده داشبورد و گزارش‌های مالی"
    REPORTING_METRIC_CATALOG_VIEW = (
        "reporting.metric_catalog.view",
        "مشاهده کاتالوگ شاخص‌های حاکم‌شده",
    )
    REPORTING_METRIC_DEFINITION_PREPARE = (
        "reporting.metric_definition.prepare",
        "تهیه تعریف شاخص",
    )
    REPORTING_METRIC_DEFINITION_REVIEW = (
        "reporting.metric_definition.review",
        "بررسی تعریف شاخص",
    )
    REPORTING_METRIC_DEFINITION_PUBLISH = (
        "reporting.metric_definition.publish",
        "انتشار تعریف شاخص",
    )
    REPORTING_METRIC_RESULT_VIEW = (
        "reporting.metric_result.view",
        "مشاهده نتیجه شاخص",
    )
    REPORTING_METRIC_RESULT_VIEW_SENSITIVE = (
        "reporting.metric_result.view_sensitive",
        "مشاهده نتیجه حساس شاخص",
    )
    REPORTING_PORTFOLIO_VIEW = "reporting.portfolio.view", "مشاهده شاخص‌های سبد پروژه"
    REPORTING_METRIC_REFRESH_RUN = (
        "reporting.metric_refresh.run",
        "اجرای بازسازی شاخص",
    )
    REPORTING_METRIC_REFRESH_REVIEW = (
        "reporting.metric_refresh.review",
        "بررسی نتیجه بازسازی شاخص",
    )
    REPORTING_SOURCE_DRILLTHROUGH_VIEW = (
        "reporting.source_drillthrough.view",
        "مشاهده مسیر منبع شاخص",
    )
    REPORTING_SAVED_VIEW_MANAGE_OWN = (
        "reporting.saved_view.manage_own",
        "مدیریت نمای ذخیره‌شده شخصی",
    )
    REPORTING_SAVED_VIEW_MANAGE_SHARED = (
        "reporting.saved_view.manage_shared",
        "مدیریت نمای ذخیره‌شده مشترک",
    )
    REPORTING_EXPORT_CREATE = "reporting.export.create", "ایجاد خروجی کنترل‌شده شاخص"
    REPORTING_EXPORT_DOWNLOAD = (
        "reporting.export.download",
        "دریافت خروجی کنترل‌شده شاخص",
    )
    REPORTING_EXPORT_SENSITIVE = (
        "reporting.export.sensitive",
        "خروجی حساس شاخص",
    )
    REPORTING_AUDIT_VIEW = "reporting.audit.view", "مشاهده ممیزی گزارش‌گیری"
    REPORTING_RECONCILIATION_CATALOG_VIEW = (
        "reporting.reconciliation_catalog.view",
        "مشاهده کاتالوگ تطبیق",
    )
    REPORTING_RECONCILIATION_DEFINITION_PREPARE = (
        "reporting.reconciliation_definition.prepare",
        "تهیه تعریف تطبیق",
    )
    REPORTING_RECONCILIATION_DEFINITION_PUBLISH = (
        "reporting.reconciliation_definition.publish",
        "انتشار تعریف تطبیق",
    )
    REPORTING_RECONCILIATION_RUN_EXECUTE = (
        "reporting.reconciliation_run.execute",
        "اجرای تطبیق",
    )
    REPORTING_RECONCILIATION_RUN_VIEW = (
        "reporting.reconciliation_run.view",
        "مشاهده اجرای تطبیق",
    )
    REPORTING_RECONCILIATION_RUN_REVIEW = (
        "reporting.reconciliation_run.review",
        "بررسی اجرای تطبیق",
    )
    REPORTING_RECONCILIATION_EXCEPTION_VIEW = (
        "reporting.reconciliation_exception.view",
        "مشاهده مغایرت تطبیق",
    )
    REPORTING_RECONCILIATION_EXCEPTION_ASSIGN = (
        "reporting.reconciliation_exception.assign",
        "ارجاع مغایرت تطبیق",
    )
    REPORTING_RECONCILIATION_EXCEPTION_DISPOSITION = (
        "reporting.reconciliation_exception.disposition",
        "ثبت تصمیم مغایرت تطبیق",
    )
    REPORTING_RECONCILIATION_EXCEPTION_CLOSE = (
        "reporting.reconciliation_exception.close",
        "بستن مغایرت تطبیق",
    )
    REPORTING_RECONCILIATION_EXCEPTION_REOPEN = (
        "reporting.reconciliation_exception.reopen",
        "بازگشایی مغایرت تطبیق",
    )
    REPORTING_RECONCILIATION_EVIDENCE_LINK = (
        "reporting.reconciliation_evidence.link",
        "پیوند شاهد مغایرت تطبیق",
    )
    REPORTING_RECONCILIATION_REBUILD_EXECUTE = (
        "reporting.reconciliation_rebuild.execute",
        "اجرای بازسازی تطبیق",
    )
    REPORTING_RECONCILIATION_REBUILD_REVIEW = (
        "reporting.reconciliation_rebuild.review",
        "بررسی بازسازی تطبیق",
    )
    REPORTING_RECONCILIATION_AUDIT_VIEW = (
        "reporting.reconciliation_audit.view",
        "مشاهده ممیزی تطبیق",
    )
    REPORTING_PROJECT_CLOSEOUT_PROFILE_VIEW = (
        "reporting.project_closeout_profile.view",
        "مشاهده الگوی اختتام پروژه",
    )
    REPORTING_PROJECT_CLOSEOUT_PROFILE_PREPARE = (
        "reporting.project_closeout_profile.prepare",
        "تهیه الگوی اختتام پروژه",
    )
    REPORTING_PROJECT_CLOSEOUT_PROFILE_PUBLISH = (
        "reporting.project_closeout_profile.publish",
        "انتشار الگوی اختتام پروژه",
    )
    REPORTING_PROJECT_CLOSEOUT_CASE_VIEW = (
        "reporting.project_closeout_case.view",
        "مشاهده پرونده اختتام پروژه",
    )
    REPORTING_PROJECT_CLOSEOUT_CASE_PREPARE = (
        "reporting.project_closeout_case.prepare",
        "تهیه و ارزیابی پرونده اختتام پروژه",
    )
    REPORTING_PROJECT_CLOSEOUT_CASE_COORDINATE = (
        "reporting.project_closeout_case.coordinate",
        "هماهنگی پرونده اختتام پروژه",
    )
    REPORTING_PROJECT_CLOSEOUT_CASE_REVIEW = (
        "reporting.project_closeout_case.review",
        "بررسی پرونده اختتام پروژه",
    )
    REPORTING_PROJECT_CLOSEOUT_CASE_ACCEPT = (
        "reporting.project_closeout_case.accept",
        "پذیرش کنترل‌شده پرونده اختتام پروژه",
    )
    REPORTING_PROJECT_CLOSEOUT_CASE_REOPEN = (
        "reporting.project_closeout_case.reopen",
        "بازگشایی پرونده اختتام پروژه",
    )
    REPORTING_PROJECT_CLOSEOUT_EVIDENCE_LINK = (
        "reporting.project_closeout_evidence.link",
        "پیوند شاهد اختتام پروژه",
    )
    REPORTING_PROJECT_CLOSEOUT_SENSITIVE_VIEW = (
        "reporting.project_closeout_sensitive.view",
        "مشاهده داده حساس اختتام پروژه",
    )
    REPORTING_PROJECT_CLOSEOUT_EXPORT_CREATE = (
        "reporting.project_closeout_export.create",
        "ایجاد خروجی اختتام پروژه",
    )
    REPORTING_PROJECT_CLOSEOUT_EXPORT_DOWNLOAD = (
        "reporting.project_closeout_export.download",
        "دریافت خروجی اختتام پروژه",
    )
    REPORTING_PROJECT_CLOSEOUT_AUDIT_VIEW = (
        "reporting.project_closeout_audit.view",
        "مشاهده ممیزی اختتام پروژه",
    )
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


class InsuranceClassification(UUIDModel, TimeStampedModel):
    """Platform catalog identity; reviewed policy versions approve its applicability."""

    code = models.SlugField("کد طبقه‌بندی بیمه", max_length=100, unique=True)
    name = models.CharField("عنوان طبقه‌بندی بیمه", max_length=255)
    is_active = models.BooleanField("فعال", default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="insurance_classifications_created",
    )

    class Meta:
        ordering = ["code"]  # noqa: RUF012

    def save(self, *args: object, **kwargs: object) -> None:
        self.code = canonicalize_lower_identifier(self.code)
        if not self._state.adding:
            original = type(self).objects.get(pk=self.pk)
            if any(
                getattr(original, f) != getattr(self, f)
                for f in ("code", "name", "created_by_id")
            ):
                raise ValidationError(
                    "هویت طبقه‌بندی بیمه تغییرناپذیر است؛ طبقه‌بندی جدید ثبت کنید."
                )
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


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
    insurance_classification = models.ForeignKey(
        InsuranceClassification,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="policy_versions",
        verbose_name="طبقه‌بندی بیمه",
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
        if self.insurance_classification_id:
            from apps.organizations.policy_specs import (
                RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE,
            )

            if self.policy.code != RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE:
                raise ValidationError(
                    "طبقه‌بندی بیمه فقط به قواعد صورت‌وضعیت دریافتنی متصل می‌شود."
                )
            if (
                self.status == PolicyVersionStatus.DRAFT
                and not self.insurance_classification.is_active
            ):
                raise ValidationError("طبقه‌بندی بیمه غیرفعال است.")
        if (
            self.supersedes_id
            and self.supersedes.insurance_classification_id
            != self.insurance_classification_id
        ):
            raise ValidationError("نسخه جایگزین باید متعلق به همان طبقه‌بندی بیمه باشد.")
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
            if (
                original.insurance_classification_id != self.insurance_classification_id
                and self.review_evidence.exists()
            ):
                raise ValidationError(
                    "طبقه‌بندی نسخه بررسی‌شده تغییرناپذیر است؛ نسخه جدید ایجاد کنید."
                )
            if original.status != PolicyVersionStatus.DRAFT:
                immutable_fields = (
                    "policy_id",
                    "insurance_classification_id",
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
