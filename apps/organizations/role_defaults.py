from apps.organizations.models import BusinessPermissionCode, MembershipRole
from apps.organizations.permission_catalog import (
    permission_codes,
    permission_codes_with_suffix,
)
from apps.organizations.permission_registry import registered_permission_codes

ALL_PERMISSIONS = registered_permission_codes()
REPORTING_PERMISSIONS = frozenset(
    code for code in ALL_PERMISSIONS if code.startswith("reporting.")
)
WORKFORCE_GENERAL_PERMISSIONS = permission_codes(
    BusinessPermissionCode.WORKFORCE_SKILLS_VIEW,
    BusinessPermissionCode.WORKFORCE_SKILLS_MANAGE,
    BusinessPermissionCode.WORKFORCE_QUALIFICATIONS_VIEW,
    BusinessPermissionCode.WORKFORCE_QUALIFICATIONS_MANAGE,
    BusinessPermissionCode.WORKFORCE_QUALIFICATIONS_REVOKE,
)
WORKFORCE_SENSITIVE_PERMISSIONS = permission_codes(
    BusinessPermissionCode.WORKFORCE_PERFORMANCE_VIEW,
    BusinessPermissionCode.WORKFORCE_PERFORMANCE_MANAGE,
    BusinessPermissionCode.WORKFORCE_LABOR_RATES_VIEW,
    BusinessPermissionCode.WORKFORCE_LABOR_RATES_MANAGE,
)
TIME_ATTENDANCE_PERMISSIONS = permission_codes(
    BusinessPermissionCode.TIME_CALENDARS_VIEW,
    BusinessPermissionCode.TIME_CALENDARS_MANAGE,
    BusinessPermissionCode.ATTENDANCE_VIEW,
    BusinessPermissionCode.ATTENDANCE_CAPTURE,
    BusinessPermissionCode.ATTENDANCE_REVIEW,
    BusinessPermissionCode.ATTENDANCE_CORRECT,
    BusinessPermissionCode.ATTENDANCE_IMPORT,
    BusinessPermissionCode.LEAVE_MISSION_VIEW,
    BusinessPermissionCode.LEAVE_MISSION_REQUEST,
    BusinessPermissionCode.LEAVE_MISSION_REVIEW,
    BusinessPermissionCode.OVERTIME_VIEW,
    BusinessPermissionCode.OVERTIME_REQUEST,
    BusinessPermissionCode.OVERTIME_REVIEW,
    BusinessPermissionCode.TIMESHEETS_VIEW,
    BusinessPermissionCode.TIMESHEETS_PREPARE,
    BusinessPermissionCode.TIMESHEETS_REVIEW,
    BusinessPermissionCode.TIMESHEETS_PREVIEW,
)
PAYROLL_SENSITIVE_PERMISSIONS = permission_codes(
    BusinessPermissionCode.PAYROLL_CONFIGURATION_VIEW,
    BusinessPermissionCode.PAYROLL_CONFIGURATION_MANAGE,
    BusinessPermissionCode.PAYROLL_PREPARE,
    BusinessPermissionCode.PAYROLL_REVIEW,
    BusinessPermissionCode.PAYROLL_FINALIZE,
    BusinessPermissionCode.PAYROLL_ADJUST,
    BusinessPermissionCode.PAYROLL_RESULTS_VIEW,
    BusinessPermissionCode.PAYSLIPS_VIEW,
    BusinessPermissionCode.PAYSLIPS_EXPORT,
    BusinessPermissionCode.PAYROLL_AUDIT_VIEW,
    BusinessPermissionCode.PAYROLL_STATUTORY_CONFIGURATION_VIEW,
    BusinessPermissionCode.PAYROLL_STATUTORY_PREPARE,
    BusinessPermissionCode.PAYROLL_STATUTORY_REVIEW,
    BusinessPermissionCode.PAYROLL_STATUTORY_OUTPUT_GENERATE,
    BusinessPermissionCode.PAYROLL_STATUTORY_EXPORT,
    BusinessPermissionCode.PAYROLL_STATUTORY_CORRECT,
    BusinessPermissionCode.PAYROLL_STATUTORY_AUDIT_VIEW,
    BusinessPermissionCode.PAYROLL_LIABILITY_HANDOFF_PREPARE,
    BusinessPermissionCode.PAYROLL_LIABILITY_HANDOFF_REVIEW,
    BusinessPermissionCode.PAYROLL_ACCOUNTING_HANDOFF_PREPARE,
    BusinessPermissionCode.PAYROLL_ACCOUNTING_HANDOFF_REVIEW,
    BusinessPermissionCode.PAYROLL_PAYMENT_HANDOFF_PREPARE,
    BusinessPermissionCode.PAYROLL_PAYMENT_HANDOFF_REVIEW,
    BusinessPermissionCode.PAYROLL_PROJECT_COST_HANDOFF_PREPARE,
    BusinessPermissionCode.PAYROLL_PROJECT_COST_HANDOFF_REVIEW,
    BusinessPermissionCode.PAYROLL_HANDOFF_RECONCILIATION_PREPARE,
    BusinessPermissionCode.PAYROLL_HANDOFF_RECONCILIATION_REVIEW,
)
INVENTORY_CUSTODY_PERMISSIONS = permission_codes(
    BusinessPermissionCode.INVENTORY_RESERVATIONS_VIEW,
    BusinessPermissionCode.INVENTORY_RESERVATIONS_MANAGE,
    BusinessPermissionCode.INVENTORY_RESERVATIONS_RELEASE,
    BusinessPermissionCode.INVENTORY_TRACEABILITY_VIEW,
    BusinessPermissionCode.INVENTORY_TRACEABILITY_MANAGE,
    BusinessPermissionCode.INVENTORY_TRACEABILITY_DISPOSE,
    BusinessPermissionCode.INVENTORY_COUNTS_VIEW,
    BusinessPermissionCode.INVENTORY_COUNTS_PREPARE,
    BusinessPermissionCode.INVENTORY_COUNTS_APPROVE,
    BusinessPermissionCode.INVENTORY_COUNTS_POST,
    BusinessPermissionCode.INVENTORY_TRANSFERS_VIEW,
    BusinessPermissionCode.INVENTORY_TRANSFERS_PREPARE,
    BusinessPermissionCode.INVENTORY_TRANSFERS_DISPATCH,
    BusinessPermissionCode.INVENTORY_TRANSFERS_ACCEPT,
    BusinessPermissionCode.INVENTORY_TRANSFERS_RESOLVE,
    BusinessPermissionCode.INVENTORY_RECONCILIATIONS_VIEW,
)
EQUIPMENT_COST_PERMISSIONS = permission_codes(
    BusinessPermissionCode.EQUIPMENT_COST_POLICY_VIEW,
    BusinessPermissionCode.EQUIPMENT_COST_POLICY_MANAGE,
    BusinessPermissionCode.EQUIPMENT_COST_POLICY_PUBLISH,
    BusinessPermissionCode.EQUIPMENT_COST_ALLOCATION_VIEW,
    BusinessPermissionCode.EQUIPMENT_COST_ALLOCATION_PREPARE,
    BusinessPermissionCode.EQUIPMENT_COST_ALLOCATION_REVIEW,
    BusinessPermissionCode.EQUIPMENT_COST_ALLOCATION_REVERSE,
    BusinessPermissionCode.EQUIPMENT_COST_HANDOFF_PREPARE,
    BusinessPermissionCode.EQUIPMENT_COST_HANDOFF_REVIEW,
    BusinessPermissionCode.EQUIPMENT_COST_HANDOFF_RECONCILE,
)
FIXED_ASSET_PERMISSIONS = permission_codes(
    BusinessPermissionCode.FIXED_ASSETS_VIEW,
    BusinessPermissionCode.FIXED_ASSET_CANDIDATE_PREPARE,
    BusinessPermissionCode.FIXED_ASSET_CANDIDATE_REVIEW,
    BusinessPermissionCode.FIXED_ASSETS_MANAGE,
    BusinessPermissionCode.FIXED_ASSET_CLASS_POLICY_MANAGE,
    BusinessPermissionCode.FIXED_ASSET_CLASS_POLICY_PUBLISH,
    BusinessPermissionCode.FIXED_ASSET_CAPITALIZE,
    BusinessPermissionCode.FIXED_ASSET_TRANSACTION_PREPARE,
    BusinessPermissionCode.FIXED_ASSET_TRANSACTION_REVIEW,
    BusinessPermissionCode.FIXED_ASSET_TRANSACTION_REVERSE,
    BusinessPermissionCode.FIXED_ASSET_DEPRECIATION_PREVIEW,
    BusinessPermissionCode.FIXED_ASSET_DEPRECIATION_FINALIZE,
    BusinessPermissionCode.FIXED_ASSET_DEPRECIATION_REVERSE,
    BusinessPermissionCode.FIXED_ASSET_TRANSFER,
    BusinessPermissionCode.FIXED_ASSET_IMPAIR,
    BusinessPermissionCode.FIXED_ASSET_DISPOSE,
    BusinessPermissionCode.FIXED_ASSET_HANDOFF_PREPARE,
    BusinessPermissionCode.FIXED_ASSET_HANDOFF_REVIEW,
    BusinessPermissionCode.FIXED_ASSET_HANDOFF_RECONCILE,
    BusinessPermissionCode.FIXED_ASSET_AUDIT_VIEW,
)
FIELD_OPERATION_PERMISSIONS = permission_codes(
    BusinessPermissionCode.FIELD_OBSERVATIONS_VIEW,
    BusinessPermissionCode.FIELD_OBSERVATIONS_CAPTURE,
    BusinessPermissionCode.FIELD_OBSERVATIONS_SUBMIT,
    BusinessPermissionCode.FIELD_OBSERVATIONS_REVIEW,
    BusinessPermissionCode.FIELD_OBSERVATIONS_LOCATION_VIEW,
    BusinessPermissionCode.FIELD_PROPOSALS_PREPARE,
    BusinessPermissionCode.FIELD_PROPOSALS_REVIEW,
)
# P7-S01–S05: sensitive performance and labor-rate data is deny-by-default.
# General capability records are granted only to explicitly selected management roles.
ACTIVE_DEFAULT_PERMISSIONS = (
    ALL_PERMISSIONS
    - WORKFORCE_GENERAL_PERMISSIONS
    - WORKFORCE_SENSITIVE_PERMISSIONS
    - TIME_ATTENDANCE_PERMISSIONS
    - PAYROLL_SENSITIVE_PERMISSIONS
    - INVENTORY_CUSTODY_PERMISSIONS
    - EQUIPMENT_COST_PERMISSIONS
    - FIXED_ASSET_PERMISSIONS
    - FIELD_OPERATION_PERMISSIONS
)
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
    (
        permission_codes_with_suffix("view")
        | permission_codes(BusinessPermissionCode.DOCUMENTS_DOWNLOAD)
    )
    - BUDGET_RESTRICTED_PERMISSIONS
    - EQUIPMENT_COST_PERMISSIONS
    - FIXED_ASSET_PERMISSIONS
)
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
    MembershipRole.TENANT_OWNER: ACTIVE_DEFAULT_PERMISSIONS
    | WORKFORCE_GENERAL_PERMISSIONS,
    MembershipRole.TENANT_ADMIN: ACTIVE_DEFAULT_PERMISSIONS
    - {
        str(BusinessPermissionCode.AUTHORIZATION_UNRESOLVED_RECOVER),
        str(BusinessPermissionCode.DOCUMENT_RETENTION_APPROVE),
    }
    | WORKFORCE_GENERAL_PERMISSIONS,
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
        | WORKFORCE_GENERAL_PERMISSIONS
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
        | WORKFORCE_GENERAL_PERMISSIONS
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

