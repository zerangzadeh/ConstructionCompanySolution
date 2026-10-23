import uuid

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from apps.expenses.forms import (
    ExpenseAllocationForm,
    ExpenseCategoryForm,
    ExpenseDraftForm,
    ExpenseForm,
    ExpenseReturnForm,
    ExpenseVoidForm,
    PlatformExpenseGroupForm,
    RecurringExpenseProposalForm,
    RecurringExpenseTemplateForm,
)
from apps.expenses.models import (
    ExpenseCategory,
    PlatformExpenseGroup,
)
from apps.expenses.services import (
    add_expense_allocation,
    approve_expense,
    archive_expense_category,
    archive_platform_expense_group,
    create_expense,
    create_expense_category,
    create_expense_draft,
    create_platform_expense_group,
    create_recurring_expense_template,
    get_organization_expense_categories,
    get_organization_expenses,
    get_platform_expense_groups,
    propose_recurring_expense,
    return_expense,
    submit_expense,
    update_expense_category,
    update_platform_expense_group,
    void_expense,
)
from apps.organizations.authorization import (
    get_active_membership,
    has_business_permission,
    is_platform_admin,
    scope_queryset,
)
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
    require_organization_permission,
)
from apps.organizations.models import BusinessPermissionCode
from core.list_filters import (
    apply_table_filters,
    build_table_filters,
    has_active_table_filters,
    paginate_table,
    table_pagination_query,
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
        choice_fields={
            "category": (
                "category",
                PlatformExpenseGroup.objects.filter(
                    is_active=True,
                    archived_at__isnull=True,
                ).values_list("code", flat=True),
            )
        },
        date_fields={"incurred_on": "incurred_on"},
    )
    page = paginate_table(
        expenses,
        request,
        sort_fields={
            "description": "description",
            "project": "project__name",
            "category": "category",
            "incurred_on": "incurred_on",
            "amount": "amount",
        },
        default_ordering=("-incurred_on", "-created_at", "pk"),
    )
    return render(
        request,
        "expenses/list.html",
        {
            "expenses": page.object_list,
            "page_obj": page,
            "pagination_query": table_pagination_query(request),
            "filters": build_table_filters(
                request,
                [
                    {"name": "description", "kind": "text", "label": "شرح هزینه"},
                    {"name": "project", "kind": "text", "label": "پروژه"},
                    {
                        "name": "category",
                        "kind": "select",
                        "label": "گروه اصلی هزینه",
                        "choices": [
                            (group.code, group.name)
                            for group in PlatformExpenseGroup.objects.filter(
                                is_active=True,
                                archived_at__isnull=True,
                            ).order_by("name")
                        ],
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
@organization_permission_required(BusinessPermissionCode.EXPENSE_CATEGORIES_VIEW)
def expense_category_list(request: HttpRequest) -> HttpResponse:
    categories = get_organization_expense_categories(
        user=request.user, organization=request.organization
    ).select_related("primary_group")
    return render(
        request,
        "expenses/category_list.html",
        {"categories": categories},
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EXPENSE_CATEGORIES_CREATE)
def expense_category_create(request: HttpRequest) -> HttpResponse:
    form = ExpenseCategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            create_expense_category(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("expenses:category_list")
    return render(
        request, "expenses/category_form.html", {"form": form, "category": None}
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EXPENSE_CATEGORIES_VIEW)
def expense_category_detail(request: HttpRequest, category_id: str) -> HttpResponse:
    category = get_object_or_404(
        ExpenseCategory.objects.filter(
            organization=request.organization, archived_at__isnull=True
        ),
        pk=category_id,
    )
    if request.method == "POST":
        require_organization_permission(
            request,
            BusinessPermissionCode.EXPENSE_CATEGORIES_CHANGE,
            "اجازه ویرایش دسته هزینه را ندارید.",
        )
    form = ExpenseCategoryForm(request.POST or None, instance=category)
    if request.method == "GET" and not has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.EXPENSE_CATEGORIES_CHANGE,
    ):
        for field in form.fields.values():
            field.disabled = True
    if request.method == "POST" and form.is_valid():
        try:
            update_expense_category(
                organization=request.organization,
                actor=request.user,
                category=category,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("expenses:category_detail", category_id=category.pk)
    return render(
        request, "expenses/category_form.html", {"form": form, "category": category}
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EXPENSE_CATEGORIES_ARCHIVE)
def expense_category_archive(request: HttpRequest, category_id: str) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse(status=405)
    category = get_object_or_404(
        ExpenseCategory.objects.filter(
            organization=request.organization, archived_at__isnull=True
        ),
        pk=category_id,
    )
    try:
        archive_expense_category(
            organization=request.organization, actor=request.user, category=category
        )
    except (PermissionDenied, ValueError) as exc:
        return HttpResponseForbidden(str(exc))
    return redirect("expenses:category_list")


def _require_platform_expense_group_access(request: HttpRequest) -> None:
    if not is_platform_admin(request.user):
        raise PermissionDenied("فقط مدیر پلتفرم به گروه‌های اصلی هزینه دسترسی دارد.")


@login_required
def platform_expense_group_list(request: HttpRequest) -> HttpResponse:
    _require_platform_expense_group_access(request)
    return render(
        request,
        "expenses/platform_group_list.html",
        {"groups": get_platform_expense_groups()},
    )


@login_required
def platform_expense_group_create(request: HttpRequest) -> HttpResponse:
    _require_platform_expense_group_access(request)
    form = PlatformExpenseGroupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            create_platform_expense_group(actor=request.user, **form.cleaned_data)
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("expenses:platform_group_list")
    return render(
        request, "expenses/platform_group_form.html", {"form": form, "group": None}
    )


@login_required
def platform_expense_group_detail(request: HttpRequest, group_id: str) -> HttpResponse:
    _require_platform_expense_group_access(request)
    group = get_object_or_404(PlatformExpenseGroup, pk=group_id)
    form = PlatformExpenseGroupForm(request.POST or None, instance=group)
    if request.method == "POST" and form.is_valid():
        try:
            update_platform_expense_group(
                actor=request.user, group=group, **form.cleaned_data
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("expenses:platform_group_detail", group_id=group.pk)
    return render(
        request, "expenses/platform_group_form.html", {"form": form, "group": group}
    )


@login_required
def platform_expense_group_archive(request: HttpRequest, group_id: str) -> HttpResponse:
    _require_platform_expense_group_access(request)
    if request.method != "POST":
        return HttpResponse(status=405)
    group = get_object_or_404(PlatformExpenseGroup, pk=group_id)
    try:
        archive_platform_expense_group(actor=request.user, group=group)
    except (PermissionDenied, ValueError) as exc:
        return HttpResponseForbidden(str(exc))
    return redirect("expenses:platform_group_list")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EXPENSES_CREATE)
def expense_create(request: HttpRequest) -> HttpResponse:
    membership = get_active_membership(
        user=request.user, organization=request.organization
    )
    form = ExpenseForm(
        request.POST or None,
        organization=request.organization,
        membership=membership,
        active_project=request.active_project,
    )
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
@organization_permission_required(BusinessPermissionCode.EXPENSES_CREATE)
def expense_draft_create(request: HttpRequest) -> HttpResponse:
    initial = {"idempotency_key": str(uuid.uuid4())}
    membership = get_active_membership(
        user=request.user, organization=request.organization
    )
    form = ExpenseDraftForm(
        request.POST or None,
        organization=request.organization,
        membership=membership,
        active_project=request.active_project,
        initial=initial,
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            expense = create_expense_draft(
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
                classification=data["classification"],
                source_reference=data["source_reference"],
                idempotency_key=data["idempotency_key"],
                receipt_reference=data["receipt_reference"],
                notes=data["notes"],
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("expenses:detail", expense_id=expense.pk)
    return render(request, "expenses/create.html", {"form": form, "is_draft": True})


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EXPENSES_VIEW)
def expense_detail(request: HttpRequest, expense_id: str) -> HttpResponse:
    expense = get_object_or_404(
        get_organization_expenses(user=request.user, organization=request.organization),
        pk=expense_id,
    )
    membership = get_active_membership(
        user=request.user, organization=request.organization
    )
    return render(
        request,
        "expenses/detail.html",
        {
            "expense": expense,
            "allocation_form": ExpenseAllocationForm(
                organization=request.organization, membership=membership
            ),
            "return_form": ExpenseReturnForm(),
            "void_form": ExpenseVoidForm(),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EXPENSES_ALLOCATE)
def expense_allocate(request: HttpRequest, expense_id: str) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse(status=405)
    expense = get_object_or_404(
        get_organization_expenses(user=request.user, organization=request.organization),
        pk=expense_id,
    )
    membership = get_active_membership(
        user=request.user, organization=request.organization
    )
    form = ExpenseAllocationForm(
        request.POST,
        organization=request.organization,
        membership=membership,
        expense=expense,
    )
    if not form.is_valid():
        return HttpResponse(status=400)
    try:
        add_expense_allocation(expense=expense, actor=request.user, **form.cleaned_data)
    except PermissionDenied:
        return HttpResponse(status=403)
    except ValueError:
        return HttpResponse(status=400)
    return redirect("expenses:detail", expense_id=expense.pk)


def _transition_expense(
    request: HttpRequest, expense_id: str, operation
) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse(status=405)
    expense = get_object_or_404(
        get_organization_expenses(user=request.user, organization=request.organization),
        pk=expense_id,
    )
    try:
        operation(expense=expense, actor=request.user)
    except PermissionDenied:
        return HttpResponse(status=403)
    except ValueError:
        return HttpResponse(status=400)
    return redirect("expenses:detail", expense_id=expense.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EXPENSES_SUBMIT)
def expense_submit(request: HttpRequest, expense_id: str) -> HttpResponse:
    return _transition_expense(request, expense_id, submit_expense)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EXPENSES_APPROVE)
def expense_approve(request: HttpRequest, expense_id: str) -> HttpResponse:
    return _transition_expense(request, expense_id, approve_expense)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EXPENSES_RETURN)
def expense_return(request: HttpRequest, expense_id: str) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse(status=405)
    expense = get_object_or_404(
        get_organization_expenses(user=request.user, organization=request.organization),
        pk=expense_id,
    )
    form = ExpenseReturnForm(request.POST)
    if not form.is_valid():
        return HttpResponse(status=400)
    try:
        return_expense(
            expense=expense, actor=request.user, reason=form.cleaned_data["reason"]
        )
    except PermissionDenied:
        return HttpResponse(status=403)
    except ValueError:
        return HttpResponse(status=400)
    return redirect("expenses:detail", expense_id=expense.pk)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EXPENSE_RECURRENCES_MANAGE)
def recurrence_list(request: HttpRequest) -> HttpResponse:
    membership = get_active_membership(
        user=request.user, organization=request.organization
    )
    templates = request.organization.recurringexpensetemplate_set.none()
    if membership is not None:
        templates = scope_queryset(
            request.organization.recurringexpensetemplate_set.select_related("project"),
            membership=membership,
            project_lookup="project_id",
        ).order_by("description")
    form = RecurringExpenseTemplateForm(
        request.POST or None,
        organization=request.organization,
        membership=membership,
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            create_recurring_expense_template(
                organization=request.organization, actor=request.user, **data
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("expenses:recurrences")
    return render(
        request,
        "expenses/recurrences.html",
        {
            "templates": templates,
            "form": form,
            "proposal_form": RecurringExpenseProposalForm(),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.EXPENSE_RECURRENCES_MANAGE)
def recurrence_propose(request: HttpRequest, template_id: str) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse(status=405)
    template = get_object_or_404(
        request.organization.recurringexpensetemplate_set.all(), pk=template_id
    )
    form = RecurringExpenseProposalForm(request.POST)
    if not form.is_valid():
        return HttpResponse(status=400)
    try:
        expense = propose_recurring_expense(
            template=template,
            occurrence_on=form.cleaned_data["occurrence_on"],
            actor=request.user,
        )
    except PermissionDenied:
        return HttpResponse(status=403)
    except ValueError:
        return HttpResponse(status=400)
    return redirect("expenses:detail", expense_id=expense.pk)


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
