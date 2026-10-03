from apps.organizations.models import BusinessPermissionCode, MembershipRole
from apps.organizations.permission_catalog import (
    permission_codes,
    permission_codes_with_suffix,
)
from apps.organizations.permission_registry import registered_permission_codes

ALL_PERMISSIONS = registered_permission_codes()
ACTIVE_DEFAULT_PERMISSIONS = ALL_PERMISSIONS
ACCOUNTING_RESTRICTED_PERMISSIONS = permission_codes(
    BusinessPermissionCode.ACCOUNTING_ACCOUNTS_MANAGE,
    BusinessPermissionCode.ACCOUNTING_PERIODS_MANAGE,
    BusinessPermissionCode.ACCOUNTING_JOURNALS_PREPARE,
    BusinessPermissionCode.ACCOUNTING_JOURNALS_SUBMIT,
    BusinessPermissionCode.ACCOUNTING_JOURNALS_APPROVE,
    BusinessPermissionCode.ACCOUNTING_JOURNALS_POST,
    BusinessPermissionCode.ACCOUNTING_RECONCILIATIONS_RUN,
    BusinessPermissionCode.ACCOUNTING_RECONCILIATIONS_DISPOSE,
    BusinessPermissionCode.ACCOUNTING_RECONCILIATIONS_SIGN_OFF,
    BusinessPermissionCode.ACCOUNTING_REPORTS_VIEW,
    BusinessPermissionCode.ACCOUNTING_STATEMENTS_RUN,
    BusinessPermissionCode.ACCOUNTING_ADJUSTMENTS_PREPARE,
    BusinessPermissionCode.ACCOUNTING_PERIODS_CLOSE,
    BusinessPermissionCode.ACCOUNTING_PERIODS_REOPEN,
)
TREASURY_RESTRICTED_PERMISSIONS = permission_codes(
    BusinessPermissionCode.TREASURY_ACCOUNTS_MANAGE,
    BusinessPermissionCode.TREASURY_SENSITIVE_VIEW,
    BusinessPermissionCode.TREASURY_MAPPINGS_MANAGE,
    BusinessPermissionCode.TREASURY_MOVEMENTS_CREATE,
    BusinessPermissionCode.TREASURY_MOVEMENTS_SUBMIT,
    BusinessPermissionCode.TREASURY_MOVEMENTS_APPROVE,
    BusinessPermissionCode.TREASURY_MOVEMENTS_POST,
    BusinessPermissionCode.TREASURY_MOVEMENTS_REVERSE,
    BusinessPermissionCode.TREASURY_CHEQUES_MANAGE,
    BusinessPermissionCode.TREASURY_CHEQUES_CLEAR,
    BusinessPermissionCode.TREASURY_RECONCILIATIONS_RUN,
    BusinessPermissionCode.TREASURY_RECONCILIATIONS_REVIEW,
    BusinessPermissionCode.TREASURY_PAYMENT_REQUESTS_CREATE,
    BusinessPermissionCode.TREASURY_PAYMENT_REQUESTS_SUBMIT,
    BusinessPermissionCode.TREASURY_PAYMENT_REQUESTS_APPROVE,
    BusinessPermissionCode.TREASURY_PAYMENT_REQUESTS_RELEASE,
    BusinessPermissionCode.TREASURY_ADVANCES_MANAGE,
    BusinessPermissionCode.TREASURY_ADVANCES_SETTLE,
    BusinessPermissionCode.TREASURY_ADVANCES_REVERSE,
    BusinessPermissionCode.TREASURY_STATEMENTS_IMPORT,
    BusinessPermissionCode.TREASURY_STATEMENTS_ACCEPT,
    BusinessPermissionCode.TREASURY_STATEMENT_MATCHES_MANAGE,
    BusinessPermissionCode.TREASURY_STATEMENT_MATCHES_CLEAR,
    BusinessPermissionCode.TREASURY_BANK_RECONCILIATIONS_RUN,
)
SUBLEDGER_RESTRICTED_PERMISSIONS = permission_codes(
    BusinessPermissionCode.SUBLEDGERS_OBLIGATIONS_RECOGNIZE,
    BusinessPermissionCode.SUBLEDGERS_SETTLEMENTS_ALLOCATE,
    BusinessPermissionCode.SUBLEDGERS_SETTLEMENTS_REVERSE,
    BusinessPermissionCode.SUBLEDGERS_AGING_RUN,
    BusinessPermissionCode.SUBLEDGERS_RECONCILIATIONS_RUN,
    BusinessPermissionCode.SUBLEDGERS_RECONCILIATIONS_REVIEW,
    BusinessPermissionCode.SUBLEDGERS_WRITEOFFS_PROPOSE,
    BusinessPermissionCode.SUBLEDGERS_WRITEOFFS_APPROVE,
    BusinessPermissionCode.SUBLEDGERS_WRITEOFFS_REVERSE,
    BusinessPermissionCode.SUPPLIER_INVOICES_VIEW,
    BusinessPermissionCode.SUPPLIER_INVOICES_PREPARE,
    BusinessPermissionCode.SUPPLIER_INVOICES_APPROVE,
    BusinessPermissionCode.INVOICE_MATCH_POLICIES_MANAGE,
    BusinessPermissionCode.INVOICE_MATCH_POLICIES_APPROVE,
    BusinessPermissionCode.INVOICE_MATCHES_VIEW,
    BusinessPermissionCode.INVOICE_MATCHES_RUN,
)
BUDGET_RESTRICTED_PERMISSIONS = permission_codes(
    BusinessPermissionCode.PROJECT_CONTROLS_COMPARE,
    BusinessPermissionCode.PROJECT_CONTROLS_EXCEPTIONS_VIEW,
    BusinessPermissionCode.PROJECT_CONTROLS_EXPORT,
    BusinessPermissionCode.COST_STRUCTURES_MANAGE,
    BusinessPermissionCode.BUDGETS_VIEW,
    BusinessPermissionCode.BUDGETS_PREPARE,
    BusinessPermissionCode.BUDGETS_SUBMIT,
    BusinessPermissionCode.BUDGETS_ACCEPT,
    BusinessPermissionCode.PROJECT_COST_SOURCES_MANAGE,
    BusinessPermissionCode.PROJECT_COST_SOURCES_APPROVE,
    BusinessPermissionCode.PROJECT_COST_FACTS_RECORD,
    BusinessPermissionCode.PROJECT_COSTS_VIEW,
    BusinessPermissionCode.PROJECT_COST_RECONCILIATIONS_VIEW,
    BusinessPermissionCode.PROJECT_COST_RECONCILIATIONS_EXPORT,
    BusinessPermissionCode.PROJECT_FORECASTS_PREPARE,
    BusinessPermissionCode.PROJECT_SCHEDULES_VIEW,
    BusinessPermissionCode.PROJECT_SCHEDULES_PREPARE,
    BusinessPermissionCode.PROJECT_CONTROL_REGISTERS_VIEW,
    BusinessPermissionCode.PROJECT_CONTROL_REGISTERS_MANAGE,
    BusinessPermissionCode.PROJECT_CHANGES_VIEW,
    BusinessPermissionCode.PROJECT_CHANGES_PROPOSE,
    BusinessPermissionCode.PROJECT_REBASELINES_VIEW,
    BusinessPermissionCode.PROJECT_REBASELINES_PROPOSE,
    BusinessPermissionCode.PROJECT_SCHEDULE_BASELINES_ACCEPT,
    BusinessPermissionCode.PROJECT_CHANGES_APPROVE,
    BusinessPermissionCode.PROJECT_REBASELINES_ACCEPT,
)
UNAUTHORIZED_PROJECT_CONTROL_APPROVAL_PERMISSIONS = permission_codes(
    BusinessPermissionCode.PROJECT_SCHEDULE_BASELINES_ACCEPT,
    BusinessPermissionCode.PROJECT_CHANGES_APPROVE,
    BusinessPermissionCode.PROJECT_REBASELINES_ACCEPT,
)
UNAUTHORIZED_WRITEOFF_PERMISSIONS = permission_codes(
    BusinessPermissionCode.SUBLEDGERS_WRITEOFFS_APPROVE,
    BusinessPermissionCode.SUBLEDGERS_WRITEOFFS_REVERSE,
)
UNAUTHORIZED_RFQ_CLOSE_PERMISSIONS = permission_codes(
    BusinessPermissionCode.RFQS_CLOSE_CUSTODY,
)
UNAUTHORIZED_RFQ_CUSTODY_PERMISSIONS = permission_codes(
    BusinessPermissionCode.RFQS_CUSTODY_SEALED_EVIDENCE,
)
UNAUTHORIZED_RFQ_OPENING_PERMISSIONS = permission_codes(
    BusinessPermissionCode.RFQ_QUOTES_OPEN,
    BusinessPermissionCode.RFQ_QUOTES_APPROVE_OPEN,
    BusinessPermissionCode.RFQ_QUOTES_VIEW_CONFIDENTIAL,
    BusinessPermissionCode.RFQ_QUOTES_MANAGE_CONFIDENTIAL_ACCESS,
)
UNAUTHORIZED_SUPPLIER_PORTAL_PERMISSIONS = permission_codes(
    BusinessPermissionCode.SUPPLIER_PORTAL_INVITATIONS_MANAGE,
)
OWNER_ONLY_PERMISSIONS = permission_codes(
    BusinessPermissionCode.ACCOUNTS_CREATE,
    BusinessPermissionCode.ACCOUNTS_RESET_PASSWORD,
    BusinessPermissionCode.EMPLOYEES_LINK_ACCOUNT,
    BusinessPermissionCode.WORKFLOWS_VIEW,
    BusinessPermissionCode.WORKFLOWS_CREATE,
    BusinessPermissionCode.WORKFLOWS_CHANGE_DRAFT,
    BusinessPermissionCode.WORKFLOWS_PUBLISH,
    BusinessPermissionCode.WORKFLOWS_RETIRE,
    BusinessPermissionCode.WORKFLOWS_MIGRATE_INSTANCES,
    BusinessPermissionCode.AUTHORIZATION_ROLES_ASSIGN,
    BusinessPermissionCode.AUTHORIZATION_ROLES_REVOKE,
    BusinessPermissionCode.AUTHORIZATION_GRANTS_CREATE,
    BusinessPermissionCode.AUTHORIZATION_GRANTS_REVOKE,
    BusinessPermissionCode.AUTHORIZATION_UNRESOLVED_RECOVER,
    BusinessPermissionCode.PARTIES_MERGE,
    BusinessPermissionCode.PARTY_RESTRICTIONS_MANAGE,
    BusinessPermissionCode.PARTY_GOVERNANCE_MANAGE,
    BusinessPermissionCode.DOCUMENT_CATEGORIES_MANAGE,
    BusinessPermissionCode.DOCUMENT_RETENTION_APPROVE,
    BusinessPermissionCode.DOCUMENT_RETENTION_MANAGE,
    BusinessPermissionCode.DOCUMENT_HOLDS_PLACE,
    BusinessPermissionCode.DOCUMENT_HOLDS_RELEASE,
    BusinessPermissionCode.DOCUMENT_DISPOSALS_REQUEST,
    BusinessPermissionCode.DOCUMENT_DISPOSALS_APPROVE,
    BusinessPermissionCode.DOCUMENTS_EXPORT,
    BusinessPermissionCode.MATERIALS_MERGE,
    BusinessPermissionCode.UOM_CONVERSIONS_MANAGE,
    BusinessPermissionCode.UOM_ROUNDING_MANAGE,
    BusinessPermissionCode.MATERIAL_ATTRIBUTE_DEFINITIONS_MANAGE,
    BusinessPermissionCode.MATERIAL_ATTRIBUTES_IMPORT,
    BusinessPermissionCode.MATERIAL_TECHNICAL_APPROVE,
    BusinessPermissionCode.ACCOUNTING_PERIODS_REOPEN,
)
MANAGER_EXPLICIT_PERMISSIONS = permission_codes(
    BusinessPermissionCode.WORKFLOWS_VIEW,
    BusinessPermissionCode.WORKFLOWS_REASSIGN,
    BusinessPermissionCode.WORKFLOWS_DELEGATE,
    BusinessPermissionCode.WORK_ITEMS_VIEW,
    BusinessPermissionCode.WORK_ITEMS_CLAIM,
    BusinessPermissionCode.WORK_ITEMS_ACT,
)
READ_ONLY_PERMISSIONS = (
    permission_codes_with_suffix("view")
    | permission_codes(BusinessPermissionCode.DOCUMENTS_DOWNLOAD)
) - BUDGET_RESTRICTED_PERMISSIONS
MEMBER_OPERATION_PERMISSIONS = permission_codes(
    BusinessPermissionCode.DAILY_REPORTS_CREATE,
    BusinessPermissionCode.DAILY_REPORTS_ADD_LABOR,
    BusinessPermissionCode.DAILY_REPORTS_ADD_EQUIPMENT,
    BusinessPermissionCode.DAILY_REPORTS_ADD_MATERIAL,
    BusinessPermissionCode.DAILY_REPORTS_ADD_ACTIVITY,
    BusinessPermissionCode.DAILY_REPORTS_ADD_DELAY,
    BusinessPermissionCode.DAILY_REPORTS_SUBMIT,
    BusinessPermissionCode.PURCHASE_REQUESTS_CREATE,
    BusinessPermissionCode.PURCHASE_REQUEST_ITEMS_ADD,
    BusinessPermissionCode.PURCHASE_REQUESTS_SUBMIT,
    BusinessPermissionCode.PURCHASE_REQUESTS_CANCEL,
    BusinessPermissionCode.RFQS_CREATE,
    BusinessPermissionCode.RFQS_CHANGE,
    BusinessPermissionCode.RFQS_SUBMIT,
    BusinessPermissionCode.RFQ_QUOTES_CAPTURE,
    BusinessPermissionCode.RFQ_QUOTES_SUBMIT,
    BusinessPermissionCode.RFQ_QUOTES_WITHDRAW,
    BusinessPermissionCode.GOODS_RECEIPTS_CREATE,
    BusinessPermissionCode.GOODS_RECEIPT_ITEMS_ADD,
    BusinessPermissionCode.GOODS_RECEIPTS_POST,
    BusinessPermissionCode.SERVICE_ACCEPTANCES_CREATE,
    BusinessPermissionCode.SERVICE_ACCEPTANCES_ACCEPT,
    BusinessPermissionCode.STOCK_TRANSACTIONS_CREATE,
    BusinessPermissionCode.STOCK_TRANSACTIONS_POST,
    BusinessPermissionCode.CLAIMS_SUBMIT,
    BusinessPermissionCode.WORK_ITEMS_VIEW,
    BusinessPermissionCode.WORK_ITEMS_CLAIM,
    BusinessPermissionCode.WORK_ITEMS_ACT,
)
OPERATIONS_MANAGER_EXCLUSIONS = (
    permission_codes(
        BusinessPermissionCode.MEMBERSHIP_VIEW,
        BusinessPermissionCode.MEMBERSHIP_CHANGE_ROLE,
        BusinessPermissionCode.MEMBERSHIP_CHANGE_STATUS,
        BusinessPermissionCode.COMPANY_SETTINGS_VIEW,
        BusinessPermissionCode.COMPANY_SETTINGS_CHANGE,
        BusinessPermissionCode.TENANT_POLICIES_APPLY,
        BusinessPermissionCode.ESTIMATES_APPROVE,
        BusinessPermissionCode.BASELINES_APPROVE,
        BusinessPermissionCode.PROGRESS_VERIFY,
        BusinessPermissionCode.CLAIMS_REVISE,
        BusinessPermissionCode.CLAIMS_APPROVE,
    )
    | ACCOUNTING_RESTRICTED_PERMISSIONS
    | TREASURY_RESTRICTED_PERMISSIONS
    | SUBLEDGER_RESTRICTED_PERMISSIONS
    | BUDGET_RESTRICTED_PERMISSIONS
)