# P7-S06–S12 grants are deliberate. Tenant administrators own calendar/import
# configuration; scoped operational roles capture and prepare; review/correction
# permissions remain separate so services can enforce maker-checker.
_time_view = permission_codes(
    BusinessPermissionCode.TIME_CALENDARS_VIEW,
    BusinessPermissionCode.ATTENDANCE_VIEW,
    BusinessPermissionCode.LEAVE_MISSION_VIEW,
    BusinessPermissionCode.OVERTIME_VIEW,
    BusinessPermissionCode.TIMESHEETS_VIEW,
)
_time_prepare = permission_codes(
    BusinessPermissionCode.ATTENDANCE_CAPTURE,
    BusinessPermissionCode.LEAVE_MISSION_REQUEST,
    BusinessPermissionCode.OVERTIME_REQUEST,
    BusinessPermissionCode.TIMESHEETS_PREPARE,
)
_time_review = permission_codes(
    BusinessPermissionCode.ATTENDANCE_REVIEW,
    BusinessPermissionCode.LEAVE_MISSION_REVIEW,
    BusinessPermissionCode.OVERTIME_REVIEW,
    BusinessPermissionCode.TIMESHEETS_REVIEW,
    BusinessPermissionCode.TIMESHEETS_PREVIEW,
)
DEFAULT_ROLE_PERMISSIONS[MembershipRole.TENANT_OWNER].update(
    TIME_ATTENDANCE_PERMISSIONS
)
DEFAULT_ROLE_PERMISSIONS[MembershipRole.TENANT_ADMIN].update(
    TIME_ATTENDANCE_PERMISSIONS
)
DEFAULT_ROLE_PERMISSIONS[MembershipRole.TENANT_MANAGER].update(
    _time_view | _time_prepare | _time_review
)
DEFAULT_ROLE_PERMISSIONS[MembershipRole.PROJECT_MANAGER].update(
    _time_view | _time_prepare | _time_review
)
DEFAULT_ROLE_PERMISSIONS[MembershipRole.SUPERVISOR].update(_time_view | _time_prepare)
DEFAULT_ROLE_PERMISSIONS[MembershipRole.COMPANY_OWNER].update(
    TIME_ATTENDANCE_PERMISSIONS
)
DEFAULT_ROLE_PERMISSIONS[MembershipRole.COMPANY_MANAGER].update(
    _time_view | _time_prepare | _time_review
)
DEFAULT_ROLE_PERMISSIONS[MembershipRole.OPERATIONS_MANAGER].update(
    _time_view | _time_prepare | _time_review
)
DEFAULT_ROLE_PERMISSIONS[MembershipRole.MEMBER].update(_time_view)
DEFAULT_ROLE_PERMISSIONS[MembershipRole.VIEWER].update(_time_view)

