from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.expenses.forms import ExpenseForm
from apps.expenses.services import create_expense, get_organization_expenses
from apps.organizations.decorators import active_organization_required


@active_organization_required
def expense_list(request: HttpRequest) -> HttpResponse:
    expenses = get_organization_expenses(
        user=request.user,
        organization=request.organization,
    )
    return render(request, "expenses/list.html", {"expenses": expenses})


@active_organization_required
def expense_create(request: HttpRequest) -> HttpResponse:
    form = ExpenseForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            create_expense(
                organization=request.organization,
                project=data["project"],
                actor=request.user,
                description=data["description"],
                amount=data["amount"],
                incurred_on=data["incurred_on"],
                category=data["category"],
                vendor_name=data["vendor_name"],
                receipt_reference=data["receipt_reference"],
                notes=data["notes"],
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("expenses:list")
    return render(request, "expenses/create.html", {"form": form})
