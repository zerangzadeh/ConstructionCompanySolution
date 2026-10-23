from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from apps.organizations.authorization import has_business_permission, is_platform_admin
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode

from .forms import (
    CandidateForm,
    PromotionRequestForm,
    PublicationCorrectionForm,
    RecurrenceCorrectionForm,
    RecurrenceForm,
    ReuseCorrectionForm,
    ReuseForm,
    ReviewForm,
    SourceForm,
)
from .models import (
    KnowledgeCandidate,
    KnowledgePromotion,
    KnowledgePublicationVersion,
    KnowledgeRecurrenceEvidence,
    KnowledgeReuseEvidence,
    KnowledgeScope,
    KnowledgeSensitivity,
    PublicationStatus,
)
from .services import (
    approve_candidate,
    approve_platform_promotion,
    correct_recurrence,
    correct_reuse,
    create_candidate,
    create_publication_correction,
    get_publication_history,
    publish_candidate,
    publish_platform_promotion,
    record_recurrence,
    record_reuse,
    request_platform_promotion,
    review_candidate,
    review_platform_promotion,
    submit_candidate,
    withdraw_publication,
)


def _candidate_for_request(request, candidate_id):
    item = KnowledgeCandidate.objects.filter(
        pk=candidate_id, organization=request.organization
    ).first()
    if item is None:
        raise Http404
    return item


@require_GET
@active_organization_required
@organization_permission_required(BusinessPermissionCode.KNOWLEDGE_PUBLICATIONS_VIEW)
def catalogue(request):
    items = KnowledgePublicationVersion.objects.filter(
        Q(publication__organization=request.organization)
        | Q(publication__scope=KnowledgeScope.PLATFORM),
        status__in=[PublicationStatus.CURRENT, PublicationStatus.REVIEW_DUE],
    ).select_related("publication", "published_by")
    if not has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.KNOWLEDGE_SENSITIVE_PROVENANCE_VIEW,
    ):
        items = items.exclude(metadata__sensitivity=KnowledgeSensitivity.SENSITIVE)
    return render(
        request,
        "knowledge/catalogue.html",
        {
            "items": items[:50],
            "can_unpublished": has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.KNOWLEDGE_UNPUBLISHED_VIEW,
            ),
        },
    )


@require_GET
@active_organization_required
@organization_permission_required(BusinessPermissionCode.KNOWLEDGE_UNPUBLISHED_VIEW)
def candidates(request):
    return render(
        request,
        "knowledge/candidates.html",
        {
            "items": KnowledgeCandidate.objects.filter(
                organization=request.organization
            ).order_by("-updated_at")[:50],
            "form": CandidateForm(),
            "can_create": has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.KNOWLEDGE_CANDIDATES_CREATE,
            ),
        },
    )


@require_POST
@active_organization_required
def candidate_create(request):
    form = CandidateForm(request.POST)
    if form.is_valid():
        try:
            item = create_candidate(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValidationError) as error:
            messages.error(request, str(error))
        else:
            return redirect("knowledge:candidate_detail", candidate_id=item.pk)
    messages.error(request, "اطلاعات کاندید دانش معتبر نیست.")
    return redirect("knowledge:candidates")


@require_GET
@active_organization_required
@organization_permission_required(BusinessPermissionCode.KNOWLEDGE_UNPUBLISHED_VIEW)
def candidate_detail(request, candidate_id):
    item = _candidate_for_request(request, candidate_id)
    return render(
        request,
        "knowledge/candidate_detail.html",
        {
            "item": item,
            "source_form": SourceForm(),
            "review_form": ReviewForm(initial={"expected_status": item.status}),
            "can_submit": has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.KNOWLEDGE_CANDIDATES_SUBMIT,
            ),
            "can_review": has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.KNOWLEDGE_CANDIDATES_REVIEW,
            ),
            "can_approve": has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.KNOWLEDGE_PUBLICATIONS_APPROVE,
            ),
            "can_publish": has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.KNOWLEDGE_PUBLICATIONS_PUBLISH,
            ),
        },
    )