# P8-S05–S11: operational preparation and independent decisions are separate.
_inventory_view = permission_codes(
    BusinessPermissionCode.INVENTORY_RESERVATIONS_VIEW,
    BusinessPermissionCode.INVENTORY_TRACEABILITY_VIEW,
    BusinessPermissionCode.INVENTORY_COUNTS_VIEW,
    BusinessPermissionCode.INVENTORY_TRANSFERS_VIEW,
    BusinessPermissionCode.INVENTORY_RECONCILIATIONS_VIEW,
)
_inventory_prepare = permission_codes(
    BusinessPermissionCode.INVENTORY_RESERVATIONS_MANAGE,
    BusinessPermissionCode.INVENTORY_RESERVATIONS_RELEASE,
    BusinessPermissionCode.INVENTORY_COUNTS_PREPARE,
    BusinessPermissionCode.INVENTORY_TRANSFERS_PREPARE,
    BusinessPermissionCode.INVENTORY_TRANSFERS_DISPATCH,
)
_inventory_control = permission_codes(
    BusinessPermissionCode.INVENTORY_TRACEABILITY_MANAGE,
    BusinessPermissionCode.INVENTORY_TRACEABILITY_DISPOSE,
    BusinessPermissionCode.INVENTORY_COUNTS_APPROVE,
    BusinessPermissionCode.INVENTORY_COUNTS_POST,
    BusinessPermissionCode.INVENTORY_TRANSFERS_ACCEPT,
    BusinessPermissionCode.INVENTORY_TRANSFERS_RESOLVE,
)
for _role in (
    MembershipRole.TENANT_OWNER,
    MembershipRole.TENANT_ADMIN,
    MembershipRole.TENANT_MANAGER,
    MembershipRole.COMPANY_OWNER,
    MembershipRole.COMPANY_MANAGER,
    MembershipRole.OPERATIONS_MANAGER,
):
    DEFAULT_ROLE_PERMISSIONS[_role].update(
        _inventory_view | _inventory_prepare | _inventory_control
    )
