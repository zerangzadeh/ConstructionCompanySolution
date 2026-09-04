from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.organizations.decorators import active_organization_required
from apps.payments.forms import PaymentForm, PaymentVoidForm
from apps.payments.services import (
    create_payment,
    get_organization_payments,
    void_payment,
)


@active_organization_required
def payment_list(request: HttpRequest) -> HttpResponse:
    payments = get_organization_payments(
        user=request.user,
        organization=request.organization,
    )
    return render(request, "payments/list.html", {"payments": payments})


@active_organization_required
def payment_create(request: HttpRequest) -> HttpResponse:
    form = PaymentForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            create_payment(
                organization=request.organization,
                project=data["project"],
                contract=data["contract"],
                phase=data["phase"],
                actor=request.user,
                payment_number=data["payment_number"],
                direction=data["direction"],
                amount=data["amount"],
                paid_on=data["paid_on"],
                method=data["method"],
                counterparty_name=data["counterparty_name"],
                party=data["party"],
                reference=data["reference"],
                notes=data["notes"],
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("payments:list")
    return render(request, "payments/create.html", {"form": form})


@active_organization_required
def payment_detail(request: HttpRequest, payment_id: str) -> HttpResponse:
    payment = get_object_or_404(
        get_organization_payments(
            user=request.user,
            organization=request.organization,
        ),
        pk=payment_id,
    )
    form = PaymentVoidForm(request.POST or None)
    return render(
        request,
        "payments/detail.html",
        {"payment": payment, "form": form},
    )


@active_organization_required
def payment_void(request: HttpRequest, payment_id: str) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse(status=405)
    payment = get_object_or_404(
        get_organization_payments(
            user=request.user,
            organization=request.organization,
        ),
        pk=payment_id,
    )
    form = PaymentVoidForm(request.POST)
    if not form.is_valid():
        return render(
            request,
            "payments/detail.html",
            {"payment": payment, "form": form},
            status=400,
        )
    try:
        void_payment(
            payment=payment, actor=request.user, reason=form.cleaned_data["reason"]
        )
    except PermissionDenied as exc:
        form.add_error(None, str(exc))
        return render(
            request,
            "payments/detail.html",
            {"payment": payment, "form": form},
            status=403,
        )
    except ValueError as exc:
        form.add_error(None, str(exc))
        return render(
            request,
            "payments/detail.html",
            {"payment": payment, "form": form},
            status=400,
        )
    return redirect("payments:detail", payment_id=payment.pk)
