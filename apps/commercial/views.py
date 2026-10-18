"""Tenant-scoped Commercial Tender/Bid workspace."""

from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.commercial.forms import (
    TenderBidCreateForm,
    TenderBidEvidenceForm,
    TenderBidRevisionForm,
    TenderBidTransitionForm,
)
from apps.commercial.models import TenderBidActivation, TenderBidStatus
from apps.commercial.services import (
    TRANSITIONS,
    create_tender_bid,
    get_tender_bid,
    link_tender_evidence,
    list_tender_bids,
    revise_tender_bid,
    transition_tender_bid,
)
from apps.documents.models import DocumentVersion
from apps.documents.services import get_organization_document
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode as P


def _tender(request: HttpRequest, tender_id: str):
    try:
        return get_tender_bid(
            actor=request.user,
            organization=request.organization,
            tender_id=tender_id,
        )
    except PermissionDenied as exc:
        raise Http404("مناقصه مجاز یافت نشد.") from exc


def _context(request: HttpRequest, tender):
    revisions = list(tender.revisions.select_related("created_by").order_by("-version"))
    latest = revisions[0]
    evidence = []
    for revision in revisions:
        for link in revision.evidence_links.select_related(
            "document_version__document"
        ):
            try:
                document = get_organization_document(
                    user=request.user,
                    organization=request.organization,
                    document_id=str(link.document_version.document_id),
                )
            except PermissionDenied:
                continue
            evidence.append((link, document))
    transition_form = TenderBidTransitionForm()
    transition_form.fields["target"].choices = [
        (code, label)
        for code, label in TenderBidStatus.choices
        if code in TRANSITIONS[latest.status]
    ]
    return {
        "tender": tender,
        "latest": latest,
        "revisions": revisions,
        "evidence": evidence,
        "allowed_targets": TRANSITIONS[latest.status],
        "active_policy": TenderBidActivation.objects.filter(
            organization=request.organization,
            is_active=True,
        )
        .exclude(policy_reference="")
        .exists(),
        "revision_form": TenderBidRevisionForm(
            initial={
                "title": latest.title,
                "description": latest.description,
                "submission_reference": latest.submission_reference,
                "result_reference": latest.result_reference,
                "bid_bond_reference": latest.bid_bond_reference,
                "bid_cost_reference": latest.bid_cost_reference,
            }
        ),
        "transition_form": transition_form,
        "evidence_form": TenderBidEvidenceForm(),
    }


@active_organization_required
@organization_permission_required(P.TENDER_BIDS_VIEW)
@require_GET
def tender_list(request: HttpRequest) -> HttpResponse:
    tenders = list(
        list_tender_bids(actor=request.user, organization=request.organization)
    )
    rows = [
        (tender, tender.revisions.order_by("-version").first()) for tender in tenders
    ]
    return render(
        request,
        "commercial/tender_list.html",
        {
            "rows": rows,
            "active_policy": TenderBidActivation.objects.filter(
                organization=request.organization,
                is_active=True,
            )
            .exclude(policy_reference="")
            .exists(),
        },
    )


@active_organization_required
@organization_permission_required(P.TENDER_BIDS_PREPARE)
@require_http_methods(["GET", "POST"])
def tender_create(request: HttpRequest) -> HttpResponse:
    form = TenderBidCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            tender = create_tender_bid(
                actor=request.user,
                organization=request.organization,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("commercial:tender_detail", tender_id=tender.pk)
    return render(
        request,
        "commercial/tender_form.html",
        {"form": form},
        status=400 if request.method == "POST" else 200,
    )


@active_organization_required
@organization_permission_required(P.TENDER_BIDS_VIEW)
@require_GET
def tender_detail(request: HttpRequest, tender_id: str) -> HttpResponse:
    tender = _tender(request, tender_id)
    return render(request, "commercial/tender_detail.html", _context(request, tender))


@active_organization_required
@organization_permission_required(P.TENDER_BIDS_PREPARE)
@require_POST
def tender_revise(request: HttpRequest, tender_id: str) -> HttpResponse:
    tender = _tender(request, tender_id)
    context = _context(request, tender)
    form = TenderBidRevisionForm(request.POST)
    context["revision_form"] = form
    if form.is_valid():
        try:
            revise_tender_bid(
                actor=request.user,
                organization=request.organization,
                tender_id=str(tender.pk),
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("commercial:tender_detail", tender_id=tender.pk)
    return render(request, "commercial/tender_detail.html", context, status=400)


@active_organization_required
@organization_permission_required(P.TENDER_BIDS_TRANSITION)
@require_POST
def tender_transition(request: HttpRequest, tender_id: str) -> HttpResponse:
    tender = _tender(request, tender_id)
    context = _context(request, tender)
    form = TenderBidTransitionForm(request.POST)
    form.fields["target"].choices = [
        (code, label)
        for code, label in TenderBidStatus.choices
        if code in context["allowed_targets"]
    ]
    context["transition_form"] = form
    if form.is_valid():
        try:
            transition_tender_bid(
                actor=request.user,
                organization=request.organization,
                tender_id=str(tender.pk),
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("commercial:tender_detail", tender_id=tender.pk)
    return render(request, "commercial/tender_detail.html", context, status=400)


@active_organization_required
@organization_permission_required(P.TENDER_BIDS_PREPARE)
@require_POST
def tender_evidence(request: HttpRequest, tender_id: str) -> HttpResponse:
    tender = _tender(request, tender_id)
    context = _context(request, tender)
    form = TenderBidEvidenceForm(request.POST)
    context["evidence_form"] = form
    if form.is_valid():
        try:
            version = DocumentVersion.objects.get(
                pk=form.cleaned_data["document_version_id"]
            )
            link_tender_evidence(
                actor=request.user,
                organization=request.organization,
                tender_id=str(tender.pk),
                document_version=version,
                description=form.cleaned_data["description"],
            )
        except (DocumentVersion.DoesNotExist, PermissionDenied, ValueError) as exc:
            form.add_error(
                None,
                "نسخه سند مجاز یافت نشد."
                if isinstance(exc, DocumentVersion.DoesNotExist)
                else str(exc),
            )
        else:
            return redirect("commercial:tender_detail", tender_id=tender.pk)
    return render(request, "commercial/tender_detail.html", context, status=400)