DEFAULT_ROLE_PERMISSIONS: dict[str, set[str]] = {
    MembershipRole.TENANT_OWNER: ACTIVE_DEFAULT_PERMISSIONS,
    MembershipRole.TENANT_ADMIN: ACTIVE_DEFAULT_PERMISSIONS
    - {
        str(BusinessPermissionCode.AUTHORIZATION_UNRESOLVED_RECOVER),
        str(BusinessPermissionCode.DOCUMENT_RETENTION_APPROVE),
    },
    MembershipRole.TENANT_MANAGER: (
        ALL_PERMISSIONS
        - OWNER_ONLY_PERMISSIONS
        - ACCOUNTING_RESTRICTED_PERMISSIONS
        - TREASURY_RESTRICTED_PERMISSIONS
        - SUBLEDGER_RESTRICTED_PERMISSIONS
        - BUDGET_RESTRICTED_PERMISSIONS
        - permission_codes(
            BusinessPermissionCode.COMPANY_SETTINGS_CHANGE,
            BusinessPermissionCode.TENANT_POLICIES_APPLY,
            BusinessPermissionCode.MEMBERSHIP_CHANGE_ROLE,
            BusinessPermissionCode.MEMBERSHIP_CHANGE_STATUS,
        )
        | permission_codes(
            BusinessPermissionCode.AUTHORIZATION_ROLES_VIEW,
            BusinessPermissionCode.AUTHORIZATION_GRANTS_VIEW,
        )
    ),
    MembershipRole.PROJECT_MANAGER: (
        ALL_PERMISSIONS
        - OWNER_ONLY_PERMISSIONS
        - ACCOUNTING_RESTRICTED_PERMISSIONS
        - TREASURY_RESTRICTED_PERMISSIONS
        - SUBLEDGER_RESTRICTED_PERMISSIONS
        - BUDGET_RESTRICTED_PERMISSIONS
        - permission_codes(
            BusinessPermissionCode.COMPANY_SETTINGS_CHANGE,
            BusinessPermissionCode.TENANT_POLICIES_APPLY,
            BusinessPermissionCode.MEMBERSHIP_CHANGE_ROLE,
            BusinessPermissionCode.MEMBERSHIP_CHANGE_STATUS,
            BusinessPermissionCode.ACCOUNTS_CREATE,
            BusinessPermissionCode.ACCOUNTS_RESET_PASSWORD,
            BusinessPermissionCode.AUDIT_VIEW,
        )
    ),
    MembershipRole.ACCOUNTANT: READ_ONLY_PERMISSIONS
    | permission_codes(
        BusinessPermissionCode.ACCOUNTING_ACCOUNTS_MANAGE,
        BusinessPermissionCode.ACCOUNTING_PERIODS_MANAGE,
        BusinessPermissionCode.ACCOUNTING_JOURNALS_PREPARE,
        BusinessPermissionCode.ACCOUNTING_JOURNALS_SUBMIT,
        BusinessPermissionCode.ACCOUNTING_JOURNALS_APPROVE,
        BusinessPermissionCode.ACCOUNTING_JOURNALS_POST,
        BusinessPermissionCode.ACCOUNTING_RECONCILIATIONS_RUN,
        BusinessPermissionCode.ACCOUNTING_RECONCILIATIONS_DISPOSE,
        BusinessPermissionCode.ACCOUNTING_RECONCILIATIONS_SIGN_OFF,
        BusinessPermissionCode.ACCOUNTING_REPORTS_VIEW,
        BusinessPermissionCode.ACCOUNTING_STATEMENTS_RUN,
        BusinessPermissionCode.ACCOUNTING_ADJUSTMENTS_PREPARE,
        BusinessPermissionCode.ACCOUNTING_PERIODS_CLOSE,
        BusinessPermissionCode.TREASURY_ACCOUNTS_MANAGE,
        BusinessPermissionCode.TREASURY_SENSITIVE_VIEW,
        BusinessPermissionCode.TREASURY_MAPPINGS_MANAGE,
        BusinessPermissionCode.TREASURY_MOVEMENTS_CREATE,
        BusinessPermissionCode.TREASURY_MOVEMENTS_SUBMIT,
        BusinessPermissionCode.TREASURY_MOVEMENTS_APPROVE,
        BusinessPermissionCode.TREASURY_MOVEMENTS_POST,
        BusinessPermissionCode.TREASURY_MOVEMENTS_REVERSE,
        BusinessPermissionCode.TREASURY_CHEQUES_MANAGE,
        BusinessPermissionCode.TREASURY_CHEQUES_CLEAR,
        BusinessPermissionCode.TREASURY_RECONCILIATIONS_RUN,
        BusinessPermissionCode.TREASURY_RECONCILIATIONS_REVIEW,
        BusinessPermissionCode.TREASURY_PAYMENT_REQUESTS_CREATE,
        BusinessPermissionCode.TREASURY_PAYMENT_REQUESTS_SUBMIT,
        BusinessPermissionCode.TREASURY_PAYMENT_REQUESTS_APPROVE,
        BusinessPermissionCode.TREASURY_PAYMENT_REQUESTS_RELEASE,
        BusinessPermissionCode.TREASURY_ADVANCES_MANAGE,
        BusinessPermissionCode.TREASURY_ADVANCES_SETTLE,
        BusinessPermissionCode.TREASURY_ADVANCES_REVERSE,
        BusinessPermissionCode.TREASURY_STATEMENTS_IMPORT,
        BusinessPermissionCode.TREASURY_STATEMENTS_ACCEPT,
        BusinessPermissionCode.TREASURY_STATEMENT_MATCHES_MANAGE,
        BusinessPermissionCode.TREASURY_STATEMENT_MATCHES_CLEAR,
        BusinessPermissionCode.TREASURY_BANK_RECONCILIATIONS_RUN,
        BusinessPermissionCode.SUBLEDGERS_OBLIGATIONS_RECOGNIZE,
        BusinessPermissionCode.SUBLEDGERS_SETTLEMENTS_ALLOCATE,
        BusinessPermissionCode.SUBLEDGERS_SETTLEMENTS_REVERSE,
        BusinessPermissionCode.SUBLEDGERS_AGING_RUN,
        BusinessPermissionCode.SUBLEDGERS_RECONCILIATIONS_RUN,
        BusinessPermissionCode.SUBLEDGERS_RECONCILIATIONS_REVIEW,
        BusinessPermissionCode.SUBLEDGERS_WRITEOFFS_PROPOSE,
        BusinessPermissionCode.SUPPLIER_INVOICES_VIEW,
        BusinessPermissionCode.SUPPLIER_INVOICES_PREPARE,
        BusinessPermissionCode.SUPPLIER_INVOICES_APPROVE,
        BusinessPermissionCode.INVOICE_MATCH_POLICIES_MANAGE,
        BusinessPermissionCode.INVOICE_MATCH_POLICIES_APPROVE,
        BusinessPermissionCode.INVOICE_MATCHES_VIEW,
        BusinessPermissionCode.INVOICE_MATCHES_RUN,
        BusinessPermissionCode.EXPENSES_CREATE,
        BusinessPermissionCode.EXPENSES_VOID,
        BusinessPermissionCode.PAYMENTS_CREATE,
        BusinessPermissionCode.PAYMENTS_VOID,
        BusinessPermissionCode.PAYMENTS_ALLOCATE,
        BusinessPermissionCode.CLAIMS_CREATE,
        BusinessPermissionCode.CLAIMS_REVISE,
        BusinessPermissionCode.CLAIM_SETTLEMENTS_ALLOCATE,
        BusinessPermissionCode.CLAIM_SETTLEMENTS_REVERSE,
        BusinessPermissionCode.WORK_ITEMS_VIEW,
        BusinessPermissionCode.WORK_ITEMS_CLAIM,
        BusinessPermissionCode.WORK_ITEMS_ACT,
    ),
    MembershipRole.SUPERVISOR: READ_ONLY_PERMISSIONS | MEMBER_OPERATION_PERMISSIONS,
    MembershipRole.COMPANY_OWNER: ALL_PERMISSIONS,
    MembershipRole.COMPANY_MANAGER: (
        ALL_PERMISSIONS - OWNER_ONLY_PERMISSIONS | MANAGER_EXPLICIT_PERMISSIONS
    ),
    MembershipRole.OPERATIONS_MANAGER: (
        ALL_PERMISSIONS - OPERATIONS_MANAGER_EXCLUSIONS - OWNER_ONLY_PERMISSIONS
    ),
    MembershipRole.MEMBER: READ_ONLY_PERMISSIONS | MEMBER_OPERATION_PERMISSIONS,
    MembershipRole.VIEWER: READ_ONLY_PERMISSIONS,
}