@require_POST
@active_organization_required
def candidate_submit(request, candidate_id):
    item = _candidate_for_request(request, candidate_id)
    form = SourceForm(request.POST)
    if form.is_valid():
        try:
            submit_candidate(
                organization=request.organization,
                actor=request.user,
                candidate_id=item.pk,
                expected_status=item.status,
                sources=[form.cleaned_data],
            )
            messages.success(request, "نسخه کاندید برای بررسی ارسال شد.")
        except (
            PermissionDenied,
            ValidationError,
            KnowledgeCandidate.DoesNotExist,
        ) as error:
            messages.error(request, str(error))
    else:
        messages.error(request, "منبع انتخاب‌شده معتبر نیست.")
    return redirect("knowledge:candidate_detail", candidate_id=item.pk)


@require_POST
@active_organization_required
def candidate_review(request, candidate_id):
    item = _candidate_for_request(request, candidate_id)
    form = ReviewForm(request.POST)
    if form.is_valid():
        try:
            review_candidate(
                organization=request.organization,
                actor=request.user,
                candidate_id=item.pk,
                **form.cleaned_data,
            )
            messages.success(request, "بررسی ثبت شد.")
        except (PermissionDenied, ValidationError) as error:
            messages.error(request, str(error))
    return redirect("knowledge:candidate_detail", candidate_id=item.pk)


@require_POST
@active_organization_required
def candidate_approve(request, candidate_id):
    item = _candidate_for_request(request, candidate_id)
    try:
        approve_candidate(
            organization=request.organization,
            actor=request.user,
            candidate_id=item.pk,
            expected_status=request.POST.get("expected_status", ""),
        )
        messages.success(request, "کاندید برای انتشار تأیید شد.")
    except (PermissionDenied, ValidationError) as error:
        messages.error(request, str(error))
    return redirect("knowledge:candidate_detail", candidate_id=item.pk)


@require_POST
@active_organization_required
def candidate_publish(request, candidate_id):
    item = _candidate_for_request(request, candidate_id)
    try:
        version = publish_candidate(
            organization=request.organization,
            actor=request.user,
            candidate_id=item.pk,
            expected_status=request.POST.get("expected_status", ""),
            supersedes_id=item.corrects_version_id,
        )
        return redirect("knowledge:publication_detail", version_id=version.pk)
    except (PermissionDenied, ValidationError) as error:
        messages.error(request, str(error))
    return redirect("knowledge:candidate_detail", candidate_id=item.pk)


@require_GET
@active_organization_required
@organization_permission_required(BusinessPermissionCode.KNOWLEDGE_PUBLICATIONS_VIEW)
def publication_detail(request, version_id):
    item = (
        KnowledgePublicationVersion.objects.filter(
            Q(publication__organization=request.organization)
            | Q(publication__scope=KnowledgeScope.PLATFORM),
            pk=version_id,
        )
        .select_related("publication", "candidate_revision")
        .first()
    )
    if item is None:
        raise Http404
    return render(
        request,
        "knowledge/publication_detail.html",
        {
            "item": item,
            "reuse_form": ReuseForm(auto_id="reuse_%s"),
            "can_reuse": has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.KNOWLEDGE_REUSE_RECORD,
            ),
            "correction_form": PublicationCorrectionForm(
                auto_id="correction_%s",
                initial={"title": item.title, "body": item.body}
            ),
            "promotion_form": PromotionRequestForm(
                auto_id="promotion_%s",
                initial={
                    "title": item.title,
                    "body": item.body,
                    "audience": item.metadata.get("audience", ""),
                    "category_code": item.metadata.get("category", ""),
                }
            ),
            "can_withdraw": item.publication.scope == KnowledgeScope.TENANT
            and has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.KNOWLEDGE_PUBLICATIONS_WITHDRAW,
            ),
            "can_supersede": item.publication.scope == KnowledgeScope.TENANT
            and has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.KNOWLEDGE_PUBLICATIONS_SUPERSEDE,
            ),
            "can_promote": item.publication.scope == KnowledgeScope.TENANT
            and has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.KNOWLEDGE_PUBLICATIONS_PUBLISH,
            ),
            "can_history": has_business_permission(
                user=request.user,
                organization=request.organization,
                permission=BusinessPermissionCode.KNOWLEDGE_HISTORY_VIEW,
            ),
        },
    )


