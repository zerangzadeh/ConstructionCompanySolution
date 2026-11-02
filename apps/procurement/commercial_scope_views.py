"""Thin HTTP adapters over explicit scope preparation and the existing addendum."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.materials.models import UnitOfMeasure
from apps.organizations.authorization import require_business_permission
from apps.organizations.decorators import active_organization_required
from apps.organizations.models import BusinessPermissionCode as P

from .commercial_scope_forms import RFQAddendumForm, ScopeDefinitionForm
from .commercial_scope_services import define_rfq_commercial_scope, latest_definition
from .rfq_services import issue_rfq_addendum
from .rfq_ui import preparation_error_text
from .rfq_workspace import _rfq


@active_organization_required
@require_http_methods(["GET", "POST"])
def scope_define(request: HttpRequest, rfq_id: str) -> HttpResponse:
    rfq = _rfq(request, rfq_id)
    require_business_permission(
        user=request.user,
        organization=request.organization,
        permission=P.RFQS_ADDENDUM if rfq.current_version_number else P.RFQS_CHANGE,
        project=rfq.project,
        message="اجازه تعریف دامنه خرید این استعلام را ندارید.",
    )
    if rfq.status not in ("draft", "submitted_for_issue", "issued"):
        raise PermissionDenied("در وضعیت فعلی تعریف دامنه خرید مجاز نیست.")
    definition = latest_definition(rfq, rfq.current_version_number + 1)
    form = ScopeDefinitionForm(
        request.POST if request.method == "POST" else None,
        rfq=rfq,
        definition=definition,
    )
    if request.method == "POST" and form.is_valid():
        replay = rfq.scope_definitions.filter(
            idempotency_key=form.cleaned_data["idempotency_key"]
        ).first()
        basis = replay or definition
        scopes = list(basis.payload["scopes"]) if basis else []
        code = form.entry["scope_code"]
        exists = any(row["scope_code"] == code for row in scopes)
        operation = request.POST.get("operation")
        if operation not in ("append", "replace") or (
            operation == "replace" and not exists
        ):
            form.add_error(
                None, "برای جایگزینی، عنوان یکی از دامنه‌های ثبت‌شده را وارد کنید."
            )
        elif operation == "append" and exists and replay is None:
            form.add_error(
                "scope_code",
                "این عنوان ثبت شده است؛ برای اصلاح از جایگزینی هم‌نام استفاده کنید.",
            )
        else:
            scopes = [row for row in scopes if row["scope_code"] != code] + [form.entry]
            try:
                define_rfq_commercial_scope(
                    organization=request.organization,
                    actor=request.user,
                    rfq=rfq,
                    version_number=form.cleaned_data["version_number"],
                    scopes=scopes,
                    expected_revision=form.cleaned_data["expected_revision"],
                    idempotency_key=form.cleaned_data["idempotency_key"],
                    expected_source_fingerprint=form.cleaned_data["source_fingerprint"],
                )
            except (PermissionDenied, ValidationError, ValueError) as exc:
                form.add_error(None, preparation_error_text(exc))
            else:
                return redirect("procurement:rfq_scope_define", rfq_id=rfq.pk)
    entries = []
    if definition:
        members = {
            str(item.pk): item
            for item in rfq.purchase_request.items.select_related(
                "material", "unit_of_measure"
            )
        }
        units = {
            str(unit.pk): unit.name
            for unit in UnitOfMeasure.objects.filter(organization=request.organization)
        }
        for row in definition.payload["scopes"]:
            entry = dict(
                row,
                unit_name=units.get(row["unit_of_measure_id"], ""),
                member_labels=[],
            )
            for member in row["lines"]:
                item = members.get(member["purchase_request_item_id"])
                if item:
                    entry["member_labels"].append(
                        f"{item.material.name} · {member['quantity']} {item.unit_of_measure.name}"
                    )
            entries.append(entry)
    return render(
        request,
        "procurement/scope_form.html",
        {
            "rfq": rfq,
            "form": form,
            "definition": definition,
            "definition_entries": entries,
        },
        status=400 if form.is_bound else 200,
    )


@active_organization_required
@require_http_methods(["GET", "POST"])
def rfq_addendum(request: HttpRequest, rfq_id: str) -> HttpResponse:
    rfq = _rfq(request, rfq_id)
    require_business_permission(
        user=request.user,
        organization=request.organization,
        permission=P.RFQS_ADDENDUM,
        project=rfq.project,
        message="اجازه صدور الحاقیه این استعلام را ندارید.",
    )
    if rfq.status != "issued":
        raise PermissionDenied("الحاقیه فقط برای استعلام صادرشده مجاز است.")
    form = RFQAddendumForm(request.POST if request.method == "POST" else None, rfq=rfq)
    if request.method == "POST" and form.is_valid():
        try:
            issue_rfq_addendum(
                organization=request.organization,
                actor=request.user,
                rfq=rfq,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            form.add_error(None, preparation_error_text(exc))
        else:
            return redirect("procurement:rfq_detail", rfq_id=rfq.pk)
    return render(
        request,
        "procurement/addendum_form.html",
        {"form": form, "rfq": rfq},
        status=400 if form.is_bound else 200,
    )
