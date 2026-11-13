"""Scoped forms for Daily Report revision actions."""

from uuid import uuid4

from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_http_methods, require_POST

from apps.audit.models import AuditAction, AuditEvent
from apps.documents.services import (
    get_document_version_for_download,
    get_organization_document,
)
from apps.organizations.authorization import has_business_permission
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode as P
from apps.workflows.runtime import WorkflowConflict
from core.organization_time import render_in_organization_time as render
from core.product_surface import surface_profile

from .forms import (
    DailyActivityForm,
    DailyReportEquipmentEntryForm,
    DailyReportLaborEntryForm,
    DailyReportMaterialEntryForm,
    DelayEventForm,
    _DailyReportEntryForm,
)
from .models import DailyReport, DailyReportStatus
from .return_workflow import (
    adopt_submitted_report,
    resubmit_correction,
    return_daily_report,
    review_controls,
)
from .revision_services import (
    require_author,
    save_correction,
    scoped_permission,
    start_correction,
)
from .services import get_organization_daily_report
from .submission_snapshots import ENTRIES, HEADER_FIELDS, frozen_entries, frozen_label

ENTRY_FORMS = {
    "labor": DailyReportLaborEntryForm,
    "equipment": DailyReportEquipmentEntryForm,
    "materials": DailyReportMaterialEntryForm,
    "activities": DailyActivityForm,
    "delays": DelayEventForm,
}


class OperationForm(forms.Form):
    operation_key = forms.UUIDField(label="شناسه درخواست", widget=forms.HiddenInput, initial=uuid4)


class EditOperationForm(OperationForm):
    expected_version = forms.IntegerField(label="نسخه فرم", min_value=0, widget=forms.HiddenInput)


class ReasonForm(OperationForm):
    reason = forms.CharField(
        label="دلیل بازگشت برای اصلاح",
        max_length=1000,
        widget=forms.Textarea(
            attrs={"rows": 3, "class": "w-full rounded-lg border border-slate-300 p-2"}
        ),
    )


class AdoptionForm(ReasonForm):
    reason = forms.CharField(
        label="دلیل انتقال به بررسی مستقل",
        max_length=1000,
        widget=forms.Textarea(
            attrs={"rows": 3, "class": "w-full rounded-lg border border-slate-300 p-2"}
        ),
    )


class CorrectionHeaderForm(_DailyReportEntryForm):
    class Meta:
        model = DailyReport
        fields = HEADER_FIELDS
        widgets = {  # noqa: RUF012
            name: forms.Textarea(attrs={"rows": 2}) for name in HEADER_FIELDS[2:]
        }


def _report(request, report_id):
    return get_organization_daily_report(
        user=request.user,
        organization=request.organization,
        report_id=report_id,
    )


def _inputs(request, report_id):
    return {
        "organization": request.organization,
        "actor": request.user,
        "report_id": report_id,
    }


def _form_error(form, exc):
    if isinstance(exc, ValidationError):
        for message in exc.messages:
            form.add_error(None, message)
    else:
        form.add_error(None, str(exc))


def _pinned_documents(report, actor):
    snapshot = report.submission_snapshot
    if not snapshot and report.previous_revision_id:
        snapshot = report.previous_revision.submission_snapshot
    rows = []
    for pin in snapshot.get("documents", ()):
        try:
            document = get_organization_document(
                user=actor,
                organization=report.organization,
                document_id=pin["document_id"],
            )
        except PermissionDenied:
            continue
        try:
            version = get_document_version_for_download(
                document=document,
                version_id=pin["version_id"],
                actor=actor,
            )
        except PermissionDenied:
            version = None
        rows.append(
            {
                "title": pin["title"],
                "document_id": document.pk,
                "version_id": version.pk
                if version and version.sha256 == pin["sha256"]
                else None,
            }
        )
    return rows