@require_POST
@active_organization_required
def publication_correct(request, version_id):
    form = PublicationCorrectionForm(request.POST)
    if form.is_valid():
        try:
            candidate = create_publication_correction(
                organization=request.organization,
                actor=request.user,
                version_id=version_id,
                **form.cleaned_data,
            )
            messages.success(request, "کاندید اصلاحی پیوندخورده ایجاد شد.")
            return redirect("knowledge:candidate_detail", candidate_id=candidate.pk)
        except (
            PermissionDenied,
            ValidationError,
            KnowledgePublicationVersion.DoesNotExist,
        ) as error:
            messages.error(request, str(error))
    else:
        messages.error(request, "متن و دلیل اصلاح معتبر نیست.")
    return redirect("knowledge:publication_detail", version_id=version_id)


@never_cache
@require_GET
@active_organization_required
def publication_history(request, version_id):
    try:
        item = get_publication_history(
            organization=request.organization,
            actor=request.user,
            version_id=version_id,
        )
    except (PermissionDenied, KnowledgePublicationVersion.DoesNotExist) as error:
        raise Http404 from error
    expose_sources = item.publication.scope == KnowledgeScope.TENANT
    return render(
        request,
        "knowledge/publication_history.html",
        {"item": item, "expose_sources": expose_sources},
    )


@require_POST
@active_organization_required
def publication_promote(request, version_id):
    form = PromotionRequestForm(request.POST)
    if form.is_valid():
        try:
            request_platform_promotion(
                organization=request.organization,
                actor=request.user,
                version_id=version_id,
                **form.cleaned_data,
            )
            messages.success(request, "درخواست پالایش‌شده ترویج به Platform ثبت شد.")
        except (
            PermissionDenied,
            ValidationError,
            KnowledgePublicationVersion.DoesNotExist,
        ) as error:
            messages.error(request, str(error))
    return redirect("knowledge:publication_detail", version_id=version_id)


@require_POST
@active_organization_required
def publication_withdraw(request, version_id):
    try:
        withdraw_publication(
            organization=request.organization,
            actor=request.user,
            version_id=version_id,
            expected_status=request.POST.get("expected_status", ""),
            reason=request.POST.get("reason", ""),
        )
        messages.success(request, "نسخه منتشرشده پس گرفته شد.")
    except (
        PermissionDenied,
        ValidationError,
        KnowledgePublicationVersion.DoesNotExist,
    ) as error:
        messages.error(request, str(error))
    return redirect("knowledge:catalogue")


@require_GET
@active_organization_required
@organization_permission_required(BusinessPermissionCode.KNOWLEDGE_RECURRENCE_RECORD)
def recurrence(request):
    return render(
        request,
        "knowledge/recurrence.html",
        {
            "form": RecurrenceForm(),
            "correction_form": RecurrenceCorrectionForm(),
            "items": KnowledgeRecurrenceEvidence.objects.filter(
                organization=request.organization
            ).prefetch_related("sources", "replacements")[:30],
        },
    )


