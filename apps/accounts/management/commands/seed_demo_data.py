"""Seed a deterministic, development-only Persian ERP demonstration dataset."""

import sys
from collections.abc import Callable
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, TypeVar

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import models, transaction
from django.utils import timezone

from apps.accounts.models import LoginPageSettings, User
from apps.audit.models import AuditEvent
from apps.billing.models import (
    BaselineItem,
    ProgressClaim,
    ProgressRecord,
    ProjectBaseline,
)
from apps.billing.services import (
    add_baseline_item,
    approve_progress_claim,
    approve_project_baseline,
    create_progress_claim,
    create_progress_record,
    create_project_baseline,
    request_progress_verification,
    request_project_baseline_approval,
    submit_progress_claim,
    verify_progress_record,
)
from apps.contracts.models import Contract, ContractAmendment, ContractItem
from apps.contracts.services import (
    add_contract_item,
    approve_contract_amendment,
    create_contract,
    transition_contract_status,
)
from apps.contracts.workflow import request_contract_amendment_approval
from apps.daily_reports.models import (
    DailyActivity,
    DailyReport,
    DailyReportEquipmentEntry,
    DailyReportLaborEntry,
    DailyReportMaterialEntry,
    DailyReportStatus,
    DelayEvent,
)
from apps.daily_reports.services import (
    add_daily_activity,
    add_daily_report_equipment_entry,
    add_daily_report_labor_entry,
    add_daily_report_material_entry,
    add_delay_event,
    approve_daily_report,
    create_daily_report,
    submit_daily_report,
)
from apps.documents.models import Document, DocumentLink, DocumentVersion
from apps.documents.services import create_document
from apps.equipment.models import Equipment, EquipmentAssignment, MaintenanceRecord
from apps.equipment.services import (
    assign_equipment,
    create_equipment,
    create_maintenance_record,
)
from apps.estimates.models import Estimate, EstimateItem, EstimateRevision
from apps.estimates.services import add_estimate_item, approve_estimate, create_estimate
from apps.estimates.workflow import request_estimate_approval
from apps.expenses.models import Expense, ExpenseCategory
from apps.expenses.services import create_expense, create_expense_category
from apps.inventory.models import StockTransaction, StockTransactionStatus, Warehouse
from apps.inventory.services import (
    create_stock_transaction,
    create_warehouse,
    post_stock_transaction,
)
from apps.inventory.workflow import request_stock_transaction_posting
from apps.materials.models import Material, MaterialCategory, UnitOfMeasure
from apps.materials.services import (
    create_material,
    create_material_category,
    create_unit_of_measure,
)
from apps.organizations.models import (
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRole,
    Organization,
    OrganizationAccountConnectionRequest,
    OrganizationMembership,
    OrganizationRole,
    OrganizationSettings,
)
from apps.organizations.role_defaults import (
    DEFAULT_ROLE_METADATA,
    DEFAULT_ROLE_PERMISSIONS,
)
from apps.organizations.services import create_organization_with_owner
from apps.parties.models import BusinessParty, PartyContact, PartyRole
from apps.parties.services import (
    add_party_contact,
    assign_party_role,
    create_business_party,
)
from apps.procurement.models import (
    GoodsReceipt,
    GoodsReceiptItem,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseRequest,
    PurchaseRequestItem,
    PurchaseRequestStatus,
)
from apps.procurement.services import (
    add_goods_receipt_item,
    add_purchase_order_item,
    add_purchase_request_item,
    approve_purchase_request,
    create_goods_receipt,
    create_purchase_order,
    create_purchase_request,
    issue_purchase_order,
    post_goods_receipt,
    submit_purchase_request,
)
from apps.projects.models import Activity, Project, ProjectPhase, ProjectSite, WBSNode
from apps.projects.services import (
    create_activity,
    create_project,
    create_project_phase,
    create_project_site,
    create_wbs_node,
)
from apps.quality.models import (
    QualityIssue,
    QualityIssueSeverity,
    QualityIssueType,
)
from apps.quality.record_review import decide_quality_record, submit_quality_record
from apps.quality.services import (
    assign_quality_issue,
    close_quality_issue,
    create_quality_issue,
    review_quality_issue,
    start_quality_corrective_action,
    submit_quality_issue_for_verification,
    verify_quality_issue,
)
from apps.safety.models import (
    SafetyIncident,
    SafetyIncidentSeverity,
    SafetyIncidentType,
    SafetyReviewStatus,
)
from apps.safety.record_review import decide_safety_record, submit_safety_record
from apps.safety.services import (
    assign_safety_incident,
    close_safety_incident,
    create_safety_incident,
    resolve_safety_incident,
    review_safety_incident,
    start_corrective_action,
)
from apps.treasury.models import PaymentRequest
from apps.treasury.services import create_payment_request
from apps.workflows.models import (
    WorkflowCondition,
    WorkflowDefinition,
    WorkflowDelegation,
    WorkflowInstance,
    WorkflowRoutingRule,
    WorkflowStepDefinition,
    WorkflowStepInstance,
    WorkflowTemplate,
    WorkflowTransitionDefinition,
    WorkflowType,
    WorkflowVersion,
    WorkItem,
    WorkItemAssignmentHistory,
    WorkItemCandidate,
)
from apps.workflows.registry import registry
from apps.workflows.services import create_workflow_draft, edit_workflow_draft
from apps.workforce.models import (
    Department,
    Employee,
    EmployeePositionAssignment,
    EmployeeProjectAssignment,
    Position,
    WorkTeam,
)
from apps.workforce.services import (
    assign_employee_to_project,
    create_department,
    create_employee,
    create_position,
    create_work_team,
)

ModelType = TypeVar("ModelType", bound=models.Model)

ORGANIZATION_NAMES = (
    "شرکت سازه‌پردازان پارس",
    "گروه عمرانی افق تهران",
    "شرکت توسعه ابنیه سپهر",
    "مهندسان راه و سازه البرز",
)

DEMO_ADMIN_USERNAME = "admin"
DEMO_PASSWORD = "admin"

PERSON_NAMES = (
    ("علی", "رضایی"),
    ("مریم", "کاظمی"),
    ("رضا", "محمدی"),
    ("نگار", "احمدی"),
    ("سعید", "مرادی"),
    ("زهرا", "اکبری"),
    ("امیرحسین", "نوری"),
    ("الهام", "کریمی"),
    ("محمد", "حیدری"),
    ("پریسا", "جعفری"),
    ("حامد", "صادقی"),
    ("سمیه", "موسوی"),
    ("آرش", "بهرامی"),
    ("سارا", "قاسمی"),
    ("فرهاد", "امینی"),
    ("لیلا", "رحیمی"),
    ("پویان", "خسروی"),
    ("نرگس", "سلطانی"),
    ("بابک", "شریفی"),
    ("مهسا", "یوسفی"),
    ("کیوان", "رستمی"),
    ("آتنا", "مهدوی"),
    ("وحید", "نوروزی"),
    ("شبنم", "طاهری"),
    ("سامان", "فرهمند"),
    ("بهاره", "زمانی"),
    ("نیما", "زارعی"),
    ("نازنین", "راد"),
    ("مسعود", "پارسایی"),
    ("ترانه", "دانشور"),
)

PROJECTS = (
    (
        "مجتمع مسکونی باغستان",
        "احداث مجموعه مسکونی با رویکرد کاهش مصرف انرژی و محوطه‌سازی کامل",
        "تهران، منطقه ۲۲، بلوار پژوهش",
        Decimal(980000000000),
        "active",
    ),
    (
        "مرکز درمانی مهر",
        "ساخت مرکز درمانی تخصصی همراه با تأسیسات مکانیکی و برقی پیشرفته",
        "کرج، بلوار جمهوری، خیابان بهار",
        Decimal(640000000000),
        "active",
    ),
    (
        "بازسازی کارخانه نوآوران",
        "مقاوم‌سازی سازه موجود و نوسازی خطوط پشتیبانی و ساختمان اداری",
        "قزوین، شهر صنعتی البرز",
        Decimal(315000000000),
        "on_hold",
    ),
    (
        "ساختمان اداری آفتاب",
        "اجرای ساختمان اداری هوشمند با نمای خشک و پارکینگ طبقاتی",
        "اصفهان، خیابان هزارجریب",
        Decimal(520000000000),
        "planning",
    ),
)

PARTIES = (
    ("شرکت سرمایه‌گذاری شهر فردا", "client"),
    ("مهندسان مشاور دیدگاه سازه", "consultant"),
    ("تأمین بتن البرز", "supplier"),
    ("بازرگانی فولاد ایرانیان", "supplier"),
    ("پیمانکاری تأسیسات نیروی شرق", "subcontractor"),
    ("شرکت اجرای نمای سپید", "subcontractor"),
    ("خدمات ماشین‌آلات راهبرد", "supplier"),
    ("آزمایشگاه فنی پایش بنا", "other"),
)

UNITS = (
    ("M", "متر", "m", "length", 2),
    ("M2", "متر مربع", "m2", "area", 2),
    ("M3", "متر مکعب", "m3", "volume", 3),
    ("KG", "کیلوگرم", "kg", "weight", 2),
    ("EA", "عدد", "ea", "count", 0),
)

MATERIAL_CATEGORIES = (
    ("CON", "بتن و افزودنی‌ها"),
    ("STL", "فولاد و میلگرد"),
    ("FIN", "مصالح نازک‌کاری"),
    ("MEP", "تأسیسات مکانیکی و برقی"),
)

MATERIALS = (
    ("CON-C30", "بتن آماده رده سی سی", 0, 2, "اسلامپ کنترل‌شده برای اعضای سازه‌ای"),
    ("CEM-T2", "سیمان پرتلند تیپ دو", 0, 3, "مناسب محیط‌های با حمله متوسط سولفات"),
    ("REB-16", "میلگرد آجدار شانزده", 1, 3, "رده مقاومتی آج چهارصد"),
    ("REB-20", "میلگرد آجدار بیست", 1, 3, "رده مقاومتی آج چهارصد"),
    ("BRK-CLY", "آجر سفالی دیواری", 2, 4, "بلوک سفالی سبک برای تیغه داخلی"),
    ("TIL-GRY", "کاشی پرسلانی طوسی", 2, 1, "سطح مات و مقاوم در برابر سایش"),
    ("PLS-WHT", "گچ سفیدکاری ممتاز", 2, 3, "دانه‌بندی یکنواخت برای پرداخت نهایی"),
    ("PIP-PPR", "لوله پلیمری آب‌رسانی", 3, 0, "مناسب شبکه آب سرد و گرم ساختمان"),
    ("CAB-4", "کابل مسی چهار رشته", 3, 0, "روکش مقاوم و سطح مقطع استاندارد"),
    ("VAL-BRS", "شیرآلات برنجی صنعتی", 3, 4, "مناسب رایزرهای تأسیساتی"),
)

