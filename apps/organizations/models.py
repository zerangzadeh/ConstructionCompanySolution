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

from core.identifiers import (
    canonicalize_lower_identifier,
    canonicalize_upper_identifier,
)
from core.models import TimeStampedModel, UUIDModel

MAX_ORGANIZATION_LOGO_SIZE = 2 * 1024 * 1024
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


class MembershipStatus(models.TextChoices):
    PENDING_ROLE = "pending_role", "در انتظار تعیین نقش"
    ACTIVE = "active", "فعال"
    SUSPENDED = "suspended", "تعلیق‌شده"
    REVOKED = "revoked", "لغوشده"


class AccountConnectionRequestStatus(models.TextChoices):
    PENDING = "pending", "در انتظار پاسخ"
    ACCEPTED = "accepted", "پذیرفته‌شده"
    REJECTED = "rejected", "ردشده"


class BusinessPermissionCode(models.TextChoices):
    """Business capabilities implemented and enforced by application services."""

    MEMBERSHIP_VIEW = "membership.view", "مشاهده اعضای شرکت"
    MEMBERSHIP_CHANGE_ROLE = "membership.change_role", "تغییر نقش اعضای شرکت"
    MEMBERSHIP_CHANGE_STATUS = "membership.change_status", "تغییر وضعیت اعضای شرکت"
    ACCOUNTS_CREATE = "accounts.create", "ایجاد حساب کاربری شرکت"
    ACCOUNTS_RESET_PASSWORD = (
        "accounts.reset_password",
        "بازنشانی گذرواژه اعضای شرکت",
    )
    COMPANY_SETTINGS_VIEW = "company.settings.view", "مشاهده تنظیمات شرکت"
    COMPANY_SETTINGS_CHANGE = "company.settings.change", "ویرایش تنظیمات شرکت"

    PARTIES_VIEW = "parties.view", "مشاهده طرف‌های تجاری"
    PARTIES_CREATE = "parties.create", "ایجاد طرف تجاری"
    PARTIES_CHANGE = "parties.change", "ویرایش طرف تجاری"
    PARTIES_ARCHIVE = "parties.archive", "بایگانی طرف تجاری"
    PARTY_ROLES_ASSIGN = "party_roles.assign", "تخصیص نقش به طرف تجاری"
    PARTY_CONTACTS_ADD = "party_contacts.add", "افزودن راه ارتباطی طرف تجاری"

    UNITS_VIEW = "units.view", "مشاهده واحدهای اندازه‌گیری"
    UNITS_CREATE = "units.create", "ایجاد واحد اندازه‌گیری"
    UNITS_ARCHIVE = "units.archive", "بایگانی واحد اندازه‌گیری"
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

    EXPENSES_VIEW = "expenses.view", "مشاهده هزینه‌ها"
    EXPENSES_CREATE = "expenses.create", "ثبت هزینه"
    EXPENSES_VOID = "expenses.void", "ابطال هزینه"
    EXPENSE_CATEGORIES_VIEW = "expense_categories.view", "مشاهده دسته‌های هزینه"
    EXPENSE_CATEGORIES_CREATE = "expense_categories.create", "ایجاد دسته هزینه"
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
    """A global role assembled by a system administrator from known capabilities."""

    code = models.SlugField("کد نقش", max_length=64, unique=True)
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

    class Meta:
        verbose_name = "نقش شرکتی"
        verbose_name_plural = "نقش‌های شرکتی"
        ordering = ["name"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["is_owner"],
                condition=Q(is_owner=True),
                name="unique_company_owner_role",
            )
        ]

    def clean(self) -> None:
        super().clean()
        self.code = canonicalize_lower_identifier(self.code)
        if self.is_owner and (not self.is_system or not self.is_active):
            raise ValidationError("نقش مالک شرکت باید یک نقش سیستمی و فعال باقی بماند.")

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
    """Configuration owned by exactly one organization.

    The timezone and currency fields on :class:`Organization` remain during the
    compatibility period. Services keep their values synchronized when settings
    are changed.
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
        default="USD",
        validators=[
            RegexValidator(
                regex=r"^[A-Z]{3}$",
                message="واحد پول باید یک کد سه‌حرفی با حروف بزرگ لاتین باشد.",
            )
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