DEFAULT_ROLE_PERMISSIONS[MembershipRole.PROJECT_MANAGER].update(
    _inventory_view | _inventory_prepare | _inventory_control
)
DEFAULT_ROLE_PERMISSIONS[MembershipRole.SUPERVISOR].update(
    _inventory_view | _inventory_prepare
)
DEFAULT_ROLE_PERMISSIONS[MembershipRole.MEMBER].update(_inventory_view)
DEFAULT_ROLE_PERMISSIONS[MembershipRole.VIEWER].update(_inventory_view)

# P9-S01–S05: Field Operations is default-denied until these explicit role
# grants; precise location remains narrower than ordinary observation access.
_field_view = permission_codes(BusinessPermissionCode.FIELD_OBSERVATIONS_VIEW)
_field_capture = permission_codes(
    BusinessPermissionCode.FIELD_OBSERVATIONS_CAPTURE,
    BusinessPermissionCode.FIELD_OBSERVATIONS_SUBMIT,
    BusinessPermissionCode.FIELD_PROPOSALS_PREPARE,
)
_field_review = permission_codes(
    BusinessPermissionCode.FIELD_OBSERVATIONS_REVIEW,
    BusinessPermissionCode.FIELD_PROPOSALS_REVIEW,
)
_field_location = permission_codes(
    BusinessPermissionCode.FIELD_OBSERVATIONS_LOCATION_VIEW
)
for _role in (
    MembershipRole.TENANT_OWNER,
    MembershipRole.TENANT_ADMIN,
    MembershipRole.TENANT_MANAGER,
    MembershipRole.COMPANY_OWNER,
    MembershipRole.COMPANY_MANAGER,
    MembershipRole.OPERATIONS_MANAGER,
    MembershipRole.PROJECT_MANAGER,
):
    DEFAULT_ROLE_PERMISSIONS[_role].update(
        _field_view | _field_capture | _field_review | _field_location
    )
