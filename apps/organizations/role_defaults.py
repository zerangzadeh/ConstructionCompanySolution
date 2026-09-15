from apps.organizations.models import BusinessPermissionCode, MembershipRole
from apps.organizations.permission_catalog import (
    permission_codes,
    permission_codes_with_suffix,
)
from apps.organizations.permission_registry import registered_permission_codes

ALL_PERMISSIONS = registered_permission_codes()
OWNER_ONLY_PERMISSIONS = permission_codes(
    BusinessPermissionCode.ACCOUNTS_CREATE,
    BusinessPermissionCode.EMPLOYEES_LINK_ACCOUNT,
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
)
OPERATIONS_MANAGER_EXCLUSIONS = permission_codes(
    BusinessPermissionCode.MEMBERSHIP_VIEW,
    BusinessPermissionCode.MEMBERSHIP_CHANGE_ROLE,
    BusinessPermissionCode.MEMBERSHIP_CHANGE_STATUS,
    BusinessPermissionCode.COMPANY_SETTINGS_VIEW,
    BusinessPermissionCode.COMPANY_SETTINGS_CHANGE,
    BusinessPermissionCode.ESTIMATES_APPROVE,
)


DEFAULT_ROLE_PERMISSIONS: dict[str, set[str]] = {
    MembershipRole.COMPANY_OWNER: ALL_PERMISSIONS,
    MembershipRole.COMPANY_MANAGER: ALL_PERMISSIONS - OWNER_ONLY_PERMISSIONS,
    MembershipRole.OPERATIONS_MANAGER: (
        ALL_PERMISSIONS - OPERATIONS_MANAGER_EXCLUSIONS - OWNER_ONLY_PERMISSIONS
    ),
    MembershipRole.MEMBER: READ_ONLY_PERMISSIONS | MEMBER_OPERATION_PERMISSIONS,
    MembershipRole.VIEWER: READ_ONLY_PERMISSIONS,
}


DEFAULT_ROLE_METADATA: dict[str, dict[str, object]] = {
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