def revision_context(report, actor, **bound):
    chain = []
    reasons = {}
    can_correct = False
    try:
        require_author(report, actor)
        can_correct = True
    except PermissionDenied:
        pass
    if report.submission_hash or report.previous_revision_id:
        chain = list(
            DailyReport.objects.filter(
                organization_id=report.organization_id,
                project_id=report.project_id,
                site_id=report.site_id,
                phase_id=report.phase_id,
                reporting_date=report.reporting_date,
            ).order_by("revision_number")
        )
        reasons = {
            event.entity_id: event.metadata.get("reason")
            for event in AuditEvent.objects.filter(
                organization_id=report.organization_id,
                entity_type="daily_report",
                action=AuditAction.DAILY_REPORT_RETURNED,
                entity_id__in=[str(row.pk) for row in chain],
            )
        }
    can_adopt = (
        surface_profile() == "MVP"
        and report.status == DailyReportStatus.SUBMITTED
        and not report.submission_hash
        and has_business_permission(
            user=actor,
            organization=report.organization,
            permission=P.WORKFLOWS_MIGRATE_INSTANCES,
            project=report.project,
            site=report.site,
        )
    )
    return {
        "revision_history": [(row, reasons.get(str(row.pk))) for row in chain],
        "return_reason": reasons.get(str(report.pk)),
        "show_return": review_controls(report, actor),
        "show_start_correction": (
            can_correct
            and report.status == DailyReportStatus.RETURNED
            and not any(row.previous_revision_id == report.pk for row in chain)
        ),
        "show_edit_correction": can_correct
        and report.previous_revision_id
        and report.status == DailyReportStatus.DRAFT,
        "show_adopt": can_adopt,
        "can_resubmit_correction": has_business_permission(
            user=actor,
            organization=report.organization,
            permission=P.DAILY_REPORTS_SUBMIT,
            project=report.project,
            site=report.site,
        ),
        "return_form": ReasonForm(auto_id="return-%s"),
        "adoption_form": AdoptionForm(auto_id="adoption-%s"),
        "start_correction_form": OperationForm(auto_id="correction-start-%s"),
        "revision_documents": _pinned_documents(report, actor),
        "report_project_label": frozen_label(report, "project"),
        "report_site_label": frozen_label(report, "site"),
        "report_phase_label": frozen_label(report, "phase"),
        **{f"{kind}_rows": frozen_entries(report, kind) for kind in ENTRIES},
        **bound,
    }


def _detail_action(request, report_id, form_class, service, context_key):
    from .views import _render_daily_report_detail

    report = _report(request, report_id)
    if context_key == "return_form" and not review_controls(report, request.user):
        if not AuditEvent.objects.filter(
            organization=request.organization,
            entity_type="daily_report",
            entity_id=str(report.pk),
            actor=request.user,
            action=AuditAction.DAILY_REPORT_RETURNED,
        ).exists():
            raise PermissionDenied
        scoped_permission(report, request.user, P.DAILY_REPORTS_APPROVE)
    if context_key == "adoption_form":
        if surface_profile() != "MVP":
            raise PermissionDenied
        scoped_permission(report, request.user, P.WORKFLOWS_MIGRATE_INSTANCES)
    form = form_class(request.POST, auto_id=f"{context_key}-%s")
    status = 400
    if form.is_valid():
        try:
            result = service(**_inputs(request, report_id), **form.cleaned_data)
        except PermissionDenied:
            raise
        except (ValidationError, WorkflowConflict) as exc:
            _form_error(form, exc)
            status = 409 if isinstance(exc, WorkflowConflict) else 400
        else:
            return redirect("daily_reports:detail", report_id=result.pk)
    response = _render_daily_report_detail(request, report, **{context_key: form})
    response.status_code = status
    return response


@active_organization_required
@organization_permission_required(P.DAILY_REPORTS_APPROVE)
@require_POST
def return_report(request, report_id):
    return _detail_action(
        request, report_id, ReasonForm, return_daily_report, "return_form"
    )


@active_organization_required
@organization_permission_required(P.WORKFLOWS_MIGRATE_INSTANCES)
@require_POST
def adopt_report(request, report_id):
    return _detail_action(
        request, report_id, AdoptionForm, adopt_submitted_report, "adoption_form"
    )


@active_organization_required
@organization_permission_required(P.DAILY_REPORTS_CORRECT)
@require_POST
def begin_correction(request, report_id):
    report = _report(request, report_id)
    require_author(report, request.user)
    form = OperationForm(request.POST)
    if not form.is_valid():
        return HttpResponse("شناسه درخواست معتبر نیست.", status=400)
    try:
        result = start_correction(**_inputs(request, report_id), **form.cleaned_data)
    except (ValidationError, WorkflowConflict) as exc:
        return HttpResponse(str(exc), status=409)
    return redirect("daily_reports:correction", report_id=result.pk)


def _correction_page(
    request, report, *, header=None, token=None, status=200, submit_error=""
):
    return_event = AuditEvent.objects.filter(
        organization_id=report.organization_id,
        entity_type="daily_report",
        entity_id=str(report.previous_revision_id),
        action=AuditAction.DAILY_REPORT_RETURNED,
    ).first()
    sections = [
        {
            "kind": kind,
            "label": spec.label,
            "rows": [
                (
                    row,
                    getattr(
                        row,
                        {
                            "labor": "team_name",
                            "equipment": "equipment_name",
                            "materials": "material_name",
                            "activities": "description",
                            "delays": "cause",
                        }[kind],
                    ),
                )
                for row in getattr(report, spec.relation).all()
            ],
            "can_add": has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=spec.permission,
                project=report.project,
                site=report.site,
            ),
        }
        for kind, spec in ENTRIES.items()
    ]
    return render(
        request,
        "daily_reports/correction.html",
        {
            "report": report,
            "header": header or CorrectionHeaderForm(instance=report),
            "token": token
            or EditOperationForm(initial={"expected_version": report.edit_version}),
            "submit_token": EditOperationForm(
                initial={"expected_version": report.edit_version}, auto_id="resubmit-%s"
            ),
            "sections": sections,
            "submit_error": submit_error,
            "return_reason": return_event.metadata["reason"] if return_event else "",
            "can_submit": has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=P.DAILY_REPORTS_SUBMIT,
                project=report.project,
                site=report.site,
            ),
        },
        status=status,
    )


