"""Owning-domain shortcuts; visibility grants no business or source authority."""

from dataclasses import dataclass

from apps.organizations.authorization import (
    get_active_membership,
    membership_has_scope,
    membership_permission_codes,
    permission_supports_object_scope,
)


@dataclass(frozen=True)
class FinancialAuthorityLink:
    label: str
    route: str
    permission: str
    source_label: str


FINANCIAL_AUTHORITIES = (
    FinancialAuthorityLink(
        "حسابداری",
        "accounting:dashboard",
        "accounting.view",
        "دفتر کل و اسناد حسابداری",
    ),
    FinancialAuthorityLink(
        "خزانه‌داری",
        "treasury:workbench",
        "treasury.view",
        "دریافت، پرداخت و موجودی نقد",
    ),
    FinancialAuthorityLink(
        "دریافتنی‌ها و پرداختنی‌ها",
        "subledgers:workbench",
        "subledgers.view",
        "تعهدات دریافتنی و پرداختنی",
    ),
    FinancialAuthorityLink(
        "دارایی‌های ثابت مالی",
        "fixed_assets:workbench",
        "fixed_assets.view",
        "دارایی ثابت و استهلاک",
    ),
    FinancialAuthorityLink("هزینه‌ها", "expenses:list", "expenses.view", "اسناد هزینه"),
    FinancialAuthorityLink(
        "گزارش‌ها",
        "reporting:dashboard",
        "reporting.metric_result.view",
        "نمایش خواندنی منابع حوزه‌ها",
    ),
)


def authorized_financial_authorities(*, user, organization):
    membership = get_active_membership(user=user, organization=organization)
    codes = membership_permission_codes(membership)
    return tuple(
        link
        for link in FINANCIAL_AUTHORITIES
        if link.permission in codes
        and membership_has_scope(
            membership,
            allow_any_scope=permission_supports_object_scope(link.permission),
        )
    )