@require_POST
@active_organization_required
def recurrence_record(request):
    form = RecurrenceForm(request.POST)
    if form.is_valid():
        try:
            record_recurrence(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
            messages.success(request, "شاهد تکرار ثبت شد.")
        except (PermissionDenied, ValidationError) as error:
            messages.error(request, str(error))
    return redirect("knowledge:recurrence")


@require_POST
@active_organization_required
def recurrence_correct(request, recurrence_id):
    form = RecurrenceCorrectionForm(request.POST)
    if form.is_valid():
        try:
            correct_recurrence(
                organization=request.organization,
                actor=request.user,
                recurrence_id=recurrence_id,
                **form.cleaned_data,
            )
            messages.success(request, "اصلاح تغییرناپذیر شاهد تکرار ثبت شد.")
        except (
            PermissionDenied,
            ValidationError,
            KnowledgeRecurrenceEvidence.DoesNotExist,
        ) as error:
            messages.error(request, str(error))
    else:
        messages.error(request, "اطلاعات اصلاح تکرار معتبر نیست.")
    return redirect("knowledge:recurrence")


@require_GET
@active_organization_required
@organization_permission_required(BusinessPermissionCode.KNOWLEDGE_REUSE_RECORD)
def reuse(request):
    return render(
        request,
        "knowledge/reuse.html",
        {
            "items": KnowledgeReuseEvidence.objects.filter(
                organization=request.organization
            )
            .select_related("publication_version")
            .prefetch_related("reversed_by")[:30],
            "correction_form": ReuseCorrectionForm(),
        },
    )


@require_POST
@active_organization_required
def reuse_record(request):
    form = ReuseForm(request.POST)
    if form.is_valid():
        try:
            record_reuse(
                organization=request.organization,
                actor=request.user,
                publication_version_id=request.POST.get("publication_version_id"),
                **form.cleaned_data,
            )
            messages.success(request, "شاهد استفاده مجدد ثبت شد.")
        except (
            PermissionDenied,
            ValidationError,
            KnowledgePublicationVersion.DoesNotExist,
        ) as error:
            messages.error(request, str(error))
    return redirect("knowledge:reuse")


@require_POST
@active_organization_required
def reuse_correct(request, reuse_id):
    form = ReuseCorrectionForm(request.POST)
    if form.is_valid():
        try:
            correct_reuse(
                organization=request.organization,
                actor=request.user,
                reuse_id=reuse_id,
                **form.cleaned_data,
            )
            messages.success(request, "اصلاح تغییرناپذیر استفاده مجدد ثبت شد.")
        except (
            PermissionDenied,
            ValidationError,
            KnowledgeReuseEvidence.DoesNotExist,
        ) as error:
            messages.error(request, str(error))
    return redirect("knowledge:reuse")


@require_GET
@login_required
def platform_promotions(request):
    if not is_platform_admin(request.user):
        raise PermissionDenied("فقط Platform Admin به صف ترویج دسترسی دارد.")
    return render(
        request,
        "knowledge/platform_promotions.html",
        {
            "items": KnowledgePromotion.objects.select_related(
                "requested_by", "reviewed_by", "approved_by"
            ).order_by("-created_at")[:50]
        },
    )


@require_POST
@login_required
def platform_promotion_review(request, promotion_id):
    try:
        review_platform_promotion(
            promotion_id=promotion_id,
            actor=request.user,
            outcome=request.POST.get("outcome", ""),
            reason=request.POST.get("reason", ""),
        )
        messages.success(request, "بررسی مستقل Platform ثبت شد.")
    except (
        PermissionDenied,
        ValidationError,
        KnowledgePromotion.DoesNotExist,
    ) as error:
        messages.error(request, str(error))
    return redirect("knowledge:platform_promotions")


@require_POST
@login_required
def platform_promotion_approve(request, promotion_id):
    try:
        approve_platform_promotion(promotion_id=promotion_id, actor=request.user)
        messages.success(request, "مشتق پالایش‌شده Platform تأیید شد.")
    except (
        PermissionDenied,
        ValidationError,
        KnowledgePromotion.DoesNotExist,
    ) as error:
        messages.error(request, str(error))
    return redirect("knowledge:platform_promotions")


@require_POST
@login_required
def platform_promotion_publish(request, promotion_id):
    try:
        publish_platform_promotion(promotion_id=promotion_id, actor=request.user)
        messages.success(request, "نسخه Platform منتشر شد.")
        return redirect("knowledge:platform_promotions")
    except (
        PermissionDenied,
        ValidationError,
        KnowledgePromotion.DoesNotExist,
    ) as error:
        messages.error(request, str(error))
    return redirect("knowledge:platform_promotions")
