from dataclasses import dataclass

from apps.organizations.models import BusinessPermissionCode


@dataclass(frozen=True, slots=True)
class PermissionResource:
    """One explicitly registered tenant resource and its enforced operations."""

    key: str
    label: str
    model_labels: tuple[str, ...]
    permissions: tuple[BusinessPermissionCode, ...]
    enforcement_modules: tuple[str, ...]


P = BusinessPermissionCode

PERMISSION_RESOURCES: tuple[PermissionResource, ...] = (
    PermissionResource(
        "membership",
        "اعضا و نقش‌های سازمانی",
        ("organizations.OrganizationMembership",),
        (P.MEMBERSHIP_VIEW, P.MEMBERSHIP_CHANGE_ROLE, P.MEMBERSHIP_CHANGE_STATUS),
        ("apps.organizations.services", "apps.organizations.views"),
    ),
    PermissionResource(
        "accounts",
        "حساب‌های کاربری شرکت",
        ("organizations.OrganizationAccountConnectionRequest",),
        (P.ACCOUNTS_CREATE, P.ACCOUNTS_RESET_PASSWORD),
        ("apps.organizations.services", "apps.organizations.views"),
    ),
    PermissionResource(
        "company",
        "تنظیمات شرکت",
        ("organizations.Organization", "organizations.OrganizationSettings"),
        (P.COMPANY_SETTINGS_VIEW, P.COMPANY_SETTINGS_CHANGE),
        ("apps.organizations.services", "apps.organizations.views"),
    ),
    PermissionResource(
        "parties",
        "طرف‌های تجاری",
        ("parties.BusinessParty",),
        (P.PARTIES_VIEW, P.PARTIES_CREATE, P.PARTIES_CHANGE, P.PARTIES_ARCHIVE),
        ("apps.parties.services",),
    ),
    PermissionResource(
        "party_roles",
        "نقش‌های طرف تجاری",
        ("parties.PartyRole",),
        (P.PARTY_ROLES_ASSIGN,),
        ("apps.parties.services",),
    ),
    PermissionResource(
        "party_contacts",
        "راه‌های ارتباطی طرف تجاری",
        ("parties.PartyContact",),
        (P.PARTY_CONTACTS_ADD,),
        ("apps.parties.services",),
    ),
    PermissionResource(
        "units",
        "واحدهای اندازه‌گیری",
        ("materials.UnitOfMeasure",),
        (P.UNITS_VIEW, P.UNITS_CREATE, P.UNITS_ARCHIVE),
        ("apps.materials.services",),
    ),
    PermissionResource(
        "material_categories",
        "دسته‌بندی مصالح",
        ("materials.MaterialCategory",),
        (
            P.MATERIAL_CATEGORIES_VIEW,
            P.MATERIAL_CATEGORIES_CREATE,
            P.MATERIAL_CATEGORIES_CHANGE,
            P.MATERIAL_CATEGORIES_ARCHIVE,
        ),
        ("apps.materials.services",),
    ),
    PermissionResource(
        "materials",
        "مصالح",
        ("materials.Material",),
        (P.MATERIALS_VIEW, P.MATERIALS_CREATE, P.MATERIALS_CHANGE, P.MATERIALS_ARCHIVE),
        ("apps.materials.services",),
    ),
    PermissionResource(
        "projects",
        "پروژه‌ها",
        ("projects.Project",),
        (P.PROJECTS_VIEW, P.PROJECTS_CREATE, P.PROJECTS_ARCHIVE),
        ("apps.projects.services",),
    ),
    PermissionResource(
        "project_sites",
        "کارگاه‌های پروژه",
        ("projects.ProjectSite",),
        (P.PROJECT_SITES_VIEW, P.PROJECT_SITES_CREATE),
        ("apps.projects.services",),
    ),
    PermissionResource(
        "project_phases",
        "فازهای پروژه",
        ("projects.ProjectPhase",),
        (P.PROJECT_PHASES_VIEW, P.PROJECT_PHASES_CREATE, P.PROJECT_PHASES_TRANSITION),
        ("apps.projects.services",),
    ),
    PermissionResource(
        "project_controls",
        "کنترل پروژه",
        (),
        (P.PROJECT_CONTROLS_VIEW,),
        ("apps.projects.views",),
    ),
    PermissionResource(
        "wbs_nodes",
        "ساختار شکست",
        ("projects.WBSNode",),
        (P.WBS_NODES_VIEW, P.WBS_NODES_CREATE, P.WBS_NODES_CHANGE, P.WBS_NODES_ARCHIVE),
        ("apps.projects.services",),
    ),
    PermissionResource(
        "activities",
        "فعالیت‌های پروژه",
        ("projects.Activity",),
        (
            P.ACTIVITIES_VIEW,
            P.ACTIVITIES_CREATE,
            P.ACTIVITIES_TRANSITION,
            P.ACTIVITIES_ARCHIVE,
        ),
        ("apps.projects.services",),
    ),
    PermissionResource(
        "contracts",
        "قراردادها",
        ("contracts.Contract",),
        (
            P.CONTRACTS_VIEW,
            P.CONTRACTS_CREATE,
            P.CONTRACTS_CHANGE,
            P.CONTRACTS_TRANSITION,
        ),
        ("apps.contracts.services",),
    ),
    PermissionResource(
        "contract_items",
        "ردیف‌های قرارداد",
        ("contracts.ContractItem",),
        (P.CONTRACT_ITEMS_ADD,),
        ("apps.contracts.services",),
    ),
    PermissionResource(
        "contract_amendments",
        "الحاقیه‌های قرارداد",
        ("contracts.ContractAmendment",),
        (P.CONTRACT_AMENDMENTS_APPROVE,),
        ("apps.contracts.services",),
    ),
    PermissionResource(
        "estimates",
        "برآوردها",
        ("estimates.Estimate", "estimates.EstimateRevision"),
        (P.ESTIMATES_VIEW, P.ESTIMATES_CREATE, P.ESTIMATES_APPROVE, P.ESTIMATES_REVISE),
        ("apps.estimates.services",),
    ),
    PermissionResource(
        "estimate_items",
        "ردیف‌های برآورد",
        ("estimates.EstimateItem",),
        (P.ESTIMATE_ITEMS_ADD,),
        ("apps.estimates.services",),
    ),
    PermissionResource(
        "expenses",
        "هزینه‌ها",
        ("expenses.Expense",),
        (P.EXPENSES_VIEW, P.EXPENSES_CREATE, P.EXPENSES_VOID),
        ("apps.expenses.services",),
    ),
    PermissionResource(
        "expense_categories",
        "دسته‌های هزینه",
        ("expenses.ExpenseCategory",),
        (
            P.EXPENSE_CATEGORIES_VIEW,
            P.EXPENSE_CATEGORIES_CREATE,
            P.EXPENSE_CATEGORIES_ARCHIVE,
        ),
        ("apps.expenses.services",),
    ),
    PermissionResource(
        "payments",
        "پرداخت‌ها",
        ("payments.Payment", "payments.PaymentAllocation"),
        (P.PAYMENTS_VIEW, P.PAYMENTS_CREATE, P.PAYMENTS_VOID, P.PAYMENTS_ALLOCATE),
        ("apps.payments.services",),
    ),
    PermissionResource(
        "documents",
        "اسناد",
        ("documents.Document", "documents.DocumentVersion", "documents.DocumentLink"),
        (
            P.DOCUMENTS_VIEW,
            P.DOCUMENTS_UPLOAD,
            P.DOCUMENTS_DOWNLOAD,
            P.DOCUMENTS_ARCHIVE,
        ),
        ("apps.documents.services",),
    ),
    PermissionResource(
        "daily_reports",
        "گزارش‌های روزانه",
        (
            "daily_reports.DailyReport",
            "daily_reports.DailyReportLaborEntry",
            "daily_reports.DailyReportEquipmentEntry",
            "daily_reports.DailyReportMaterialEntry",
            "daily_reports.DailyActivity",
            "daily_reports.DelayEvent",
        ),
        (
            P.DAILY_REPORTS_VIEW,
            P.DAILY_REPORTS_CREATE,
            P.DAILY_REPORTS_ADD_LABOR,
            P.DAILY_REPORTS_ADD_EQUIPMENT,
            P.DAILY_REPORTS_ADD_MATERIAL,
            P.DAILY_REPORTS_ADD_ACTIVITY,
            P.DAILY_REPORTS_ADD_DELAY,
            P.DAILY_REPORTS_SUBMIT,
            P.DAILY_REPORTS_APPROVE,
        ),
        ("apps.daily_reports.services",),
    ),
    PermissionResource(
        "departments",
        "دپارتمان‌ها",
        ("workforce.Department",),
        (
            P.DEPARTMENTS_VIEW,
            P.DEPARTMENTS_CREATE,
            P.DEPARTMENTS_CHANGE,
            P.DEPARTMENTS_ARCHIVE,
        ),
        ("apps.workforce.services",),
    ),
    PermissionResource(
        "positions",
        "سمت‌های شغلی",
        ("workforce.Position",),
        (P.POSITIONS_VIEW, P.POSITIONS_CREATE, P.POSITIONS_CHANGE, P.POSITIONS_ARCHIVE),
        ("apps.workforce.services",),
    ),
    PermissionResource(
        "work_teams",
        "تیم‌های کاری",
        ("workforce.WorkTeam",),
        (P.WORK_TEAMS_VIEW, P.WORK_TEAMS_CREATE, P.WORK_TEAMS_ARCHIVE),
        ("apps.workforce.services",),
    ),
    PermissionResource(
        "employees",
        "کارکنان",
        ("workforce.Employee",),
        (
            P.EMPLOYEES_VIEW,
            P.EMPLOYEES_CREATE,
            P.EMPLOYEES_CHANGE_PROFILE_IMAGE,
            P.EMPLOYEES_CHANGE_STATUS,
            P.EMPLOYEES_ARCHIVE,
            P.EMPLOYEES_LINK_ACCOUNT,
        ),
        ("apps.workforce.services",),
    ),
    PermissionResource(
        "employee_positions",
        "سمت‌های کارکنان",
        ("workforce.EmployeePositionAssignment",),
        (P.EMPLOYEE_POSITIONS_ASSIGN, P.EMPLOYEE_POSITIONS_END),
        ("apps.workforce.services",),
    ),
    PermissionResource(
        "project_assignments",
        "تخصیص نیروی پروژه",
        ("workforce.EmployeeProjectAssignment",),
        (
            P.PROJECT_ASSIGNMENTS_VIEW,
            P.PROJECT_ASSIGNMENTS_CREATE,
            P.PROJECT_ASSIGNMENTS_CHANGE_STATUS,
        ),
        ("apps.workforce.services",),
    ),
    PermissionResource(
        "purchase_requests",
        "درخواست‌های خرید",
        ("procurement.PurchaseRequest",),
        (
            P.PURCHASE_REQUESTS_VIEW,
            P.PURCHASE_REQUESTS_CREATE,
            P.PURCHASE_REQUESTS_SUBMIT,
            P.PURCHASE_REQUESTS_APPROVE,
            P.PURCHASE_REQUESTS_REJECT,
            P.PURCHASE_REQUESTS_CANCEL,
        ),
        ("apps.procurement.services",),
    ),
    PermissionResource(
        "purchase_request_items",
        "ردیف‌های درخواست خرید",
        ("procurement.PurchaseRequestItem",),
        (P.PURCHASE_REQUEST_ITEMS_ADD,),
        ("apps.procurement.services",),
    ),
    PermissionResource(
        "purchase_orders",
        "سفارش‌های خرید",
        ("procurement.PurchaseOrder",),
        (
            P.PURCHASE_ORDERS_VIEW,
            P.PURCHASE_ORDERS_CREATE,
            P.PURCHASE_ORDERS_ISSUE,
            P.PURCHASE_ORDERS_CANCEL,
        ),
        ("apps.procurement.services",),
    ),
    PermissionResource(
        "purchase_order_items",
        "ردیف‌های سفارش خرید",
        ("procurement.PurchaseOrderItem",),
        (P.PURCHASE_ORDER_ITEMS_ADD,),
        ("apps.procurement.services",),
    ),
    PermissionResource(
        "goods_receipts",
        "رسیدهای کالا",
        ("procurement.GoodsReceipt",),
        (
            P.GOODS_RECEIPTS_VIEW,
            P.GOODS_RECEIPTS_CREATE,
            P.GOODS_RECEIPTS_POST,
            P.GOODS_RECEIPTS_VOID,
        ),
        ("apps.procurement.services",),
    ),
    PermissionResource(
        "goods_receipt_items",
        "ردیف‌های رسید کالا",
        ("procurement.GoodsReceiptItem",),
        (P.GOODS_RECEIPT_ITEMS_ADD,),
        ("apps.procurement.services",),
    ),
    PermissionResource(
        "warehouses",
        "انبارها",
        ("inventory.Warehouse",),
        (P.WAREHOUSES_VIEW, P.WAREHOUSES_CREATE, P.WAREHOUSES_ARCHIVE),
        ("apps.inventory.services",),
    ),
    PermissionResource(
        "stock_transactions",
        "تراکنش‌های انبار",
        ("inventory.StockTransaction",),
        (
            P.STOCK_TRANSACTIONS_VIEW,
            P.STOCK_TRANSACTIONS_CREATE,
            P.STOCK_TRANSACTIONS_POST,
            P.STOCK_TRANSACTIONS_REVERSE,
        ),
        ("apps.inventory.services",),
    ),
    PermissionResource(
        "stock_balances",
        "موجودی انبار",
        (),
        (P.STOCK_BALANCES_VIEW,),
        ("apps.inventory.services",),
    ),
    PermissionResource(
        "equipment",
        "تجهیزات",
        ("equipment.Equipment",),
        (
            P.EQUIPMENT_VIEW,
            P.EQUIPMENT_CREATE,
            P.EQUIPMENT_CHANGE_STATUS,
            P.EQUIPMENT_ARCHIVE,
        ),
        ("apps.equipment.services",),
    ),
    PermissionResource(
        "equipment_assignments",
        "تخصیص تجهیزات",
        ("equipment.EquipmentAssignment",),
        (
            P.EQUIPMENT_ASSIGNMENTS_VIEW,
            P.EQUIPMENT_ASSIGNMENTS_CREATE,
            P.EQUIPMENT_ASSIGNMENTS_TRANSITION,
        ),
        ("apps.equipment.services",),
    ),
    PermissionResource(
        "maintenance_records",
        "سوابق سرویس و تعمیر",
        ("equipment.MaintenanceRecord",),
        (
            P.MAINTENANCE_RECORDS_VIEW,
            P.MAINTENANCE_RECORDS_CREATE,
            P.MAINTENANCE_RECORDS_TRANSITION,
        ),
        ("apps.equipment.services",),
    ),
    PermissionResource(
        "safety_incidents",
        "حوادث ایمنی",
        ("safety.SafetyIncident",),
        (
            P.SAFETY_INCIDENTS_VIEW,
            P.SAFETY_INCIDENTS_CREATE,
            P.SAFETY_INCIDENTS_REVIEW,
            P.SAFETY_INCIDENTS_MANAGE,
            P.SAFETY_INCIDENTS_CLOSE,
        ),
        ("apps.safety.services", "apps.safety.views"),
    ),
    PermissionResource(
        "quality_issues",
        "مسائل کیفیت",
        ("quality.QualityIssue",),
        (
            P.QUALITY_ISSUES_VIEW,
            P.QUALITY_ISSUES_CREATE,
            P.QUALITY_ISSUES_REVIEW,
            P.QUALITY_ISSUES_MANAGE,
            P.QUALITY_ISSUES_VERIFY,
            P.QUALITY_ISSUES_CLOSE,
        ),
        ("apps.quality.services", "apps.quality.views"),
    ),
    PermissionResource(
        "financials",
        "گزارش‌های مالی",
        (),
        (P.FINANCIALS_VIEW,),
        ("apps.financials.services",),
    ),
    PermissionResource(
        "audit",
        "ممیزی",
        ("audit.AuditEvent",),
        (P.AUDIT_VIEW,),
        ("apps.audit.services",),
    ),
    PermissionResource(
        "workflows",
        "تعریف‌های گردش‌کار",
        (
            "workflows.WorkflowDefinition",
            "workflows.WorkflowVersion",
            "workflows.WorkflowStepDefinition",
            "workflows.WorkflowTransitionDefinition",
            "workflows.WorkflowCondition",
            "workflows.WorkflowRoutingRule",
            "workflows.WorkflowInstance",
            "workflows.WorkflowStepInstance",
            "workflows.WorkflowDelegation",
        ),
        (
            P.WORKFLOWS_VIEW,
            P.WORKFLOWS_CREATE,
            P.WORKFLOWS_CHANGE_DRAFT,
            P.WORKFLOWS_PUBLISH,
            P.WORKFLOWS_RETIRE,
            P.WORKFLOWS_REASSIGN,
            P.WORKFLOWS_DELEGATE,
            P.WORKFLOWS_MIGRATE_INSTANCES,
        ),
        (
            "apps.workflows.services",
            "apps.workflows.simulation",
            "apps.workflows.runtime",
        ),
    ),
    PermissionResource(
        "work_items",
        "کارهای گردش‌کار",
        (
            "workflows.WorkItem",
            "workflows.WorkItemCandidate",
            "workflows.WorkItemAssignmentHistory",
        ),
        (
            P.WORK_ITEMS_VIEW,
            P.WORK_ITEMS_CLAIM,
            P.WORK_ITEMS_ACT,
        ),
        ("apps.workflows.runtime", "apps.workflows.routing"),
    ),
)

PERMISSION_MANAGED_APPS = frozenset(
    {
        "organizations",
        "parties",
        "materials",
        "projects",
        "contracts",
        "estimates",
        "expenses",
        "payments",
        "documents",
        "daily_reports",
        "workforce",
        "procurement",
        "inventory",
        "equipment",
        "safety",
        "quality",
        "audit",
        "workflows",
    }
)

# These models define the global catalog itself and are intentionally system-admin only.
GLOBAL_PERMISSION_MODEL_EXCLUSIONS = frozenset(
    {
        "organizations.BusinessPermission",
        "organizations.OrganizationRole",
        "workflows.WorkflowType",
        "workflows.WorkflowTemplate",
    }
)


def registered_permission_codes() -> set[str]:
    return {
        permission.value
        for resource in PERMISSION_RESOURCES
        for permission in resource.permissions
    }


def registered_model_labels() -> set[str]:
    return {
        model_label
        for resource in PERMISSION_RESOURCES
        for model_label in resource.model_labels
    }


PERMISSION_RESOURCES_BY_KEY = {
    resource.key: resource for resource in PERMISSION_RESOURCES
}