# P3-S27-Q03 is unresolved. Catalogue the permissions but grant neither approval
# nor reversal to any default role until authority and SoD policy are accepted.
for _default_permissions in DEFAULT_ROLE_PERMISSIONS.values():
    _default_permissions.difference_update(UNAUTHORIZED_WRITEOFF_PERMISSIONS)
    _default_permissions.difference_update(UNAUTHORIZED_RFQ_CLOSE_PERMISSIONS)
    _default_permissions.difference_update(UNAUTHORIZED_RFQ_CUSTODY_PERMISSIONS)
    _default_permissions.difference_update(UNAUTHORIZED_RFQ_OPENING_PERMISSIONS)
    _default_permissions.difference_update(UNAUTHORIZED_SUPPLIER_PORTAL_PERMISSIONS)
    _default_permissions.difference_update(
        UNAUTHORIZED_PROJECT_CONTROL_APPROVAL_PERMISSIONS
    )


DEFAULT_ROLE_METADATA: dict[str, dict[str, object]] = {
    MembershipRole.TENANT_OWNER: {
        "name": "Tenant Owner",
        "description": "مالک Tenant؛ نقش، دامنه و نامزدی را به‌تنهایی ایجاد نمی‌کند.",
        "is_system": True,
        "is_owner": False,
    },
    MembershipRole.TENANT_ADMIN: {
        "name": "Tenant Admin",
        "description": "مدیر محلی Tenant با نقش مستقل از مالک و مدیر عملیاتی.",
        "is_system": True,
        "is_owner": False,
    },
    MembershipRole.TENANT_MANAGER: {
        "name": "Tenant Manager",
        "description": "مدیر کسب‌وکار Tenant بدون اختیارات حفاظت‌شده مالک.",
        "is_system": True,
        "is_owner": False,
    },
    MembershipRole.PROJECT_MANAGER: {
        "name": "Project Manager",
        "description": "مدیر پروژه در تقاطع مجوز و دامنه صریح پروژه/کارگاه.",
        "is_system": True,
        "is_owner": False,
    },
    MembershipRole.ACCOUNTANT: {
        "name": "Accountant",
        "description": "نقش حسابداری مستقل و دامنه‌دار.",
        "is_system": True,
        "is_owner": False,
    },
    MembershipRole.SUPERVISOR: {
        "name": "Supervisor",
        "description": "ناظر عملیات روزمره در دامنه صریح.",
        "is_system": True,
        "is_owner": False,
    },
    MembershipRole.COMPANY_OWNER: {
        "name": "Company Owner",
        "description": "مالک نهایی شرکت و مسئول انتقال مالکیت.",
        "is_system": True,
        "is_owner": True,
    },
    MembershipRole.COMPANY_MANAGER: {
        "name": "Company Manager",
        "description": "مدیریت اعضا، تنظیمات و عملیات شرکت بدون اختیار مالکیت.",
        "is_system": True,
        "is_owner": False,
    },
    MembershipRole.OPERATIONS_MANAGER: {
        "name": "Operations Manager",
        "description": "مدیریت عملیات اجرایی و مالی شرکت.",
        "is_system": True,
        "is_owner": False,
    },
    MembershipRole.MEMBER: {
        "name": "Member",
        "description": "مشاهده اطلاعات و انجام عملیات روزمره مجاز.",
        "is_system": True,
        "is_owner": False,
    },
    MembershipRole.VIEWER: {
        "name": "Viewer",
        "description": "مشاهده اطلاعات شرکت بدون امکان تغییر.",
        "is_system": True,
        "is_owner": False,
    },
}
