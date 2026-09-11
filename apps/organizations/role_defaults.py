from apps.organizations.models import BusinessPermissionCode, MembershipRole

DEFAULT_ROLE_PERMISSIONS: dict[str, set[str]] = {
    MembershipRole.COMPANY_OWNER: set(BusinessPermissionCode.values),
    MembershipRole.COMPANY_MANAGER: set(BusinessPermissionCode.values),
    MembershipRole.OPERATIONS_MANAGER: {
        BusinessPermissionCode.PARTIES_MANAGE,
        BusinessPermissionCode.MATERIALS_MANAGE,
        BusinessPermissionCode.PROJECTS_MANAGE,
        BusinessPermissionCode.CONTRACTS_MANAGE,
        BusinessPermissionCode.ESTIMATES_MANAGE,
        BusinessPermissionCode.EXPENSES_MANAGE,
        BusinessPermissionCode.PAYMENTS_MANAGE,
        BusinessPermissionCode.DOCUMENTS_MANAGE,
        BusinessPermissionCode.DAILY_REPORTS_CREATE,
        BusinessPermissionCode.DAILY_REPORTS_MANAGE,
        BusinessPermissionCode.WORKFORCE_MANAGE,
        BusinessPermissionCode.PROCUREMENT_REQUEST,
        BusinessPermissionCode.PROCUREMENT_MANAGE,
        BusinessPermissionCode.INVENTORY_MOVEMENT,
        BusinessPermissionCode.INVENTORY_MANAGE,
        BusinessPermissionCode.AUDIT_VIEW,
    },
    MembershipRole.MEMBER: {
        BusinessPermissionCode.DAILY_REPORTS_CREATE,
        BusinessPermissionCode.PROCUREMENT_REQUEST,
        BusinessPermissionCode.INVENTORY_MOVEMENT,
        BusinessPermissionCode.AUDIT_VIEW,
    },
    MembershipRole.VIEWER: {BusinessPermissionCode.AUDIT_VIEW},
}


DEFAULT_ROLE_METADATA: dict[str, dict[str, object]] = {
    MembershipRole.COMPANY_OWNER: {
        "name": "مالک شرکت",
        "description": "مالک نهایی شرکت و مسئول انتقال مالکیت.",
        "is_system": True,
        "is_owner": True,
    },
    MembershipRole.COMPANY_MANAGER: {
        "name": "مدیر شرکت",
        "description": "مدیریت اعضا، تنظیمات و عملیات شرکت بدون اختیار مالکیت.",
        "is_system": True,
        "is_owner": False,
    },
    MembershipRole.OPERATIONS_MANAGER: {
        "name": "مدیر اجرایی",
        "description": "مدیریت عملیات اجرایی و مالی شرکت.",
        "is_system": True,
        "is_owner": False,
    },
    MembershipRole.MEMBER: {
        "name": "عضو",
        "description": "انجام عملیات روزمره مجاز.",
        "is_system": True,
        "is_owner": False,
    },
    MembershipRole.VIEWER: {
        "name": "مشاهده‌گر",
        "description": "مشاهده اطلاعات شرکت بدون امکان تغییر.",
        "is_system": True,
        "is_owner": False,
    },
}
