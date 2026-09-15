from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.expenses.forms import ExpenseForm, ExpenseVoidForm
from apps.expenses.models import LegacyExpenseCategory
from apps.expenses.services import (
    create_expense,
    get_organization_expenses,
    void_expense,
)
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode
from core.list_filters import (
    apply_table_filters,
    build_table_filters,
    has_active_table_filters,
)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EXPENSES_VIEW)
def expense_list(request: HttpRequest) -> HttpResponse:
    expenses = get_organization_expenses(
        user=request.user,
        organization=request.organization,
    )
    expenses = apply_table_filters(
        expenses,
        request,
        text_fields={
            "description": ("description", "vendor_name", "receipt_reference"),
            "project": ("project__name", "phase__name"),
        },
        choice_fields={"category": ("category", LegacyExpenseCategory.values)},
        date_fields={"incurred_on": "incurred_on"},
    )
    return render(
        request,
        "expenses/list.html",
        {
            "expenses": expenses,
            "filters": build_table_filters(
                request,
                [
                    {"name": "description", "kind": "text", "label": "شرح هزینه"},
                    {"name": "project", "kind": "text", "label": "پروژه"},
                    {
                        "name": "category",
                        "kind": "select",
                        "label": "دسته‌بندی",
                        "choices": LegacyExpenseCategory.choices,
                    },
                    {"name": "incurred_on", "kind": "date_range", "label": "تاریخ"},
                    None,
                    None,
                ],
            ),
            "has_active_filters": has_active_table_filters(request),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EXPENSES_CREATE)
def expense_create(request: HttpRequest) -> HttpResponse:
    form = ExpenseForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            create_expense(
                organization=request.organization,
                project=data["project"],
                phase=data["phase"],
                actor=request.user,
                description=data["description"],
                amount=data["amount"],
                incurred_on=data["incurred_on"],
                category=data["category"],
                vendor_name=data["vendor_name"],
                party=data["party"],
                expense_category=data["expense_category"],
                receipt_reference=data["receipt_reference"],
                notes=data["notes"],
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("expenses:list")
    return render(request, "expenses/create.html", {"form": form})


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EXPENSES_VOID)
def expense_void(request: HttpRequest, expense_id: str) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse(status=405)
    expense = get_object_or_404(
        get_organization_expenses(
            user=request.user,
            organization=request.organization,
        ),
        pk=expense_id,
    )
    form = ExpenseVoidForm(request.POST)
    if not form.is_valid():
        return HttpResponse(status=400)
    try:
        void_expense(
            expense=expense,
            actor=request.user,
            reason=form.cleaned_data["reason"],
        )
    except PermissionDenied:
        return HttpResponse(status=403)
    except ValueError:
        return HttpResponse(status=400)
    return redirect("expenses:list")
