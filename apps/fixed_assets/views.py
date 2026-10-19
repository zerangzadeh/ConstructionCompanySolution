from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.audit.models import AuditEvent
from apps.fixed_assets.forms import (
    AssetClassForm,
    AssetForm,
    AssetTransactionForm,
    BookPolicyForm,
    CapitalizeForm,
    DepreciationPreviewForm,
    HandoffForm,
    ReconciliationForm,
    ReversalForm,
    SourceForm,
)
from apps.fixed_assets.models import (
    AssetBookPolicyVersion,
    AssetSourceReference,
    AssetTransaction,
    DepreciationRun,
    FixedAsset,
    FixedAssetClassVersion,
    FixedAssetSourceEnvelope,
)
from apps.fixed_assets.services import (
    add_asset_source,
    capitalize_asset,
    create_asset_class,
    create_book_policy,
    finalize_asset_transaction,
    finalize_depreciation,
    prepare_asset,
    prepare_asset_transaction,
    prepare_handoff,
    preview_depreciation,
    publish_policy,
    reconcile_handoff,
    reverse_asset_transaction,
    reverse_depreciation,
    review_asset_source,
    review_handoff,
    review_policy,
)
from apps.fixed_assets.workspace import (
    asset_accounting_targets,
    asset_operational_links,
    visible_assets,
)
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode


@active_organization_required
@organization_permission_required(BusinessPermissionCode.FIXED_ASSETS_VIEW)
def workbench(request: HttpRequest) -> HttpResponse:
    organization = request.organization
    return render(
        request,
        "fixed_assets/workbench.html",
        {
            "assets": visible_assets(
                organization=organization, actor=request.user
            ).select_related("asset_class", "book_policy", "project")[:100],
            "workspace_observed_at": timezone.now(),
            "classes": FixedAssetClassVersion.objects.filter(organization=organization)[
                :50
            ],
            "books": AssetBookPolicyVersion.objects.filter(organization=organization)[
                :50
            ],
            "runs": DepreciationRun.objects.filter(
                organization=organization
            ).select_related("fiscal_period", "book_policy")[:50],
            "transactions": AssetTransaction.objects.filter(
                organization=organization
            ).select_related("asset")[:100],
            "envelopes": FixedAssetSourceEnvelope.objects.filter(
                organization=organization
            ).select_related(
                "asset_transaction__asset",
                "depreciation_line__asset",
                "depreciation_line__run__fiscal_period",
            )[:100],
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.FIXED_ASSETS_VIEW)
@require_GET
def asset_detail(request: HttpRequest, asset_id) -> HttpResponse:
    asset = get_object_or_404(
        visible_assets(
            organization=request.organization, actor=request.user
        ).select_related("asset_class", "book_policy", "project", "site"),
        pk=asset_id,
    )
    return render(
        request,
        "fixed_assets/asset_detail.html",
        {
            "asset": asset,
            "operational_links": asset_operational_links(
                organization=request.organization, actor=request.user, asset=asset
            ),
            "accounting_targets": asset_accounting_targets(
                organization=request.organization, actor=request.user, asset=asset
            ),
            "sources": asset.source_references.filter(
                organization=request.organization
            ),
            "workspace_observed_at": timezone.now(),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.FIXED_ASSET_AUDIT_VIEW)
def audit_evidence(request: HttpRequest) -> HttpResponse:
    events = AuditEvent.objects.filter(
        organization=request.organization,
        entity_type__in=[
            "fixed_asset_policy",
            "fixed_asset",
            "fixed_asset_transaction",
            "fixed_asset_depreciation",
            "fixed_asset_handoff",
        ],
    ).select_related("actor")[:200]
    return render(
        request,
        "fixed_assets/audit_evidence.html",
        {"events": events},
    )


def _form_view(request, form, title, service):
    if request.method == "POST" and form.is_valid():
        try:
            service(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("fixed_assets:workbench")
    return render(request, "fixed_assets/form.html", {"form": form, "title": title})


@active_organization_required
@organization_permission_required(
    BusinessPermissionCode.FIXED_ASSET_CLASS_POLICY_MANAGE
)
def class_create(request):
    return _form_view(
        request,
        AssetClassForm(request.POST or None),
        "طبقه دارایی ثابت",
        create_asset_class,
    )


@active_organization_required
@organization_permission_required(
    BusinessPermissionCode.FIXED_ASSET_CLASS_POLICY_MANAGE
)
def book_create(request):
    return _form_view(
        request,
        BookPolicyForm(request.POST or None),
        "سیاست کتاب دارایی",
        create_book_policy,
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.FIXED_ASSET_CANDIDATE_PREPARE)
def asset_create(request):
    return _form_view(
        request,
        AssetForm(request.POST or None, organization=request.organization),
        "نامزد دارایی ثابت",
        prepare_asset,
    )


@active_organization_required
@organization_permission_required(
    BusinessPermissionCode.FIXED_ASSET_CLASS_POLICY_PUBLISH
)
@require_POST
def policy_transition(request, policy_id, kind, action):
    model = (
        FixedAssetClassVersion
        if kind == "class"
        else AssetBookPolicyVersion
        if kind == "book"
        else None
    )
    if model is None:
        raise Http404
    policy = get_object_or_404(model, pk=policy_id, organization=request.organization)
    service = (
        review_policy
        if action == "review"
        else publish_policy
        if action == "publish"
        else None
    )
    if service is None:
        raise Http404
    try:
        service(organization=request.organization, actor=request.user, policy=policy)
    except (PermissionDenied, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("fixed_assets:workbench")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.FIXED_ASSET_CANDIDATE_PREPARE)
def source_create(request, asset_id):
    asset = get_object_or_404(
        FixedAsset, pk=asset_id, organization=request.organization
    )
    form = SourceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            add_asset_source(
                organization=request.organization,
                actor=request.user,
                asset=asset,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("fixed_assets:workbench")
    return render(
        request, "fixed_assets/form.html", {"form": form, "title": "منبع دارایی"}
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.FIXED_ASSET_CANDIDATE_REVIEW)
@require_POST
def source_review(request, source_id):
    source = get_object_or_404(
        AssetSourceReference, pk=source_id, organization=request.organization
    )
    try:
        review_asset_source(
            organization=request.organization, actor=request.user, source=source
        )
    except (PermissionDenied, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("fixed_assets:workbench")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.FIXED_ASSET_CAPITALIZE)
def asset_capitalize(request, asset_id):
    asset = get_object_or_404(
        FixedAsset, pk=asset_id, organization=request.organization
    )
    form = CapitalizeForm(request.POST or None, asset=asset)
    if request.method == "POST" and form.is_valid():
        try:
            capitalize_asset(
                organization=request.organization,
                actor=request.user,
                asset=asset,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("fixed_assets:workbench")
    return render(
        request,
        "fixed_assets/form.html",
        {"form": form, "title": "سرمایه‌ای‌کردن دارایی"},
    )


@active_organization_required
@organization_permission_required(
    BusinessPermissionCode.FIXED_ASSET_DEPRECIATION_PREVIEW
)
def depreciation_preview(request):
    return _form_view(
        request,
        DepreciationPreviewForm(
            request.POST or None, organization=request.organization
        ),
        "پیش‌نمایش استهلاک",
        preview_depreciation,
    )


@active_organization_required
@organization_permission_required(
    BusinessPermissionCode.FIXED_ASSET_DEPRECIATION_FINALIZE
)
@require_POST
def depreciation_finalize(request, run_id):
    run = get_object_or_404(
        DepreciationRun, pk=run_id, organization=request.organization
    )
    try:
        finalize_depreciation(
            organization=request.organization, actor=request.user, run=run
        )
    except (PermissionDenied, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("fixed_assets:workbench")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.FIXED_ASSETS_VIEW)
def transaction_create(request):
    return _form_view(
        request,
        AssetTransactionForm(request.POST or None, organization=request.organization),
        "رویداد دارایی ثابت",
        prepare_asset_transaction,
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.FIXED_ASSET_TRANSACTION_REVIEW)
@require_POST
def transaction_finalize(request, transaction_id):
    transaction_record = get_object_or_404(
        AssetTransaction, pk=transaction_id, organization=request.organization
    )
    try:
        finalize_asset_transaction(
            organization=request.organization,
            actor=request.user,
            transaction_record=transaction_record,
        )
    except (PermissionDenied, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("fixed_assets:workbench")


@active_organization_required
@organization_permission_required(
    BusinessPermissionCode.FIXED_ASSET_TRANSACTION_REVERSE
)
def transaction_reverse(request, transaction_id):
    transaction_record = get_object_or_404(
        AssetTransaction, pk=transaction_id, organization=request.organization
    )
    form = ReversalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            reverse_asset_transaction(
                organization=request.organization,
                actor=request.user,
                transaction_record=transaction_record,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("fixed_assets:workbench")
    return render(
        request,
        "fixed_assets/form.html",
        {"form": form, "title": "برگشت رویداد دارایی"},
    )


@active_organization_required
@organization_permission_required(
    BusinessPermissionCode.FIXED_ASSET_DEPRECIATION_REVERSE
)
def depreciation_reverse(request, run_id):
    run = get_object_or_404(
        DepreciationRun, pk=run_id, organization=request.organization
    )
    form = ReversalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            reverse_depreciation(
                organization=request.organization,
                actor=request.user,
                run=run,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("fixed_assets:workbench")
    return render(
        request,
        "fixed_assets/form.html",
        {"form": form, "title": "برگشت اجرای استهلاک"},
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.FIXED_ASSET_HANDOFF_PREPARE)
def handoff_create(request):
    return _form_view(
        request,
        HandoffForm(request.POST or None, organization=request.organization),
        "پیشنهاد تحویل دارایی ثابت",
        prepare_handoff,
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.FIXED_ASSET_HANDOFF_REVIEW)
@require_POST
def handoff_review(request, envelope_id):
    envelope = get_object_or_404(
        FixedAssetSourceEnvelope, pk=envelope_id, organization=request.organization
    )
    try:
        review_handoff(
            organization=request.organization, actor=request.user, envelope=envelope
        )
    except (PermissionDenied, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("fixed_assets:workbench")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.FIXED_ASSET_HANDOFF_RECONCILE)
def handoff_reconcile(request, envelope_id):
    envelope = get_object_or_404(
        FixedAssetSourceEnvelope, pk=envelope_id, organization=request.organization
    )
    form = ReconciliationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            reconcile_handoff(
                organization=request.organization,
                actor=request.user,
                envelope=envelope,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("fixed_assets:workbench")
    return render(
        request,
        "fixed_assets/form.html",
        {"form": form, "title": "تطبیق پیشنهاد دارایی ثابت"},
    )