CONTRACT_SUBJECTS = (
    ("قرارداد مدیریت پیمان و اجرای عملیات اصلی", 0, "receivable", "client"),
    ("قرارداد تأمین بتن آماده و خدمات پمپاژ", 2, "payable", "supplier"),
    ("قرارداد خرید و تحویل فولاد مصرفی", 3, "payable", "supplier"),
    ("قرارداد اجرای تأسیسات مکانیکی و برقی", 4, "payable", "subcontract"),
    ("قرارداد اجرای نما و پوسته ساختمان", 5, "payable", "subcontract"),
)

EXPENSES = (
    ("خرید اقلام مصرفی تجهیز کارگاه", "materials", 0),
    ("هزینه حمل مصالح تا محل پروژه", "other", 1),
    ("اجاره ماهانه جرثقیل و بالابر", "equipment", 2),
    ("دستمزد نیروی اجرایی پیمان روزمزد", "labor", 3),
    ("هزینه آزمایش مقاومت نمونه‌های بتن", "other", 4),
)

REPORT_WORK = (
    "آماده‌سازی بستر و کنترل تراز محورهای اجرایی انجام شد.",
    "آرماتوربندی و قالب‌بندی بخش شرقی فونداسیون ادامه یافت.",
    "بتن‌ریزی پی نواری با کنترل پیوسته کیفیت اجرا شد.",
    "نصب ستون‌ها و مهاربندی موقت جبهه شمالی انجام شد.",
    "دیوارچینی پیرامونی طبقه همکف مطابق نقشه پیش رفت.",
    "اجرای رایزرهای تأسیساتی و جانمایی غلاف‌ها تکمیل شد.",
    "زیرسازی نما و کنترل اتصالات مکانیکی انجام گرفت.",
    "پاک‌سازی کارگاه و تحویل جبهه کاری مرحله بعد انجام شد.",
)