DEFAULT_ROLE_PERMISSIONS[MembershipRole.SUPERVISOR].update(_field_view | _field_capture)
DEFAULT_ROLE_PERMISSIONS[MembershipRole.MEMBER].update(_field_view | _field_capture)
DEFAULT_ROLE_PERMISSIONS[MembershipRole.VIEWER].update(_field_view)

# P9-S06–S11: common mechanics do not merge HSE/QA authority. Default roles
# receive bounded capabilities; sensitive evidence remains explicitly denied.
_compliance_view = permission_codes(BusinessPermissionCode.COMPLIANCE_VIEW)
_compliance_field = permission_codes(
    BusinessPermissionCode.COMPLIANCE_INSPECTIONS_CREATE,
    BusinessPermissionCode.COMPLIANCE_INSPECTIONS_EXECUTE,
    BusinessPermissionCode.COMPLIANCE_INSPECTIONS_SUBMIT,
    BusinessPermissionCode.COMPLIANCE_FINDINGS_CREATE,
    BusinessPermissionCode.COMPLIANCE_PERMITS_PREPARE,
    BusinessPermissionCode.COMPLIANCE_TESTS_REQUEST,
    BusinessPermissionCode.COMPLIANCE_TESTS_EXECUTE,
    BusinessPermissionCode.COMPLIANCE_CAPA_EXECUTE,
    BusinessPermissionCode.COMPLIANCE_EVIDENCE_LINK,
)
_compliance_control = permission_codes(
    BusinessPermissionCode.COMPLIANCE_TEMPLATES_MANAGE,
    BusinessPermissionCode.COMPLIANCE_TEMPLATES_PUBLISH,
    BusinessPermissionCode.COMPLIANCE_INSPECTIONS_REVIEW,
    BusinessPermissionCode.COMPLIANCE_FINDINGS_CLASSIFY,
    BusinessPermissionCode.COMPLIANCE_FINDINGS_MANAGE,
    BusinessPermissionCode.COMPLIANCE_PERMITS_ISSUE,
    BusinessPermissionCode.COMPLIANCE_PERMITS_CONTROL,
    BusinessPermissionCode.COMPLIANCE_TESTS_REVIEW,
    BusinessPermissionCode.COMPLIANCE_NCR_MANAGE,
    BusinessPermissionCode.COMPLIANCE_CAPA_ASSIGN,
    BusinessPermissionCode.COMPLIANCE_VERIFY,
    BusinessPermissionCode.COMPLIANCE_EFFECTIVENESS_REVIEW,
    BusinessPermissionCode.COMPLIANCE_CLOSE,
    BusinessPermissionCode.COMPLIANCE_REOPEN,
    BusinessPermissionCode.COMPLIANCE_EXPORT,
    BusinessPermissionCode.COMPLIANCE_AUDIT_RECONCILE,
)
for _role in (
    MembershipRole.TENANT_OWNER,
    MembershipRole.TENANT_ADMIN,
    MembershipRole.TENANT_MANAGER,
    MembershipRole.COMPANY_OWNER,
    MembershipRole.COMPANY_MANAGER,
    MembershipRole.OPERATIONS_MANAGER,
    MembershipRole.PROJECT_MANAGER,
):
    DEFAULT_ROLE_PERMISSIONS[_role].update(
        _compliance_view | _compliance_field | _compliance_control
    )
