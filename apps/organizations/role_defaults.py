from apps.organizations.models import BusinessPermissionCode, MembershipRole
from apps.organizations.permission_catalog import (
    permission_codes,
    permission_codes_with_suffix,
)
from apps.organizations.permission_registry import registered_permission_codes

ALL_PERMISSIONS = registered_permission_codes()
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
    BusinessPermissionCode.TENANT_POLICIES_APPROVE,
)
MANAGER_EXPLICIT_PERMISSIONS = permission_codes(
    BusinessPermissionCode.WORKFLOWS_VIEW,
    BusinessPermissionCode.WORKFLOWS_REASSIGN,
    BusinessPermissionCode.WORKFLOWS_DELEGATE,
    BusinessPermissionCode.WORK_ITEMS_VIEW,
    BusinessPermissionCode.WORK_ITEMS_CLAIM,
    BusinessPermissionCode.WORK_ITEMS_ACT,
)
READ_ONLY_PERMISSIONS = permission_codes_with_suffix("view") | permission_codes(
    BusinessPermissionCode.DOCUMENTS_DOWNLOAD,
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
    BusinessPermissionCode.GOODS_RECEIPTS_CREATE,
    BusinessPermissionCode.GOODS_RECEIPT_ITEMS_ADD,
    BusinessPermissionCode.GOODS_RECEIPTS_POST,
    BusinessPermissionCode.STOCK_TRANSACTIONS_CREATE,
    BusinessPermissionCode.STOCK_TRANSACTIONS_POST,
    BusinessPermissionCode.CLAIMS_SUBMIT,
    BusinessPermissionCode.WORK_ITEMS_VIEW,
    BusinessPermissionCode.WORK_ITEMS_CLAIM,
    BusinessPermissionCode.WORK_ITEMS_ACT,
)
OPERATIONS_MANAGER_EXCLUSIONS = permission_codes(
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


DEFAULT_ROLE_PERMISSIONS: dict[str, set[str]] = {
    MembershipRole.TENANT_OWNER: ALL_PERMISSIONS,
    MembershipRole.TENANT_ADMIN: ALL_PERMISSIONS
    - {
        str(BusinessPermissionCode.AUTHORIZATION_UNRESOLVED_RECOVER),
        str(BusinessPermissionCode.TENANT_POLICIES_APPROVE),
    },
    MembershipRole.TENANT_MANAGER: (
        ALL_PERMISSIONS
        - OWNER_ONLY_PERMISSIONS
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