class Command(BaseCommand):
    help = "Create deterministic Persian demo data in development only."

    tracked_models = (
        User,
        LoginPageSettings,
        # System-owned business catalog records are restored only when absent;
        # Django's own auth/session/content-type records are never seeded here.
        BusinessPermission,
        OrganizationRole,
        Organization,
        OrganizationSettings,
        OrganizationMembership,
        OrganizationAccountConnectionRequest,
        BusinessParty,
        PartyRole,
        PartyContact,
        UnitOfMeasure,
        MaterialCategory,
        Material,
        Project,
        ProjectSite,
        ProjectPhase,
        WBSNode,
        Activity,
        Contract,
        ContractItem,
        ContractAmendment,
        Estimate,
        EstimateRevision,
        EstimateItem,
        ExpenseCategory,
        Expense,
        PaymentRequest,
        ProjectBaseline,
        BaselineItem,
        ProgressRecord,
        ProgressClaim,
        Document,
        DocumentVersion,
        DocumentLink,
        DailyReport,
        DailyReportLaborEntry,
        DailyReportEquipmentEntry,
        DailyReportMaterialEntry,
        DailyActivity,
        DelayEvent,
        Department,
        Position,
        WorkTeam,
        Employee,
        EmployeePositionAssignment,
        EmployeeProjectAssignment,
        Equipment,
        EquipmentAssignment,
        MaintenanceRecord,
        SafetyIncident,
        QualityIssue,
        PurchaseRequest,
        PurchaseRequestItem,
        PurchaseOrder,
        PurchaseOrderItem,
        GoodsReceipt,
        GoodsReceiptItem,
        Warehouse,
        StockTransaction,
        AuditEvent,
        WorkflowType,
        WorkflowTemplate,
        WorkflowDefinition,
        WorkflowVersion,
        WorkflowStepDefinition,
        WorkflowTransitionDefinition,
        WorkflowCondition,
        WorkflowRoutingRule,
        WorkflowInstance,
        WorkflowStepInstance,
        WorkItem,
        WorkItemCandidate,
        WorkItemAssignmentHistory,
        WorkflowDelegation,
    )

    def handle(self, *args: object, **options: object) -> None:
        if not settings.DEBUG and "pytest" not in sys.modules:
            raise CommandError(
                "seed_demo_data is restricted to config.settings.development with DEBUG=True."
            )

        before = {model: model.objects.count() for model in self.tracked_models}
        # This development command is idempotent.  Keep each tenant isolated in
        # its own transaction instead of holding one multi-tenant transaction
        # open for the whole dataset; long checkpoints or an interrupted local
        # session must not leave all four tenants in one oversized transaction.
        with transaction.atomic():
            self._ensure_system_catalog()
            admin = self._admin_user()
        for organization_index, organization_name in enumerate(
            ORGANIZATION_NAMES, start=1
        ):
            with transaction.atomic():
                self._seed_organization(organization_index, organization_name, admin)

        self.stdout.write(self.style.SUCCESS("Persian demo dataset is ready."))
        self.stdout.write(f"Admin username: {DEMO_ADMIN_USERNAME}")
        self.stdout.write(f"Admin password: {DEMO_PASSWORD}")
        for model in self.tracked_models:
            created = model.objects.count() - before[model]
            self.stdout.write(f"{model._meta.label}: {created} created")

    def _existing_or_create(
        self,
        model: type[ModelType],
        lookup: dict[str, Any],
        creator: Callable[[], ModelType],
    ) -> ModelType:
        existing = model.objects.filter(**lookup).first()
        return existing if existing is not None else creator()

    def _ensure_system_catalog(self) -> None:
        """Restore only missing migration-owned business catalog records.

        A development database can have migration history without its data
        migrations (for example after a restored schema-only dump).  Creating
        an organization through the approved service requires these global
        roles and permissions.  Existing catalog records and role grants are
        intentionally left untouched.
        """

        permissions: dict[str, BusinessPermission] = {}
        for code in BusinessPermissionCode.values:
            permission, _ = BusinessPermission.objects.get_or_create(
                code=code,
                defaults={
                    "name": BusinessPermissionCode(code).label,
                    "description": "مجوز سیستمی موردنیاز سامانه ساخت.",
                    "is_active": True,
                },
            )
            permissions[code] = permission

        for code, metadata in DEFAULT_ROLE_METADATA.items():
            role, created = OrganizationRole.objects.get_or_create(
                code=code,
                defaults=metadata,
            )
            if created:
                role.permissions.add(
                    *(
                        permissions[permission]
                        for permission in DEFAULT_ROLE_PERMISSIONS[code]
                    )
                )

        workflow_catalog = (
            (
                "procurement.purchase_request_approval",
                "درخواست خرید",
                "گردش‌کار تأیید درخواست خرید سازگار با فرآیند تدارکات.",
                "purchase_request_legacy_compatibility",
                "سازگاری تأیید درخواست خرید",
                "رفتار تأیید یا رد تک‌مرحله‌ای درخواست خرید.",
                "apps.procurement.workflow",
            ),
            (
                "daily_reports.daily_report_approval",
                "تأیید گزارش روزانه",
                "گردش‌کار مرحله‌ای ارسال و تأیید گزارش روزانه.",
                "daily_report_legacy_compatibility",
                "سازگاری تأیید گزارش روزانه",
                "رفتار ارسال و تأیید گزارش روزانه.",
                "apps.daily_reports.workflow",
            ),
            (
                "safety.safety_incident_lifecycle",
                "چرخه حادثه ایمنی",
                "گردش‌کار بررسی، اقدام اصلاحی و بستن حادثه ایمنی.",
                "safety_incident_legacy_compatibility",
                "سازگاری چرخه حادثه ایمنی",
                "رفتار چرخه وضعیت فعلی حادثه ایمنی.",
                "apps.safety.workflow",
            ),
            (
                "estimates.estimate_approval",
                "تأیید برآورد",
                "گردش‌کار تأیید برآورد و بازنگری جاری.",
                "estimate_legacy_compatibility",
                "سازگاری تأیید برآورد",
                "رفتار تأیید تک‌مرحله‌ای برآورد.",
                "apps.estimates.workflow",
            ),
            (
                "contracts.contract_amendment_approval",
                "تأیید الحاقیه قرارداد",
                "گردش‌کار تأیید الحاقیه قرارداد.",
                "contract_amendment_legacy_compatibility",
                "سازگاری تأیید الحاقیه",
                "رفتار تأیید تک‌مرحله‌ای الحاقیه قرارداد.",
                "apps.contracts.workflow",
            ),
            (
                "quality.quality_issue_lifecycle",
                "چرخه مسئله کیفیت",
                "بررسی، تخصیص، اقدام، راستی‌آزمایی و بستن مسئله کیفیت.",
                "quality_issue_legacy_compatibility",
                "سازگاری چرخه مسئله کیفیت",
                "چرخه فعلی مسئله کیفیت.",
                "apps.quality.workflow",
            ),
            (
                "equipment.maintenance_record_lifecycle",
                "چرخه سرویس و تعمیر تجهیز",
                "چرخه اقدام‌پذیر سرویس، تعمیر و بازرسی تجهیزات.",
                "maintenance_record_lifecycle_legacy_compatibility",
                "سازگاری چرخه سرویس و تعمیر تجهیز",
                "چرخه فعلی سرویس و تعمیر تجهیز.",
                "apps.equipment.workflow",
            ),
        )
        for (
            code,
            name,
            description,
            template_code,
            template_name,
            template_description,
            module_path,
        ) in workflow_catalog:
            specification = registry.workflow_types[code]
            workflow_type, _ = WorkflowType.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "description": description,
                    "subject_type": specification.subject_type,
                    "subject_adapter": specification.subject_adapter,
                    "allowed_scope_fields": sorted(specification.allowed_scope_fields),
                    "is_active": True,
                },
            )
            module = __import__(module_path, fromlist=["COMPATIBILITY_CONFIGURATION"])
            WorkflowTemplate.objects.get_or_create(
                workflow_type=workflow_type,
                code=template_code,
                defaults={
                    "name": template_name,
                    "description": template_description,
                    "configuration": module.COMPATIBILITY_CONFIGURATION,
                    "is_active": True,
                },
            )
        inventory_workflow = __import__(
            "apps.inventory.workflow", fromlist=["POSTING", "REVERSAL"]
        )
        for action in (inventory_workflow.POSTING, inventory_workflow.REVERSAL):
            specification = registry.workflow_types[action.workflow_type]
            workflow_type, _ = WorkflowType.objects.get_or_create(
                code=action.workflow_type,
                defaults={
                    "name": action.name,
                    "description": action.description,
                    "subject_type": specification.subject_type,
                    "subject_adapter": specification.subject_adapter,
                    "allowed_scope_fields": sorted(specification.allowed_scope_fields),
                    "is_active": True,
                },
            )
            WorkflowTemplate.objects.get_or_create(
                workflow_type=workflow_type,
                code=action.template_code,
                defaults={
                    "name": f"سازگاری {action.name}",
                    "description": action.description,
                    "configuration": inventory_workflow._configuration(action),
                    "is_active": True,
                },
            )

        # F6 catalog rows are migration-owned, too.  Include them in this
        # repair path so a schema-only restored development database can seed
        # the complete approved billing lifecycle.
        billing_catalog = (
            (
                "billing.project_baseline_approval",
                "تأیید مبنای تجاری پروژه",
                "تأیید مبنای تجاری کاملاً قیمت‌گذاری‌شده پروژه.",
                "billing.project_baseline",
                ["project_id", "contract_id"],
                "project_baseline_f61",
                "baselines.approve",
                {
                    "steps": [
                        {
                            "key": "start",
                            "name": "شروع",
                            "step_type": "start",
                            "is_start": True,
                        },
                        {
                            "key": "approval",
                            "name": "تأیید مبنای تجاری",
                            "step_type": "approval",
                            "configuration": {"decision_policy": "any"},
                            "routing": [
                                {
                                    "resolver_type": "business_permission",
                                    "configuration": {
                                        "permission": "baselines.approve"
                                    },
                                },
                            ],
                        },
                        {
                            "key": "approved",
                            "name": "تأییدشده",
                            "step_type": "end",
                            "is_terminal": True,
                        },
                    ],
                    "transitions": [
                        {
                            "source": "start",
                            "target": "approval",
                            "outcome": "requested",
                            "is_default": True,
                        },
                        {
                            "source": "approval",
                            "target": "approved",
                            "outcome": "approved",
                            "domain_command": "billing.project_baseline.approve",
                            "required_permission": "baselines.approve",
                        },
                    ],
                },
            ),
            (
                "billing.progress_verification",
                "راستی‌آزمایی پیشرفت",
                "راستی‌آزمایی منبع اندازه‌گیری پیشرفت پروژه.",
                "billing.progress_record",
                ["project_id", "contract_id", "baseline_id"],
                "progress_verification_f62",
                "progress.verify",
                {
                    "steps": [
                        {
                            "key": "start",
                            "name": "شروع",
                            "step_type": "start",
                            "is_start": True,
                        },
                        {
                            "key": "verification",
                            "name": "راستی‌آزمایی پیشرفت",
                            "step_type": "approval",
                            "configuration": {"decision_policy": "any"},
                            "routing": [
                                {
                                    "resolver_type": "business_permission",
                                    "configuration": {"permission": "progress.verify"},
                                },
                            ],
                        },
                        {
                            "key": "verified",
                            "name": "راستی‌آزمایی‌شده",
                            "step_type": "end",
                            "is_terminal": True,
                        },
                        {
                            "key": "rejected",
                            "name": "ردشده",
                            "step_type": "end",
                            "is_terminal": True,
                        },
                    ],
                    "transitions": [
                        {
                            "source": "start",
                            "target": "verification",
                            "outcome": "requested",
                            "is_default": True,
                        },
                        {
                            "source": "verification",
                            "target": "verified",
                            "outcome": "verified",
                            "domain_command": "billing.progress.verify",
                            "required_permission": "progress.verify",
                        },
                        {
                            "source": "verification",
                            "target": "rejected",
                            "outcome": "rejected",
                            "domain_command": "billing.progress.reject",
                            "required_permission": "progress.verify",
                        },
                    ],
                },
            ),
            (
                "billing.progress_claim_approval",
                "تأیید صورت‌وضعیت",
                "تأیید یا بازگردانی نسخه ارسالی صورت‌وضعیت.",
                "billing.progress_claim",
                ["project_id", "contract_id", "baseline_id"],
                "progress_claim_approval_f64",
                "claims.approve",
                {
                    "steps": [
                        {
                            "key": "start",
                            "name": "شروع",
                            "step_type": "start",
                            "is_start": True,
                        },
                        {
                            "key": "approval",
                            "name": "تأیید صورت‌وضعیت",
                            "step_type": "approval",
                            "configuration": {
                                "decision_policy": "any",
                                "exclude_submitter": True,
                            },
                            "routing": [
                                {
                                    "resolver_type": "submitter_primary_position_manager",
                                    "configuration": {"permission": "claims.approve"},
                                },
                                {
                                    "resolver_type": "business_permission",
                                    "configuration": {
                                        "permission": "claims.approve",
                                        "exclude_submitter_unless_no_other": True,
                                    },
                                    "is_fallback": True,
                                },
                            ],
                        },
                        {
                            "key": "approved",
                            "name": "تأییدشده",
                            "step_type": "end",
                            "is_terminal": True,
                        },
                        {
                            "key": "returned",
                            "name": "بازگردانده‌شده",
                            "step_type": "end",
                            "is_terminal": True,
                        },
                    ],
                    "transitions": [
                        {
                            "source": "start",
                            "target": "approval",
                            "outcome": "requested",
                            "is_default": True,
                        },
                        {
                            "source": "approval",
                            "target": "approved",
                            "outcome": "approved",
                            "domain_command": "billing.progress_claim.approve",
                            "required_permission": "claims.approve",
                        },
                        {
                            "source": "approval",
                            "target": "returned",
                            "outcome": "returned",
                            "domain_command": "billing.progress_claim.return",
                            "required_permission": "claims.approve",
                        },
                    ],
                },
            ),
        )
        runtime_permissions = list(
            BusinessPermission.objects.filter(
                code__in=("work_items.view", "work_items.claim", "work_items.act")
            )
        )
        for (
            code,
            name,
            description,
            subject_type,
            allowed_scope_fields,
            template_code,
            approval_permission,
            configuration,
        ) in billing_catalog:
            workflow_type, _ = WorkflowType.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "description": description,
                    "subject_type": subject_type,
                    "subject_adapter": subject_type,
                    "allowed_scope_fields": allowed_scope_fields,
                    "is_active": True,
                },
            )
            WorkflowTemplate.objects.get_or_create(
                workflow_type=workflow_type,
                code=template_code,
                defaults={
                    "name": name,
                    "description": "مسیر تک‌مرحله‌ای مناسب سازمان‌های کوچک.",
                    "configuration": configuration,
                    "is_active": True,
                },
            )
            for role in OrganizationRole.objects.filter(
                permissions__code=approval_permission
            ).distinct():
                role.permissions.add(*runtime_permissions)

    def _admin_user(self) -> User:
        """Create the single development administrator without changing it later."""

        admin = User.objects.filter(username=DEMO_ADMIN_USERNAME).first()
        if admin is None:
            return User.objects.create_superuser(
                username=DEMO_ADMIN_USERNAME,
                password=DEMO_PASSWORD,
                first_name="مدیر",
                last_name="سامانه",
            )
        if not admin.is_staff or not admin.is_superuser:
            raise CommandError(
                f"The existing '{DEMO_ADMIN_USERNAME}' user is not a superuser."
            )
        return admin

    def _seed_organization(self, index: int, name: str, owner: User) -> None:
        slug = f"demo-construction-{index:02d}"
        organization = self._existing_or_create(
            Organization,
            {"slug": slug},
            lambda: create_organization_with_owner(
                owner=owner,
                name=name,
                legal_name=f"{name} (سهامی خاص)",
                slug=slug,
                timezone_name="Asia/Tehran",
                currency="IRR",
            ),
        )
        # The organization service creates the initial active owner membership.
        # This command deliberately creates no other demo authentication users.
        OrganizationMembership.objects.get_or_create(
            organization=organization,
            user=owner,
            defaults={"role": MembershipRole.COMPANY_OWNER, "status": "active"},
        )

        parties = self._seed_parties(index, organization, owner)
        units = self._seed_units(organization, owner)
        categories = self._seed_material_categories(organization, owner)
        materials = self._seed_materials(organization, owner, units, categories)
        expense_categories = self._seed_expense_categories(organization, owner)

        first_project: Project | None = None
        first_site: ProjectSite | None = None
        for project_index, project_data in enumerate(PROJECTS, start=1):
            project, site = self._seed_project(
                organization_index=index,
                project_index=project_index,
                organization=organization,
                owner=owner,
                manager=owner,
                parties=parties,
                units=units,
                materials=materials,
                expense_categories=expense_categories,
                project_data=project_data,
            )
            if first_project is None:
                first_project, first_site = project, site

        if first_project is not None and first_site is not None:
            self._seed_workforce(
                organization=organization,
                owner=owner,
                manager=owner,
                project=first_project,
                site=first_site,
            )
            self._seed_equipment(
                organization=organization,
                owner=owner,
                project=first_project,
                site=first_site,
                maintenance_provider=parties[6],
                organization_index=index,
            )
            self._seed_workflow_condition_example(
                organization=organization,
                owner=owner,
                project=first_project,
            )

    def _seed_workflow_condition_example(
        self,
        *,
        organization: Organization,
        owner: User,
        project: Project,
    ) -> None:
        """Add one valid, unpublished condition example per tenant.

        Published compatibility workflows are immutable, so this demonstration
        stays a draft and cannot change live routing or domain transitions.
        """

        code = "demo-purchase-request-condition"
        if WorkflowDefinition.objects.filter(
            organization=organization,
            code=code,
        ).exists():
            return
        version = create_workflow_draft(
            actor=owner,
            organization=organization,
            workflow_type_code="procurement.purchase_request_approval",
            code=code,
            name="نمونه شرط تأیید درخواست خرید",
            description="پیش‌نویس آموزشی برای بررسی شرط‌های مجاز گردش‌کار.",
            scope={"project_id": str(project.pk)},
            change_summary="نمونه داده توسعه‌ای",
        )
        edit_workflow_draft(
            actor=owner,
            organization=organization,
            version_id=version.pk,
            configuration={
                "steps": [
                    {
                        "key": "start",
                        "name": "شروع",
                        "step_type": "start",
                        "is_start": True,
                    },
                    {
                        "key": "decision",
                        "name": "تصمیم مالک",
                        "step_type": "approval",
                        "configuration": {"decision_policy": "any"},
                        "routing": [
                            {
                                "resolver_type": "business_permission",
                                "configuration": {
                                    "permission": "purchase_requests.reject"
                                },
                            }
                        ],
                    },
                    {
                        "key": "approved",
                        "name": "تأییدشده",
                        "step_type": "end",
                        "is_terminal": True,
                    },
                    {
                        "key": "rejected",
                        "name": "ردشده",
                        "step_type": "end",
                        "is_terminal": True,
                    },
                ],
                "transitions": [
                    {
                        "source": "start",
                        "target": "decision",
                        "outcome": "submitted",
                        "is_default": True,
                    },
                    {
                        "source": "decision",
                        "target": "approved",
                        "outcome": "approved",
                        "domain_command": "procurement.purchase_request.approve",
                        "required_permission": "purchase_requests.approve",
                        "conditions": [{"condition_type": "always"}],
                    },
                    {
                        "source": "decision",
                        "target": "rejected",
                        "outcome": "rejected",
                        "domain_command": "procurement.purchase_request.reject",
                        "required_permission": "purchase_requests.reject",
                    },
                ],
            },
        )

    def _seed_equipment(
        self,
        *,
        organization: Organization,
        owner: User,
        project: Project,
        site: ProjectSite,
        maintenance_provider: BusinessParty,
        organization_index: int,
    ) -> None:
        excavator = self._existing_or_create(
            Equipment,
            {"organization": organization, "code": f"EQ-{organization_index:02d}-EXC"},
            lambda: create_equipment(
                organization=organization,
                actor=owner,
                code=f"EQ-{organization_index:02d}-EXC",
                name="بیل مکانیکی زنجیری",
                category="ماشین‌آلات سنگین",
                manufacturer="کوماتسو",
                model="PC200",
                serial_number=f"DEMO-EXC-{organization_index:02d}",
                registration_number=f"TEH-{organization_index:02d}-381",
                acquired_on=date(2025, 1, 15),
                notes="تجهیز نمونه برای عملیات خاک‌برداری و بارگیری کارگاه.",
            ),
        )
        self._existing_or_create(
            Equipment,
            {"organization": organization, "code": f"EQ-{organization_index:02d}-CRN"},
            lambda: create_equipment(
                organization=organization,
                actor=owner,
                code=f"EQ-{organization_index:02d}-CRN",
                name="جرثقیل کارگاهی",
                category="تجهیزات بالابری",
                ownership_type="rented",
                manufacturer="پتن",
                model="ST 80",
                registration_number=f"TEH-{organization_index:02d}-582",
                acquired_on=date(2026, 3, 21),
                notes="تجهیز اجاره‌ای نمونه برای جابه‌جایی مصالح در کارگاه.",
            ),
        )
        self._existing_or_create(
            EquipmentAssignment,
            {
                "organization": organization,
                "equipment": excavator,
                "project": project,
                "start_date": date(2026, 1, 1),
            },
            lambda: assign_equipment(
                organization=organization,
                actor=owner,
                equipment=excavator,
                project=project,
                site=site,
                start_date=date(2026, 1, 1),
                purpose="عملیات خاک‌برداری و آماده‌سازی محوطه",
                notes="تخصیص فعال نمونه برای کارگاه اصلی پروژه.",
            ),
        )
        self._existing_or_create(
            MaintenanceRecord,
            {
                "organization": organization,
                "record_number": f"MNT-{organization_index:02d}-001",
            },
            lambda: create_maintenance_record(
                organization=organization,
                actor=owner,
                equipment=excavator,
                record_number=f"MNT-{organization_index:02d}-001",
                maintenance_type="preventive",
                summary="سرویس دوره‌ای بیل مکانیکی",
                scheduled_date=date(2026, 10, 1),
                project=project,
                site=site,
                provider=maintenance_provider,
                description="بازرسی روغن هیدرولیک، فیلترها و اتصالات بازو.",
                notes="سرویس پیشگیرانه نمونه در تقویم نگهداری.",
            ),
        )

    def _seed_parties(
        self, index: int, organization: Organization, owner: User
    ) -> list[BusinessParty]:
        result = []
        for party_index, (party_name, role) in enumerate(PARTIES, start=1):
            tax_identifier = f"DEMO{index:02d}{party_index:09d}"
            party = self._existing_or_create(
                BusinessParty,
                {"organization": organization, "tax_identifier": tax_identifier},
                lambda party_name=party_name, tax_identifier=tax_identifier: (
                    create_business_party(
                        organization=organization,
                        actor=owner,
                        party_kind="company",
                        display_name=party_name,
                        legal_name=f"{party_name} (ثبت‌شده)",
                        tax_identifier=tax_identifier,
                    )
                ),
            )
            if not PartyRole.objects.filter(
                organization=organization, party=party, role=role
            ).exists():
                assign_party_role(
                    organization=organization, actor=owner, party=party, role=role
                )
            phone = f"021-88{index:02d}{party_index:04d}"
            if not PartyContact.objects.filter(
                organization=organization,
                party=party,
                contact_type="phone",
                value=phone,
            ).exists():
                add_party_contact(
                    organization=organization,
                    actor=owner,
                    party=party,
                    contact_type="phone",
                    value=phone,
                    label="دفتر مرکزی",
                    is_primary=True,
                )
            result.append(party)
        return result

    def _seed_units(
        self, organization: Organization, owner: User
    ) -> list[UnitOfMeasure]:
        result = []
        for code, name, symbol, category, decimal_places in UNITS:
            unit = self._existing_or_create(
                UnitOfMeasure,
                {"organization": organization, "code": code},
                lambda code=code, name=name, symbol=symbol, category=category, decimal_places=decimal_places: (
                    create_unit_of_measure(
                        organization=organization,
                        actor=owner,
                        code=code,
                        name=name,
                        symbol=symbol,
                        category=category,
                        decimal_places=decimal_places,
                    )
                ),
            )
            result.append(unit)
        return result

    def _seed_material_categories(
        self, organization: Organization, owner: User
    ) -> list[MaterialCategory]:
        result = []
        for code, name in MATERIAL_CATEGORIES:
            category = self._existing_or_create(
                MaterialCategory,
                {"organization": organization, "code": code},
                lambda code=code, name=name: create_material_category(
                    organization=organization,
                    actor=owner,
                    code=code,
                    name=name,
                ),
            )
            result.append(category)
        return result

    def _seed_materials(
        self,
        organization: Organization,
        owner: User,
        units: list[UnitOfMeasure],
        categories: list[MaterialCategory],
    ) -> list[Material]:
        result = []
        for code, name, category_index, unit_index, specifications in MATERIALS:
            material = self._existing_or_create(
                Material,
                {"organization": organization, "code": code},
                lambda code=code, name=name, category_index=category_index, unit_index=unit_index, specifications=specifications: (
                    create_material(
                        organization=organization,
                        actor=owner,
                        code=code,
                        name=name,
                        category=categories[category_index],
                        unit_of_measure=units[unit_index],
                        specifications=specifications,
                    )
                ),
            )
            result.append(material)
        return result

    def _seed_expense_categories(
        self, organization: Organization, owner: User
    ) -> list[ExpenseCategory]:
        names = (
            "خرید مصالح",
            "حمل و لجستیک",
            "ماشین‌آلات و تجهیزات",
            "دستمزد اجرایی",
            "کنترل کیفیت و آزمایشگاه",
        )
        result = []
        for category_index, name in enumerate(names, start=1):
            code = f"demo-{category_index:02d}"
            category = self._existing_or_create(
                ExpenseCategory,
                {"organization": organization, "code": code},
                lambda code=code, name=name: create_expense_category(
                    organization=organization, actor=owner, code=code, name=name
                ),
            )
            result.append(category)
        return result

    def _seed_project(
        self,
        *,
        organization_index: int,
        project_index: int,
        organization: Organization,
        owner: User,
        manager: User,
        parties: list[BusinessParty],
        units: list[UnitOfMeasure],
        materials: list[Material],
        expense_categories: list[ExpenseCategory],
        project_data: tuple[str, str, str, Decimal, str],
    ) -> tuple[Project, ProjectSite]:
        name, description, address, budget, status = project_data
        code = f"PRJ-{organization_index:02d}-{project_index:02d}"
        start = date(2025, 3, 21) + timedelta(days=project_index * 35)
        project = self._existing_or_create(
            Project,
            {"organization": organization, "code": code},
            lambda: create_project(
                organization=organization,
                actor=owner,
                code=code,
                name=name,
                description=description,
                status=status,
                start_date=start,
                end_date=start + timedelta(days=540),
                estimated_budget=budget + Decimal(organization_index * 7_500_000_000),
            ),
        )
        site = self._existing_or_create(
            ProjectSite,
            {"organization": organization, "project": project, "code": "SITE-01"},
            lambda: create_project_site(
                organization=organization,
                project=project,
                actor=owner,
                code="SITE-01",
                name="کارگاه اصلی پروژه",
                address=address,
            ),
        )
        phases = self._seed_phases(organization, owner, site, start)
        wbs_nodes = self._seed_wbs(organization, owner, project)
        activities = self._seed_activities(
            organization, owner, project, site, phases, wbs_nodes, units, start
        )
        contracts = self._seed_contracts(
            organization_index,
            project_index,
            organization,
            owner,
            project,
            parties,
            units,
            wbs_nodes,
            start,
            budget,
        )
        self._seed_estimates(
            organization_index,
            project_index,
            organization,
            owner,
            project,
            phases,
            contracts,
            units,
        )
        self._seed_w54_open_workflow_examples(
            organization_index=organization_index,
            project_index=project_index,
            organization=organization,
            actor=owner,
            contracts=contracts,
        )
        self._seed_treasury_requests(
            organization_index,
            project_index,
            organization,
            owner,
            project,
            phases,
            contracts,
            parties,
            start,
        )
        self._seed_billing(
            organization_index=organization_index,
            project_index=project_index,
            organization=organization,
            owner=owner,
            project=project,
            contract=contracts[0],
            start=start,
        )
        self._seed_expenses(
            organization_index,
            project_index,
            organization,
            owner,
            project,
            phases,
            parties,
            expense_categories,
            start,
        )
        self._seed_documents(
            organization_index,
            project_index,
            organization,
            owner,
            project,
        )
        self._seed_daily_reports(
            organization,
            owner,
            manager,
            project,
            site,
            phases,
            activities,
            materials,
            start,
        )
        self._seed_safety_incident(
            organization_index=organization_index,
            project_index=project_index,
            organization=organization,
            owner=owner,
            manager=manager,
            project=project,
            site=site,
            phase=phases[0],
            activity=activities[0],
            responsible_party=parties[4],
            start=start,
        )
        self._seed_quality_issue(
            organization_index=organization_index,
            project_index=project_index,
            organization=organization,
            owner=owner,
            manager=manager,
            project=project,
            site=site,
            phase=phases[0],
            activity=activities[1],
            responsible_party=parties[4],
            start=start,
        )
        self._seed_procurement_and_inventory(
            organization_index=organization_index,
            project_index=project_index,
            organization=organization,
            owner=owner,
            project=project,
            supplier=parties[2],
            materials=materials,
            start=start,
            warehouse_location=address,
        )
        if project_index == 1:
            self._seed_open_inventory_workflow(
                organization_index=organization_index,
                organization=organization,
                actor=owner,
                project=project,
                material=materials[0],
                start=start,
            )
        self._seed_open_workflow_examples(
            organization_index=organization_index,
            project_index=project_index,
            organization=organization,
            actor=owner,
            project=project,
            site=site,
            phase=phases[0],
            activities=activities,
            materials=materials,
            start=start,
        )
        return project, site

    def _seed_billing(
        self,
        *,
        organization_index: int,
        project_index: int,
        organization: Organization,
        owner: User,
        project: Project,
        contract: Contract,
        start: date,
    ) -> None:
        """Seed measurements; create claims only with existing approved terms."""

        baseline = (
            ProjectBaseline.objects.filter(
                organization=organization,
                project=project,
                contract=contract,
                status="approved",
            )
            .order_by("-version")
            .first()
        )
        if baseline is None:
            baseline = (
                ProjectBaseline.objects.filter(
                    organization=organization,
                    project=project,
                    contract=contract,
                    status="draft",
                )
                .order_by("-version")
                .first()
            )
        if baseline is None:
            baseline = create_project_baseline(
                organization=organization,
                actor=owner,
                project=project,
                contract=contract,
                effective_date=start,
            )
        baseline_item = baseline.items.order_by("sort_order", "line_key").first()
        if baseline_item is None:
            approved_amendments = sum(
                (
                    amendment.value_change
                    for amendment in contract.amendments.filter(status="approved")
                ),
                Decimal("0.00"),
            )
            baseline_item = add_baseline_item(
                organization=organization,
                actor=owner,
                baseline=baseline,
                line_key=f"F6-{project_index:02d}",
                description="نمونه مبنای تجاری صورت‌وضعیت",
                unit="ea",
                planned_quantity=Decimal("1.0000"),
                unit_rate=contract.contract_value + approved_amendments,
                sort_order=1,
            )
        if baseline.status == "draft":
            request_project_baseline_approval(
                organization=organization,
                actor=owner,
                baseline=baseline,
            )
            baseline = approve_project_baseline(
                organization=organization,
                actor=owner,
                baseline=baseline,
                reason="تأیید دادهٔ نمایشی F6",
            )
            baseline_item.refresh_from_db()

        period_start = start
        period_end = start + timedelta(days=30)
        reference = f"DEMO-F6-{organization_index:02d}-{project_index:02d}"
        record = ProgressRecord.objects.filter(
            organization=organization,
            baseline_item=baseline_item,
            source_type="demo",
            source_reference=reference,
        ).first()
        if record is None:
            record = create_progress_record(
                organization=organization,
                actor=owner,
                baseline=baseline,
                baseline_item=baseline_item,
                period_start=period_start,
                period_end=period_end,
                measured_on=start + timedelta(days=14),
                source_type="demo",
                source_reference=reference,
                period_quantity=Decimal("0.3500"),
                cumulative_quantity=Decimal("0.3500"),
                evidence="اندازه‌گیری نمونه برای نمایش جریان F6",
            )
        if record.status == "draft":
            request_progress_verification(
                organization=organization,
                actor=owner,
                record=record,
            )
            record.refresh_from_db()
        if record.status == "submitted":
            record = verify_progress_record(
                organization=organization,
                actor=owner,
                record=record,
                reason="راستی‌آزمایی دادهٔ نمایشی F6",
            )

        # Demo generation is not authority to invent or approve commercial
        # terms. Keep measurements available and Treasury requests pending when
        # this tenant has no approved terms at the measurement cutoff. All other
        # claim prerequisites remain enforced by the normal Billing services.
        if not contract.term_versions.filter(
            organization=organization,
            status__in=("approved", "superseded"),
            effective_from__lte=period_end,
        ).exists():
            self.stdout.write(
                "Demo claim omitted: approved commercial terms are required; "
                "no AR or cash history was fabricated."
            )
            return

        claim = ProgressClaim.objects.filter(
            organization=organization,
            contract=contract,
            baseline=baseline,
            period_start=period_start,
            period_end=period_end,
            revision_number=1,
        ).first()
        if claim is None:
            claim = create_progress_claim(
                organization=organization,
                actor=owner,
                baseline=baseline,
                period_start=period_start,
                period_end=period_end,
                measurement_cutoff=period_end,
            )
        if claim.status == "draft":
            submit_progress_claim(
                organization=organization,
                actor=owner,
                claim=claim,
            )
            claim.refresh_from_db()
        if claim.status == "submitted":
            claim = approve_progress_claim(
                organization=organization,
                actor=owner,
                claim=claim,
                reason="تأیید دادهٔ نمایشی F6",
            )

        # No synthetic receipt or settlement. Explicit AR recognition and posted
        # Treasury receipts require the tenant's approved financial configuration.

    def _seed_open_inventory_workflow(
        self,
        *,
        organization_index: int,
        organization: Organization,
        actor: User,
        project: Project,
        material: Material,
        start: date,
    ) -> None:
        """Keep one explicit, actionable W5.6 posting example per tenant."""

        transaction_number = f"STK-{organization_index:02d}-WF"
        stock_transaction = StockTransaction.objects.filter(
            organization=organization,
            transaction_number=transaction_number,
        ).first()
        if stock_transaction is None:
            warehouse = Warehouse.objects.get(
                organization=organization, project=project
            )
            stock_transaction = create_stock_transaction(
                organization=organization,
                actor=actor,
                transaction_number=transaction_number,
                transaction_type="adjustment_in",
                material=material,
                unit_of_measure=material.unit_of_measure,
                quantity=Decimal(10),
                occurred_at=timezone.make_aware(
                    datetime.combine(start + timedelta(days=35), datetime.min.time())
                ),
                destination_warehouse=warehouse,
                project=project,
                notes="نمونه باز درخواست تأیید ورود اصلاحی انبار.",
            )
        if stock_transaction.status == StockTransactionStatus.DRAFT:
            request_stock_transaction_posting(
                organization=organization,
                actor=actor,
                stock_transaction=stock_transaction,
            )

    def _seed_open_workflow_examples(
        self,
        *,
        organization_index: int,
        project_index: int,
        organization: Organization,
        actor: User,
        project: Project,
        site: ProjectSite,
        phase: ProjectPhase,
        activities: list[Activity],
        materials: list[Material],
        start: date,
    ) -> None:
        """Create deterministic actionable examples for the central workbench."""

        request_number = f"PRQ-{organization_index:02d}-{project_index:02d}-WF"
        purchase_request = PurchaseRequest.objects.filter(
            organization=organization,
            request_number=request_number,
        ).first()
        if purchase_request is None:
            purchase_request = create_purchase_request(
                organization=organization,
                actor=actor,
                project=project,
                request_number=request_number,
                title="درخواست خرید در انتظار بررسی کارتابل",
                required_by=start + timedelta(days=75),
                notes="نمونه باز برای نمایش گردش تأیید درخواست خرید در کارتابل متمرکز.",
            )
        if (
            purchase_request.status == PurchaseRequestStatus.DRAFT
            and not purchase_request.items.exists()
        ):
            material = materials[(project_index - 1) % len(materials)]
            add_purchase_request_item(
                organization=organization,
                actor=actor,
                purchase_request=purchase_request,
                material=material,
                unit_of_measure=material.unit_of_measure,
                quantity=Decimal(25 + project_index * 5),
                description=f"تأمین {material.name} برای نمونه گردش‌کار باز",
                sort_order=1,
            )
        if purchase_request.status == PurchaseRequestStatus.DRAFT:
            submit_purchase_request(
                organization=organization,
                actor=actor,
                purchase_request=purchase_request,
            )

        reporting_date = start + timedelta(days=30 + project_index)
        report = DailyReport.objects.filter(
            organization=organization,
            site=site,
            reporting_date=reporting_date,
        ).first()
        if report is None:
            report = create_daily_report(
                organization=organization,
                project=project,
                site=site,
                phase=phase,
                actor=actor,
                reporting_date=reporting_date,
                work_performed="عملیات اجرایی روزانه برای نمونه گردش تأیید ثبت شد.",
                weather_conditions="صاف",
                labor_count=12 + project_index,
                progress_summary="نمونه باز برای نمایش تأیید گزارش روزانه در کارتابل متمرکز.",
                safety_notes="کنترل‌های ایمنی ابتدای شیفت انجام شد.",
                quality_notes="کنترل کیفیت عملیات اجراشده ثبت شد.",
            )
        if report.status == DailyReportStatus.DRAFT:
            self._seed_report_entries(
                organization,
                actor,
                report,
                project_index,
                activities,
                materials,
                ("بیل مکانیکی", "جرثقیل برجی", "پمپ بتن", "بالابر کارگاهی"),
                (
                    "گروه اجرایی یک",
                    "گروه اجرایی دو",
                    "گروه اجرایی سه",
                    "گروه اجرایی چهار",
                ),
            )
            submit_daily_report(
                organization=organization,
                report_id=str(report.pk),
                actor=actor,
            )

    def _seed_safety_incident(
        self,
        *,
        organization_index: int,
        project_index: int,
        organization: Organization,
        owner: User,
        manager: User,
        project: Project,
        site: ProjectSite,
        phase: ProjectPhase,
        activity: Activity,
        responsible_party: BusinessParty,
        start: date,
    ) -> None:
        incident_number = f"SAF-{organization_index:02d}-{project_index:02d}-01"
        if SafetyIncident.objects.filter(
            organization=organization, incident_number=incident_number
        ).exists():
            return
        daily_report = (
            DailyReport.objects.filter(
                organization=organization,
                project=project,
                site=site,
            )
            .order_by("reporting_date")
            .first()
        )
        incident_types = (
            SafetyIncidentType.NEAR_MISS,
            SafetyIncidentType.INJURY,
            SafetyIncidentType.PROPERTY_DAMAGE,
            SafetyIncidentType.UNSAFE_CONDITION,
        )
        severities = (
            SafetyIncidentSeverity.HIGH,
            SafetyIncidentSeverity.MEDIUM,
            SafetyIncidentSeverity.CRITICAL,
            SafetyIncidentSeverity.LOW,
        )
        occurred_at = timezone.make_aware(
            datetime.combine(start + timedelta(days=3), datetime.min.time())
        )
        incident = create_safety_incident(
            organization=organization,
            actor=manager,
            project=project,
            site=site,
            phase=phase,
            activity=activity,
            daily_report=daily_report,
            incident_number=incident_number,
            occurred_at=occurred_at,
            incident_type=incident_types[(project_index - 1) % len(incident_types)],
            severity=severities[(project_index - 1) % len(severities)],
            description="در جریان عملیات اجرایی، یک رویداد ایمنی در محدوده کارگاه ثبت و محل برای بررسی ایمن‌سازی شد.",
            immediate_action="عملیات متوقف، محدوده محصور و جلسه توجیهی فوری برای گروه اجرایی برگزار شد.",
        )
        incident = review_safety_incident(
            organization=organization,
            actor=owner,
            incident_id=str(incident.pk),
        )
        if project_index == 4:
            return
        incident = assign_safety_incident(
            organization=organization,
            actor=owner,
            incident_id=str(incident.pk),
            due_date=start + timedelta(days=12),
            responsible_user=manager,
            responsible_party=responsible_party,
        )
        if project_index == 3:
            return
        incident = start_corrective_action(
            organization=organization,
            actor=manager,
            incident_id=str(incident.pk),
            corrective_action="حفاظ فیزیکی نصب، مسیر تردد اصلاح و کنترل روزانه توسط مدیر کارگاه ثبت شود.",
        )
        if project_index == 2:
            return
        incident = resolve_safety_incident(
            organization=organization,
            actor=manager,
            incident_id=str(incident.pk),
            resolution_summary="اقدامات اصلاحی اجرا و اثربخشی آن در بازدید مشترک کارگاه تأیید شد.",
        )
        # Human-approved demo closure uses the source-owned record review API.
        # Keep the normal permission checks, revisions and closure prerequisite.
        submit_safety_record(
            organization=organization,
            actor=manager,
            incident_id=str(incident.pk),
            reason="Demo record submitted for separate Safety approval.",
        )
        decide_safety_record(
            organization=organization,
            actor=owner,
            incident_id=str(incident.pk),
            outcome=SafetyReviewStatus.APPROVED,
            reason="Demo Safety closure authorized by Human decision 2026-10-20.",
        )
        close_safety_incident(
            organization=organization,
            actor=owner,
            incident_id=str(incident.pk),
            closure_summary="مدارک اقدام بررسی شد و حادثه پس از تأیید کنترل‌های پایدار بسته شد.",
        )

    def _seed_quality_issue(
        self,
        *,
        organization_index: int,
        project_index: int,
        organization: Organization,
        owner: User,
        manager: User,
        project: Project,
        site: ProjectSite,
        phase: ProjectPhase,
        activity: Activity,
        responsible_party: BusinessParty,
        start: date,
    ) -> None:
        issue_number = f"QLT-{organization_index:02d}-{project_index:02d}-01"
        if QualityIssue.objects.filter(
            organization=organization, issue_number=issue_number
        ).exists():
            return
        daily_report = (
            DailyReport.objects.filter(
                organization=organization,
                project=project,
                site=site,
            )
            .order_by("reporting_date")
            .first()
        )
        issue_types = (
            QualityIssueType.NONCONFORMANCE,
            QualityIssueType.WORKMANSHIP,
            QualityIssueType.MATERIAL,
            QualityIssueType.INSPECTION,
        )
        severities = (
            QualityIssueSeverity.MAJOR,
            QualityIssueSeverity.MINOR,
            QualityIssueSeverity.CRITICAL,
            QualityIssueSeverity.MAJOR,
        )
        identified_at = timezone.make_aware(
            datetime.combine(start + timedelta(days=10), datetime.min.time())
        )
        issue = create_quality_issue(
            organization=organization,
            actor=manager,
            project=project,
            site=site,
            phase=phase,
            activity=activity,
            daily_report=daily_report,
            issue_number=issue_number,
            identified_at=identified_at,
            issue_type=issue_types[(project_index - 1) % len(issue_types)],
            severity=severities[(project_index - 1) % len(severities)],
            description=(
                "در بازرسی اجرایی، عدم انطباقی در کیفیت سطح، ابعاد یا مصالح مصرفی "
                "شناسایی و برای پیگیری رسمی ثبت شد."
            ),
            specification_reference="مشخصات فنی عمومی پیمان و نقشه اجرایی مصوب پروژه",
        )
        issue = review_quality_issue(
            organization=organization,
            actor=owner,
            issue_id=str(issue.pk),
        )
        issue = assign_quality_issue(
            organization=organization,
            actor=owner,
            issue_id=str(issue.pk),
            due_date=start + timedelta(days=24),
            responsible_user=manager,
            responsible_party=responsible_party,
        )
        if project_index == 4:
            return
        issue = start_quality_corrective_action(
            organization=organization,
            actor=manager,
            issue_id=str(issue.pk),
            corrective_action=(
                "بخش نامنطبق اصلاح، مصالح و روش اجرا بازبینی و نتیجه کنترل مجدد ثبت شود."
            ),
        )
        issue = submit_quality_issue_for_verification(
            organization=organization,
            actor=manager,
            issue_id=str(issue.pk),
            corrective_action_result=(
                "اصلاح مطابق روش اجرایی مصوب انجام و کنترل داخلی پیمانکار تکمیل شد."
            ),
        )
        if project_index == 3:
            return
        issue = verify_quality_issue(
            organization=organization,
            actor=owner,
            issue_id=str(issue.pk),
            verification_summary=(
                "بازرسی مجدد انجام شد و نتیجه اصلاح با مشخصات فنی و نقشه مصوب تطابق دارد."
            ),
        )
        if project_index == 2:
            return
        # Source-owned record review is distinct from corrective verification.
        # Existing services retain the approved snapshot, actor, reason and audit.
        submit_quality_record(
            organization=organization,
            actor=manager,
            issue_id=str(issue.pk),
            reason="Development demo Quality record submitted for review.",
        )
        decide_quality_record(
            organization=organization,
            actor=owner,
            issue_id=str(issue.pk),
            outcome="approved",
            reason="Development demo Quality record and specification reviewed.",
        )
        close_quality_issue(
            organization=organization,
            actor=owner,
            issue_id=str(issue.pk),
            closure_summary=(
                "شواهد اصلاح و راستی‌آزمایی بررسی شد و مسئله کیفیت بسته شد."
            ),
        )

    def _seed_phases(
        self,
        organization: Organization,
        owner: User,
        site: ProjectSite,
        start: date,
    ) -> list[ProjectPhase]:
        phase_data = (
            ("PH-01", "عملیات زیرسازی و سازه", "active"),
            ("PH-02", "نازک‌کاری و تأسیسات", "planning"),
        )
        result = []
        for phase_index, (code, name, status) in enumerate(phase_data):
            phase_start = start + timedelta(days=phase_index * 210)
            phase = self._existing_or_create(
                ProjectPhase,
                {"organization": organization, "site": site, "code": code},
                lambda code=code, name=name, status=status, phase_start=phase_start: (
                    create_project_phase(
                        organization=organization,
                        site=site,
                        actor=owner,
                        code=code,
                        name=name,
                        status=status,
                        planned_start_date=phase_start,
                        planned_end_date=phase_start + timedelta(days=240),
                    )
                ),
            )
            result.append(phase)
        return result

    def _seed_wbs(
        self, organization: Organization, owner: User, project: Project
    ) -> list[WBSNode]:
        data = (
            ("01", "عملیات تجهیز و آماده‌سازی", None),
            ("02", "عملیات سازه و معماری", None),
            ("02-01", "اجرای فونداسیون و اسکلت", 1),
        )
        result: list[WBSNode] = []
        for sort_order, (code, title, parent_index) in enumerate(data, start=1):
            parent = result[parent_index] if parent_index is not None else None
            node = self._existing_or_create(
                WBSNode,
                {"project": project, "code": code},
                lambda code=code, title=title, parent=parent, sort_order=sort_order: (
                    create_wbs_node(
                        organization=organization,
                        project=project,
                        actor=owner,
                        code=code,
                        title=title,
                        parent=parent,
                        sort_order=sort_order,
                    )
                ),
            )
            result.append(node)
        return result

    def _seed_activities(
        self,
        organization: Organization,
        owner: User,
        project: Project,
        site: ProjectSite,
        phases: list[ProjectPhase],
        wbs_nodes: list[WBSNode],
        units: list[UnitOfMeasure],
        start: date,
    ) -> list[Activity]:
        data = (
            ("ACT-01", "تجهیز و حصارکشی کارگاه", 0, 4, Decimal(1)),
            ("ACT-02", "خاک‌برداری و آماده‌سازی بستر", 1, 2, Decimal(2200)),
            ("ACT-03", "آرماتوربندی و بتن‌ریزی فونداسیون", 2, 2, Decimal(780)),
            ("ACT-04", "اجرای اسکلت و سقف طبقات", 2, 1, Decimal(6400)),
        )
        result = []
        for activity_index, (code, name, wbs_index, unit_index, quantity) in enumerate(
            data
        ):
            activity_start = start + timedelta(days=activity_index * 35)
            activity = self._existing_or_create(
                Activity,
                {"project": project, "code": code},
                lambda code=code, name=name, wbs_index=wbs_index, unit_index=unit_index, quantity=quantity, activity_index=activity_index, activity_start=activity_start: (
                    create_activity(
                        organization=organization,
                        project=project,
                        wbs_node=wbs_nodes[wbs_index],
                        actor=owner,
                        code=code,
                        name=name,
                        site=site,
                        phase=phases[0],
                        unit_of_measure=units[unit_index],
                        planned_quantity=quantity,
                        planned_start_date=activity_start,
                        planned_end_date=activity_start + timedelta(days=75),
                        status="active" if activity_index < 3 else "planning",
                    )
                ),
            )
            result.append(activity)
        return result

    def _seed_contracts(
        self,
        organization_index: int,
        project_index: int,
        organization: Organization,
        owner: User,
        project: Project,
        parties: list[BusinessParty],
        units: list[UnitOfMeasure],
        wbs_nodes: list[WBSNode],
        start: date,
        budget: Decimal,
    ) -> list[Contract]:
        result = []
        target_statuses = ("active", "active", "draft", "completed", "active")
        for contract_index, (title, party_index, direction, contract_type) in enumerate(
            CONTRACT_SUBJECTS, start=1
        ):
            number = (
                f"CTR-{organization_index:02d}-{project_index:02d}-{contract_index:02d}"
            )
            party = parties[party_index]
            value = (
                budget * Decimal("0.62" if contract_index == 1 else "0.08")
            ) + Decimal(contract_index * 900_000_000)
            contract = Contract.objects.filter(
                organization=organization, contract_number=number
            ).first()
            if contract is None:
                contract = create_contract(
                    organization=organization,
                    project=project,
                    actor=owner,
                    contract_number=number,
                    title=title,
                    counterparty_name=party.display_name,
                    party=party,
                    direction=direction,
                    contract_type=contract_type,
                    contract_value=value,
                    signed_at=start - timedelta(days=12 - contract_index),
                    start_date=start,
                    end_date=start + timedelta(days=420),
                    notes="شرایط پرداخت مرحله‌ای و کنترل کیفیت مطابق اسناد پیمان است.",
                )
            for item_index, item_description in enumerate(
                ("عملیات اجرایی و تأمین نیروی متخصص", "تأمین مصالح و تجهیزات مرتبط"),
                start=1,
            ):
                if not ContractItem.objects.filter(
                    contract=contract, sort_order=item_index
                ).exists():
                    add_contract_item(
                        organization=organization,
                        actor=owner,
                        contract=contract,
                        description=item_description,
                        quantity=Decimal("1.0000"),
                        unit_price=(
                            value * Decimal("0.55" if item_index == 1 else "0.45")
                        ).quantize(Decimal("0.01")),
                        unit=units[4].symbol,
                        unit_of_measure=units[4],
                        wbs_node=wbs_nodes[min(item_index, 2)],
                        sort_order=item_index,
                    )
            target_status = target_statuses[contract_index - 1]
            if contract.status == "draft" and target_status != "draft":
                contract = transition_contract_status(
                    organization=organization,
                    actor=owner,
                    contract=contract,
                    status="active",
                )
                if target_status == "completed":
                    contract = transition_contract_status(
                        organization=organization,
                        actor=owner,
                        contract=contract,
                        status="completed",
                    )
            result.append(contract)

        amendment = ContractAmendment.objects.filter(
            contract=result[0], amendment_number=1
        ).first()
        if amendment is None:
            amendment = ContractAmendment.objects.create(
                organization=organization,
                contract=result[0],
                amendment_number=1,
                title="الحاقیه تعدیل برنامه تأمین مصالح",
                reason="هماهنگی زمان تحویل مصالح با برنامه به‌روزشده اجرای پروژه",
                value_change=Decimal(1750000000),
                created_by=owner,
            )
            approve_contract_amendment(
                organization=organization, actor=owner, amendment=amendment
            )
        return result

    def _seed_estimates(
        self,
        organization_index: int,
        project_index: int,
        organization: Organization,
        owner: User,
        project: Project,
        phases: list[ProjectPhase],
        contracts: list[Contract],
        units: list[UnitOfMeasure],
    ) -> None:
        titles = ("برآورد عملیات سازه و فونداسیون", "برآورد نازک‌کاری و تأسیسات")
        for estimate_index, title in enumerate(titles, start=1):
            number = (
                f"EST-{organization_index:02d}-{project_index:02d}-{estimate_index:02d}"
            )
            estimate = Estimate.objects.filter(
                organization=organization, estimate_number=number
            ).first()
            if estimate is None:
                estimate = create_estimate(
                    organization=organization,
                    project=project,
                    actor=owner,
                    estimate_number=number,
                    title=title,
                    contract=contracts[0],
                    phase=phases[estimate_index - 1],
                    notes="مقادیر بر پایه آخرین نقشه‌های اجرایی و استعلام‌های معتبر تنظیم شده است.",
                )
            estimate_items = (
                ("تأمین و اجرای بتن سازه‌ای", Decimal(540), units[2], Decimal(9800000)),
                ("تهیه و نصب فولاد تقویتی", Decimal(72000), units[3], Decimal(940000)),
                (
                    "خدمات اجرایی و کنترل کیفی",
                    Decimal(1),
                    units[4],
                    Decimal(2600000000),
                ),
            )
            for sort_order, (description, quantity, unit, price) in enumerate(
                estimate_items, start=1
            ):
                if not EstimateItem.objects.filter(
                    estimate=estimate,
                    revision=estimate.current_revision,
                    sort_order=sort_order,
                ).exists():
                    add_estimate_item(
                        estimate=estimate,
                        actor=owner,
                        description=description,
                        quantity=quantity,
                        unit_price=price,
                        unit=unit.symbol,
                        unit_of_measure=unit,
                        sort_order=sort_order,
                    )
            if estimate_index == 1 and estimate.status == "draft":
                approve_estimate(estimate=estimate, actor=owner)

    def _seed_w54_open_workflow_examples(
        self,
        *,
        organization_index: int,
        project_index: int,
        organization: Organization,
        actor: User,
        contracts: list[Contract],
    ) -> None:
        """Create one explicit, pending W5.4 item for each approval flow."""
        estimate_number = f"EST-{organization_index:02d}-{project_index:02d}-02"
        estimate = (
            Estimate.objects.filter(
                organization=organization,
                estimate_number=estimate_number,
                status="draft",
            )
            .select_related("current_revision")
            .first()
        )
        if estimate and estimate.current_revision_id:
            request_estimate_approval(estimate=estimate, actor=actor)

        amendment = ContractAmendment.objects.filter(
            organization=organization,
            contract=contracts[0],
            amendment_number=2,
        ).first()
        if amendment is None:
            amendment = ContractAmendment.objects.create(
                organization=organization,
                contract=contracts[0],
                amendment_number=2,
                title="الحاقیه باز برای کارتابل تأیید",
                reason="نمونه صریحِ در انتظار تأیید برای نمایش در کارتابل متمرکز.",
                value_change=Decimal(250000000),
                created_by=actor,
            )
        if amendment.status == "draft":
            request_contract_amendment_approval(
                organization=organization,
                actor=actor,
                amendment=amendment,
            )

    def _seed_treasury_requests(
        self,
        organization_index,
        project_index,
        organization,
        owner,
        project,
        phases,
        contracts,
        parties,
        start,
    ) -> None:
        """Create pending Treasury requests without inventing GL/cash history."""
        for index in range(2, 6):
            create_payment_request(
                organization=organization,
                actor=owner,
                kind="payment",
                amount=Decimal(2_200_000_000 + index * 475_000_000),
                purpose=f"Demo pending payment {organization_index}-{project_index}-{index}",
                idempotency_key=f"DEMO-TR-{organization_index}-{project_index}-{index}",
                project=project,
                party=parties[min(index, 5)],
            )

    def _seed_expenses(
        self,
        organization_index: int,
        project_index: int,
        organization: Organization,
        owner: User,
        project: Project,
        phases: list[ProjectPhase],
        parties: list[BusinessParty],
        expense_categories: list[ExpenseCategory],
        start: date,
    ) -> None:
        for expense_index, (description, legacy_category, category_index) in enumerate(
            EXPENSES, start=1
        ):
            reference = (
                f"EXP-{organization_index:02d}-{project_index:02d}-{expense_index:02d}"
            )
            if Expense.objects.filter(
                organization=organization, receipt_reference=reference
            ).exists():
                continue
            party = parties[min(expense_index + 1, len(parties) - 1)]
            create_expense(
                organization=organization,
                project=project,
                actor=owner,
                description=description,
                amount=Decimal(85_000_000 + expense_index * 47_500_000),
                incurred_on=start + timedelta(days=expense_index * 11),
                phase=phases[0],
                category=legacy_category,
                vendor_name=party.display_name,
                party=party,
                expense_category=expense_categories[category_index],
                receipt_reference=reference,
                notes="اسناد هزینه بررسی شده و به دوره مالی پروژه تخصیص یافته است.",
            )

    def _seed_documents(
        self,
        organization_index: int,
        project_index: int,
        organization: Organization,
        owner: User,
        project: Project,
    ) -> None:
        titles = ("صورت‌جلسه هماهنگی اجرایی", "گزارش کنترل کیفیت مصالح")
        for document_index, title in enumerate(titles, start=1):
            file_name = f"DOC-{organization_index:02d}-{project_index:02d}-{document_index:02d}.pdf"
            reference = file_name.removesuffix(".pdf")
            if Document.objects.filter(
                organization=organization,
                reference=reference,
            ).exists():
                continue
            upload = SimpleUploadedFile(
                file_name,
                b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n",
                content_type="application/pdf",
            )
            create_document(
                organization=organization,
                actor=owner,
                document_type="general" if document_index == 1 else "other",
                title=title,
                reference=reference,
                description="سند نمونه نسخه‌بندی‌شده و خصوصی پروژه.",
                upload=upload,
                target=project,
            )

    def _seed_daily_reports(
        self,
        organization: Organization,
        owner: User,
        manager: User,
        project: Project,
        site: ProjectSite,
        phases: list[ProjectPhase],
        activities: list[Activity],
        materials: list[Material],
        start: date,
    ) -> None:
        weather = ("آفتابی", "نیمه‌ابری", "صاف و خنک", "ابری با باد ملایم")
        equipment = ("بیل مکانیکی", "جرثقیل برجی", "پمپ بتن", "بالابر کارگاهی")
        teams = ("گروه آرماتوربندی", "گروه قالب‌بندی", "گروه تأسیسات", "گروه بنایی")
        for report_index, work_performed in enumerate(REPORT_WORK, start=1):
            reporting_date = start + timedelta(days=report_index * 3)
            report = DailyReport.objects.filter(
                organization=organization,
                site=site,
                reporting_date=reporting_date,
            ).first()
            if report is None:
                report = create_daily_report(
                    organization=organization,
                    project=project,
                    site=site,
                    actor=manager,
                    reporting_date=reporting_date,
                    phase=phases[0],
                    work_performed=work_performed,
                    weather_conditions=weather[(report_index - 1) % len(weather)],
                    labor_count=18 + report_index,
                    progress_summary=f"پیشرفت روزانه بخش اجرایی شماره {report_index} مطابق برنامه ثبت شد.",
                    issues_and_delays="هماهنگی ورود مصالح و دسترسی ماشین‌آلات پیگیری شد.",
                    safety_notes="جلسه ایمنی آغاز شیفت برگزار و تجهیزات حفاظت فردی کنترل شد.",
                    quality_notes="ابعاد، تراز و کیفیت مصالح مصرفی توسط ناظر کارگاه بررسی شد.",
                )
            if report.status == "draft":
                self._seed_report_entries(
                    organization,
                    manager,
                    report,
                    report_index,
                    activities,
                    materials,
                    equipment,
                    teams,
                )
                if report_index <= 5:
                    report = submit_daily_report(
                        organization=organization,
                        report_id=str(report.pk),
                        actor=manager,
                    )
                if report_index <= 3:
                    approve_daily_report(
                        organization=organization,
                        report_id=str(report.pk),
                        actor=owner,
                    )

    def _seed_report_entries(
        self,
        organization: Organization,
        manager: User,
        report: DailyReport,
        report_index: int,
        activities: list[Activity],
        materials: list[Material],
        equipment: tuple[str, ...],
        teams: tuple[str, ...],
    ) -> None:
        activity = activities[(report_index - 1) % len(activities)]
        material = materials[(report_index - 1) % len(materials)]
        if not report.labor_entries.exists():
            add_daily_report_labor_entry(
                organization=organization,
                report_id=str(report.pk),
                actor=manager,
                team_name=teams[(report_index - 1) % len(teams)],
                worker_count=8 + report_index,
                hours_worked=Decimal(56 + report_index * 4),
                notes="حضور گروه اجرایی و ساعات کارکرد در دفتر کارگاه ثبت شد.",
            )
        if not report.equipment_entries.exists():
            add_daily_report_equipment_entry(
                organization=organization,
                report_id=str(report.pk),
                actor=manager,
                equipment_name=equipment[(report_index - 1) % len(equipment)],
                hours_used=Decimal("6.50") + Decimal(report_index) / 10,
                notes="بازرسی پیش از کار انجام شد و تجهیز در وضعیت عملیاتی قرار داشت.",
            )
        if not report.material_entries.exists():
            add_daily_report_material_entry(
                organization=organization,
                report_id=str(report.pk),
                actor=manager,
                material_name=material.name,
                material=material,
                quantity=Decimal(20 + report_index * 7),
                unit=material.unit_of_measure.symbol,
                notes="مقدار مصرف پس از کنترل حواله انبار ثبت شد.",
            )
        if not report.daily_activities.exists():
            add_daily_activity(
                organization=organization,
                report_id=str(report.pk),
                actor=manager,
                description=activity.name,
                activity=activity,
                quantity=Decimal(12 + report_index * 3),
                unit_of_measure=activity.unit_of_measure,
                progress_percent=Decimal(min(100, report_index * 9)),
                notes="مقدار اجرا توسط سرپرست کارگاه اندازه‌گیری و تأیید شد.",
            )
        if not report.delay_events.exists():
            add_delay_event(
                organization=organization,
                report_id=str(report.pk),
                actor=manager,
                occurred_on=report.reporting_date,
                activity=activity,
                category="تدارکات و هماهنگی",
                cause="ورود محموله مصالح با فاصله کوتاه از برنامه روزانه انجام شد.",
                impact="ترتیب اجرای دو جبهه کاری برای حفظ بهره‌وری اصلاح شد.",
                responsible_party="واحد تدارکات پروژه",
                duration_hours=Decimal("0.75") + Decimal(report_index) / 10,
            )

    def _seed_workforce(
        self,
        *,
        organization: Organization,
        owner: User,
        manager: User,
        project: Project,
        site: ProjectSite,
    ) -> None:
        technical = self._existing_or_create(
            Department,
            {"organization": organization, "code": "TEC"},
            lambda: create_department(
                organization=organization,
                actor=owner,
                code="TEC",
                name="دفتر فنی و مهندسی",
                description="کنترل نقشه‌ها، برنامه‌ریزی و هماهنگی فنی پروژه‌ها",
            ),
        )
        execution = self._existing_or_create(
            Department,
            {"organization": organization, "code": "EXE"},
            lambda: create_department(
                organization=organization,
                actor=owner,
                code="EXE",
                name="مدیریت اجرا",
                description="مدیریت عملیات اجرایی و گروه‌های کارگاهی",
            ),
        )
        site_manager = self._existing_or_create(
            Position,
            {"organization": organization, "code": "SITE-MGR"},
            lambda: create_position(
                organization=organization,
                actor=owner,
                code="SITE-MGR",
                title="مدیر کارگاه",
                department=execution,
                description="مسئول برنامه‌ریزی و هماهنگی عملیات روزانه کارگاه",
            ),
        )
        technical_manager = self._existing_or_create(
            Position,
            {"organization": organization, "code": "TECH-MGR"},
            lambda: create_position(
                organization=organization,
                actor=owner,
                code="TECH-MGR",
                title="مدیر دفتر فنی",
                department=technical,
                description="مسئول کنترل فنی، متره و هماهنگی نقشه‌های اجرایی",
            ),
        )
        owner_employee = self._existing_or_create(
            Employee,
            {"organization": organization, "employee_number": "EMP-001"},
            lambda: create_employee(
                organization=organization,
                actor=owner,
                employee_number="EMP-001",
                first_name=owner.first_name,
                last_name=owner.last_name,
                user=owner,
                department=execution,
                position=site_manager,
                phone_number="۰۹۱۲۱۲۳۴۵۶۷",
                hire_date=date(2021, 3, 21),
            ),
        )
        execution_team = self._existing_or_create(
            WorkTeam,
            {"organization": organization, "code": "CIVIL"},
            lambda: create_work_team(
                organization=organization,
                actor=owner,
                code="CIVIL",
                name="گروه اجرای سازه",
                department=execution,
                lead=owner_employee,
                description="گروه اجرایی عملیات سازه و ابنیه پروژه",
            ),
        )
        manager_employee = self._existing_or_create(
            Employee,
            {"organization": organization, "employee_number": "EMP-002"},
            lambda: create_employee(
                organization=organization,
                actor=owner,
                employee_number="EMP-002",
                first_name="مریم",
                last_name="کاظمی",
                department=technical,
                position=technical_manager,
                work_team=execution_team,
                phone_number="۰۹۱۲۲۳۴۵۶۷۸",
                hire_date=date(2022, 6, 22),
            ),
        )
        for employee, role_title in (
            (owner_employee, "مدیر کارگاه"),
            (manager_employee, "مسئول دفتر فنی"),
        ):
            if not EmployeeProjectAssignment.objects.filter(
                organization=organization,
                employee=employee,
                project=project,
                site=site,
            ).exists():
                assign_employee_to_project(
                    organization=organization,
                    actor=owner,
                    employee=employee,
                    project=project,
                    site=site,
                    start_date=project.start_date,
                    role_title=role_title,
                    notes="تخصیص فعال نیروی انسانی به کارگاه اصلی پروژه",
                )

    def _seed_procurement_and_inventory(
        self,
        *,
        organization_index: int,
        project_index: int,
        organization: Organization,
        owner: User,
        project: Project,
        supplier: BusinessParty,
        materials: list[Material],
        start: date,
        warehouse_location: str,
    ) -> None:
        warehouse = self._existing_or_create(
            Warehouse,
            {
                "organization": organization,
                "code": f"WH-{project_index:02d}",
            },
            lambda: create_warehouse(
                organization=organization,
                actor=owner,
                code=f"WH-{project_index:02d}",
                name=f"انبار کارگاه پروژه {project.name}",
                project=project,
                location=warehouse_location,
            ),
        )
        request_number = f"PRQ-{organization_index:02d}-{project_index:02d}-01"
        if PurchaseRequest.objects.filter(
            organization=organization,
            request_number=request_number,
        ).exists():
            return

        purchase_request = create_purchase_request(
            organization=organization,
            actor=owner,
            project=project,
            request_number=request_number,
            title="درخواست تأمین مصالح مرحله نخست اجرا",
            required_by=start + timedelta(days=45),
            notes="اقلام بر پایه برنامه اجرایی و موجودی کارگاه درخواست شده‌اند.",
        )
        requested_items = []
        for sort_order, (material, quantity) in enumerate(
            ((materials[0], Decimal(120)), (materials[2], Decimal(8500))),
            start=1,
        ):
            requested_items.append(
                add_purchase_request_item(
                    organization=organization,
                    actor=owner,
                    purchase_request=purchase_request,
                    material=material,
                    unit_of_measure=material.unit_of_measure,
                    quantity=quantity,
                    description=f"تأمین {material.name} مورد نیاز جبهه اجرایی",
                    sort_order=sort_order,
                )
            )
        purchase_request = submit_purchase_request(
            organization=organization,
            actor=owner,
            purchase_request=purchase_request,
        )
        purchase_request = approve_purchase_request(
            organization=organization,
            actor=owner,
            purchase_request=purchase_request,
            reason="نیاز پروژه و اعتبار بودجه بررسی و تأیید شد.",
        )

        purchase_order = create_purchase_order(
            organization=organization,
            actor=owner,
            project=project,
            supplier=supplier,
            order_number=f"POR-{organization_index:02d}-{project_index:02d}-01",
            order_date=start + timedelta(days=10),
            purchase_request=purchase_request,
            expected_delivery_date=start + timedelta(days=35),
            notes="تحویل در انبار کارگاه و ارائه گواهی کیفیت الزامی است.",
        )
        order_items = []
        prices = (Decimal(9800000), Decimal(940000))
        for sort_order, (request_item, unit_price) in enumerate(
            zip(requested_items, prices, strict=True),
            start=1,
        ):
            order_items.append(
                add_purchase_order_item(
                    organization=organization,
                    actor=owner,
                    purchase_order=purchase_order,
                    purchase_request_item=request_item,
                    material=request_item.material,
                    unit_of_measure=request_item.unit_of_measure,
                    quantity=request_item.quantity,
                    unit_price=unit_price,
                    description=f"خرید {request_item.material.name} مطابق مشخصات فنی",
                    sort_order=sort_order,
                )
            )
        purchase_order = issue_purchase_order(
            organization=organization,
            actor=owner,
            purchase_order=purchase_order,
        )

        received_at = timezone.make_aware(
            datetime.combine(start + timedelta(days=32), datetime.min.time())
        )
        goods_receipt = create_goods_receipt(
            organization=organization,
            actor=owner,
            purchase_order=purchase_order,
            receipt_number=f"GRC-{organization_index:02d}-{project_index:02d}-01",
            received_at=received_at,
            notes="مقدار و کیفیت اقلام تحویلی در محل انبار کنترل شد.",
        )
        receipt_items = []
        for order_item in order_items:
            receipt_items.append(
                add_goods_receipt_item(
                    organization=organization,
                    actor=owner,
                    goods_receipt=goods_receipt,
                    purchase_order_item=order_item,
                    quantity=order_item.quantity,
                    notes="کالا سالم و مطابق سفارش تحویل گرفته شد.",
                )
            )
        goods_receipt = post_goods_receipt(
            organization=organization,
            actor=owner,
            goods_receipt=goods_receipt,
        )
        for item_index, receipt_item in enumerate(receipt_items, start=1):
            stock_transaction = create_stock_transaction(
                organization=organization,
                actor=owner,
                transaction_number=(
                    f"STK-{organization_index:02d}-{project_index:02d}-{item_index:02d}"
                ),
                transaction_type="receipt",
                material=receipt_item.material,
                unit_of_measure=receipt_item.unit_of_measure,
                quantity=receipt_item.quantity,
                occurred_at=received_at,
                destination_warehouse=warehouse,
                project=project,
                goods_receipt_item=receipt_item,
                reference=goods_receipt.receipt_number,
                notes="ورود مصالح خریداری‌شده به موجودی انبار کارگاه",
            )
            post_stock_transaction(
                organization=organization,
                actor=owner,
                stock_transaction=stock_transaction,
            )