DEFAULT_ROLE_PERMISSIONS[MembershipRole.SUPERVISOR].update(
    _compliance_view | _compliance_field
)
DEFAULT_ROLE_PERMISSIONS[MembershipRole.MEMBER].update(_compliance_view)
DEFAULT_ROLE_PERMISSIONS[MembershipRole.VIEWER].update(_compliance_view)

_partner_view = permission_codes(BusinessPermissionCode.PARTNER_VIEW)
_partner_field = permission_codes(
    BusinessPermissionCode.PARTNER_PROFILE_MANAGE,
    BusinessPermissionCode.PARTNER_QUALIFICATIONS_PREPARE,
    BusinessPermissionCode.PARTNER_QUALIFICATIONS_SUBMIT,
    BusinessPermissionCode.PARTNER_EVIDENCE_LINK,
    BusinessPermissionCode.PARTNER_EVALUATIONS_PREPARE,
    BusinessPermissionCode.PARTNER_EVALUATIONS_SUBMIT,
    BusinessPermissionCode.PARTNER_EVALUATIONS_APPEAL,
    BusinessPermissionCode.PARTNER_PROPOSALS_CREATE,
)
_partner_control = permission_codes(
    BusinessPermissionCode.PARTNER_REQUIREMENTS_MANAGE,
    BusinessPermissionCode.PARTNER_QUALIFICATIONS_REVIEW,
    BusinessPermissionCode.PARTNER_QUALIFICATIONS_CONTROL,
    BusinessPermissionCode.PARTNER_CATEGORY_DECIDE,
    BusinessPermissionCode.PARTNER_EVALUATIONS_PUBLISH,
    BusinessPermissionCode.PARTNER_EXPORT,
    BusinessPermissionCode.PARTNER_AUDIT_RECONCILE,
)
for _role in (
    MembershipRole.TENANT_OWNER,
    MembershipRole.TENANT_ADMIN,
    MembershipRole.TENANT_MANAGER,
    MembershipRole.COMPANY_OWNER,
    MembershipRole.COMPANY_MANAGER,
    MembershipRole.OPERATIONS_MANAGER,
    MembershipRole.PROJECT_MANAGER,
):
    DEFAULT_ROLE_PERMISSIONS[_role].update(
        _partner_view | _partner_field | _partner_control
    )
DEFAULT_ROLE_PERMISSIONS[MembershipRole.SUPERVISOR].update(
    _partner_view | _partner_field
)
DEFAULT_ROLE_PERMISSIONS[MembershipRole.MEMBER].update(_partner_view)
DEFAULT_ROLE_PERMISSIONS[MembershipRole.VIEWER].update(_partner_view)

# P9-S21–S24: discovery and drafting are useful default capabilities, but every
# consequential publication/sensitivity/reconciliation operation remains explicit.
_knowledge_view = permission_codes(BusinessPermissionCode.KNOWLEDGE_PUBLICATIONS_VIEW)
_knowledge_prepare = permission_codes(
    BusinessPermissionCode.KNOWLEDGE_CANDIDATES_CREATE,
    BusinessPermissionCode.KNOWLEDGE_CANDIDATES_SUBMIT,
    BusinessPermissionCode.KNOWLEDGE_UNPUBLISHED_VIEW,
    BusinessPermissionCode.KNOWLEDGE_REUSE_RECORD,
)
for _role in (
    MembershipRole.TENANT_OWNER,
    MembershipRole.TENANT_ADMIN,
    MembershipRole.TENANT_MANAGER,
    MembershipRole.COMPANY_OWNER,
    MembershipRole.COMPANY_MANAGER,
    MembershipRole.OPERATIONS_MANAGER,
    MembershipRole.PROJECT_MANAGER,
):
    DEFAULT_ROLE_PERMISSIONS[_role].update(_knowledge_view | _knowledge_prepare)