@active_organization_required
@organization_permission_required(P.DAILY_REPORTS_CORRECT)
@require_http_methods(["GET", "POST"])
def correction(request, report_id):
    report = _report(request, report_id)
    require_author(report, request.user)
    if not report.previous_revision_id:
        raise PermissionDenied
    if request.method == "POST":
        token = EditOperationForm(request.POST)
        form = CorrectionHeaderForm(request.POST, instance=report)
        if token.is_valid() and form.is_valid():
            try:
                save_correction(
                    **_inputs(request, report_id),
                    **token.cleaned_data,
                    kind="header",
                    values=form.cleaned_data,
                )
            except (ValidationError, WorkflowConflict) as exc:
                _form_error(form, exc)
                return _correction_page(
                    request, report, header=form, token=token, status=409
                )
            return redirect("daily_reports:correction", report_id=report_id)
        return _correction_page(request, report, header=form, token=token, status=400)
    if report.status != DailyReportStatus.DRAFT:
        return redirect("daily_reports:detail", report_id=report_id)
    return _correction_page(request, report)


@active_organization_required
@organization_permission_required(P.DAILY_REPORTS_CORRECT)
@require_http_methods(["GET", "POST"])
def correction_entry(request, report_id, kind, entry_id=None):
    report = _report(request, report_id)
    require_author(report, request.user)
    spec = ENTRIES.get(kind)
    if not report.previous_revision_id or spec is None:
        raise PermissionDenied
    if entry_id is None and not has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=spec.permission,
        project=report.project,
        site=report.site,
    ):
        raise PermissionDenied
    token = EditOperationForm(
        request.POST if request.method == "POST" else None,
        initial={"expected_version": report.edit_version},
    )
    remove = request.method == "POST" and request.POST.get("action") == "remove"
    # Removal replay uses the receipt even after the row was deleted.
    if remove and token.is_valid():
        try:
            save_correction(
                **_inputs(request, report_id),
                **token.cleaned_data,
                kind=kind,
                entry_id=entry_id,
                values={},
                remove=True,
            )
        except (ValidationError, WorkflowConflict) as exc:
            return _correction_page(request, report, status=409, submit_error=str(exc))
        return redirect("daily_reports:correction", report_id=report_id)
    if report.status != DailyReportStatus.DRAFT and request.method != "POST":
        return redirect("daily_reports:detail", report_id=report_id)
    instance = (
        spec.model.objects.filter(
            pk=entry_id, organization=request.organization, report=report
        ).first()
        if entry_id
        else None
    )
    if entry_id and instance is None:
        raise PermissionDenied
    kwargs = {}
    if kind in ("activities", "delays"):
        kwargs["report"] = report
    if kind == "materials":
        kwargs["organization_id"] = report.organization_id
    form = ENTRY_FORMS[kind](
        request.POST if request.method == "POST" else None,
        instance=instance,
        **kwargs,
    )
    if kind == "labor":
        del form.fields["operation_key"]
    status = 200
    if request.method == "POST":
        status = 400
        if token.is_valid() and form.is_valid():
            try:
                save_correction(
                    **_inputs(request, report_id),
                    **token.cleaned_data,
                    kind=kind,
                    entry_id=entry_id,
                    values=form.cleaned_data,
                )
            except (ValidationError, WorkflowConflict) as exc:
                _form_error(form, exc)
                status = 409
            else:
                return redirect("daily_reports:correction", report_id=report_id)
    return render(
        request,
        "daily_reports/correction_entry.html",
        {
            "form": form,
            "token": token,
            "label": spec.label,
            "report": report,
            "entry_id": entry_id,
        },
        status=status,
    )


@active_organization_required
@organization_permission_required(P.DAILY_REPORTS_CORRECT)
@require_POST
def submit_correction(request, report_id):
    report = _report(request, report_id)
    require_author(report, request.user)
    token = EditOperationForm(request.POST)
    if not token.is_valid():
        return _correction_page(
            request,
            report,
            status=400,
            submit_error="شناسه یا نسخه درخواست معتبر نیست.",
        )
    try:
        result = resubmit_correction(
            **_inputs(request, report_id), **token.cleaned_data
        )
    except (ValidationError, WorkflowConflict) as exc:
        return _correction_page(request, report, status=409, submit_error=str(exc))
    return redirect("daily_reports:detail", report_id=result.pk)