DEFAULT_ROLE_PERMISSIONS[MembershipRole.SUPERVISOR].update(
    _knowledge_view | _knowledge_prepare
)
DEFAULT_ROLE_PERMISSIONS[MembershipRole.MEMBER].update(
    _knowledge_view | _knowledge_prepare
)
DEFAULT_ROLE_PERMISSIONS[MembershipRole.VIEWER].update(_knowledge_view)

# P8-S24–S27: cost and asset finance permissions remain default-denied except
# for explicitly selected roles. Services still enforce maker-checker per object.
_equipment_cost_view = permission_codes(
    BusinessPermissionCode.EQUIPMENT_COST_POLICY_VIEW,
    BusinessPermissionCode.EQUIPMENT_COST_ALLOCATION_VIEW,
)
_equipment_cost_prepare = permission_codes(
    BusinessPermissionCode.EQUIPMENT_COST_POLICY_MANAGE,
    BusinessPermissionCode.EQUIPMENT_COST_ALLOCATION_PREPARE,
    BusinessPermissionCode.EQUIPMENT_COST_HANDOFF_PREPARE,
)
_equipment_cost_control = (
    EQUIPMENT_COST_PERMISSIONS - _equipment_cost_view - _equipment_cost_prepare
)
_fixed_asset_view = permission_codes(BusinessPermissionCode.FIXED_ASSETS_VIEW)

for _role in (MembershipRole.TENANT_OWNER, MembershipRole.COMPANY_OWNER):
    DEFAULT_ROLE_PERMISSIONS[_role].update(
        EQUIPMENT_COST_PERMISSIONS | FIXED_ASSET_PERMISSIONS
    )
for _role in (MembershipRole.TENANT_ADMIN, MembershipRole.ACCOUNTANT):
    DEFAULT_ROLE_PERMISSIONS[_role].update(
        EQUIPMENT_COST_PERMISSIONS | FIXED_ASSET_PERMISSIONS
    )
for _role in (MembershipRole.TENANT_MANAGER, MembershipRole.COMPANY_MANAGER):
    DEFAULT_ROLE_PERMISSIONS[_role].update(
        _equipment_cost_view
        | _equipment_cost_prepare
        | _equipment_cost_control
        | _fixed_asset_view
    )
for _role in (MembershipRole.PROJECT_MANAGER, MembershipRole.OPERATIONS_MANAGER):
    DEFAULT_ROLE_PERMISSIONS[_role].update(
        _equipment_cost_view | _equipment_cost_prepare | _fixed_asset_view
    )

# P3-S27-Q03 is unresolved. Catalogue the permissions but grant neither approval
# nor reversal to any default role until authority and SoD policy are accepted.
for _default_permissions in DEFAULT_ROLE_PERMISSIONS.values():
    # P7-S01–S05 sensitive employee data is deny-by-default.  It may be granted
    # only through an explicit, organization-specific role assignment.
    _default_permissions.difference_update(WORKFORCE_SENSITIVE_PERMISSIONS)
    _default_permissions.difference_update(PAYROLL_SENSITIVE_PERMISSIONS)
    _default_permissions.difference_update(UNAUTHORIZED_WRITEOFF_PERMISSIONS)
    _default_permissions.difference_update(UNAUTHORIZED_RFQ_CLOSE_PERMISSIONS)
    _default_permissions.difference_update(UNAUTHORIZED_RFQ_CUSTODY_PERMISSIONS)
    _default_permissions.difference_update(UNAUTHORIZED_RFQ_OPENING_PERMISSIONS)
    _default_permissions.difference_update(UNAUTHORIZED_SUPPLIER_PORTAL_PERMISSIONS)
    _default_permissions.difference_update(
        UNAUTHORIZED_PROJECT_CONTROL_APPROVAL_PERMISSIONS
    )
    # P10-M17=A: every new reporting permission is explicitly assigned and no
    # existing role name implies metric, drill-through, export, or audit access.
    _default_permissions.difference_update(REPORTING_PERMISSIONS)


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
