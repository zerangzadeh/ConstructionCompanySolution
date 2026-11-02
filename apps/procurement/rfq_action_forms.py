"""RFQ-bound presentation inputs for existing Procurement commands."""

from uuid import uuid4

from django import forms
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.forms import formset_factory
from django.http import Http404

from apps.organizations.authorization import has_business_permission
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import OrganizationMembership
from apps.procurement import models as m
from core.forms import JalaliDateMixin
from core.jalali import format_jalali

# Fixed presentation catalogue; permissions and transitions remain domain-owned.
ACTIONS = {
    "capture": (P.RFQ_QUOTES_CAPTURE, "ثبت پیشنهاد مهروموم‌شده"),
    "submit": (P.RFQ_QUOTES_SUBMIT, "ثبت نهایی پیشنهاد"),
    "withdraw": (P.RFQ_QUOTES_WITHDRAW, "بازپس‌گیری پیشنهاد"),
    "request_opening": (P.RFQ_QUOTES_OPEN, "درخواست گشایش"),
    "approve_opening": (P.RFQ_QUOTES_APPROVE_OPEN, "تأیید مستقل گشایش"),
    "grant_access": (P.RFQ_QUOTES_MANAGE_CONFIDENTIAL_ACCESS, "اعطای دسترسی نسخه"),
    "revoke_access": (P.RFQ_QUOTES_MANAGE_CONFIDENTIAL_ACCESS, "لغو دسترسی نسخه"),
    "prepare_admissibility": (P.RFQ_QUOTES_PREPARE_ADMISSIBILITY, "آماده‌سازی پذیرش"),
    "approve_admissibility": (P.RFQ_QUOTES_APPROVE_ADMISSIBILITY, "تأیید پذیرش"),
    "prepare_comparison": (P.RFQ_QUOTES_PREPARE_COMPARISON, "آماده‌سازی مقایسه"),
    "appoint_evaluator": (P.RFQ_QUOTES_PREPARE_COMPARISON, "تعیین ارزیاب"),
    "declare_conflict": (P.RFQ_QUOTES_EVALUATE_COMPARISON, "اعلام تعارض ارزیاب"),
    "dispose_conflict": (P.RFQ_QUOTES_DISPOSE_CONFLICT, "تعیین تکلیف مستقل تعارض"),
    "evaluate": (P.RFQ_QUOTES_EVALUATE_COMPARISON, "ثبت بررسی مستند"),
    "finalize_comparison": (P.RFQ_QUOTES_FINALIZE_COMPARISON, "نهایی‌سازی مقایسه"),
    "prepare_award": (P.RFQ_QUOTES_PREPARE_SOURCING_AWARD, "آماده‌سازی انتخاب"),
    "finalize_award": (P.RFQ_QUOTES_FINALIZE_SOURCING_AWARD, "نهایی‌سازی انتخاب"),
    "attach_evidence": (P.RFQS_CUSTODY_SEALED_EVIDENCE, "نگهداری اصل و پیوست پیشنهاد"),
}


def confidential_revisions(*, rfq, actor):
    """Read projection: exact active grants intersect permission, tenant and RFQ."""
    records = m.QuoteRevision.objects.filter(
        organization=rfq.organization, envelope__rfq=rfq
    )
    if not has_business_permission(
        user=actor,
        organization=rfq.organization,
        permission=P.RFQ_QUOTES_VIEW_CONFIDENTIAL,
        project=rfq.project,
    ):
        return records.none()
    grants = m.QuoteConfidentialAccessGrant.objects.filter(
        organization=rfq.organization,
        membership__user=actor,
        membership__status="active",
        revocation__isnull=True,
    ).values("quote_revision_id")
    return records.filter(pk__in=grants, opening_event__isnull=False)


def comparison_records(*, rfq, actor):
    records = m.CommercialComparison.objects.filter(
        organization=rfq.organization,
        commercial_scope__rfq_version__rfq=rfq,
    )
    # Never expose assertion/evaluation context from a version without a grant.
    return records.exclude(
        inputs__quote_revision__in=m.QuoteRevision.objects.exclude(
            pk__in=confidential_revisions(rfq=rfq, actor=actor).values("pk")
        )
    )


def choice(queryset, label, *, required=True, describe=None):
    field = forms.ModelChoiceField(queryset=queryset, label=label, required=required)
    if describe:
        field.label_from_instance = describe
    return field


def revision_label(revision):
    return f"{revision.envelope.supplier.display_name} · نسخه {revision.revision_number} · {revision.get_status_display()}"


def comparison_label(comparison):
    return f"{scope_label(comparison.commercial_scope)} · {comparison.get_status_display()} · {format_jalali(comparison.created_at, include_time=True)}"


def scope_label(scope):
    line = scope.rfq_version_line
    name = line.material.name if line else f"بسته {scope.scope_code}"
    return f"{name} · {scope.required_quantity} {scope.unit_of_measure.symbol} · نسخه استعلام {scope.rfq_version.version_number}"


class RFQActionForm(JalaliDateMixin, forms.Form):
    supplier_submitted_at = forms.DateTimeField(
        label="زمان ارائه تأمین‌کننده", required=False
    )

    def __init__(self, *args, rfq, actor, action, context=None, **kwargs):
        super().__init__(*args, **kwargs)
        org = rfq.organization
        revisions = m.QuoteRevision.objects.filter(
            organization=org, envelope__rfq=rfq
        ).select_related("envelope__supplier")
        confidential = confidential_revisions(rfq=rfq, actor=actor)
        comparisons = comparison_records(rfq=rfq, actor=actor).select_related(
            "commercial_scope"
        )
        members = OrganizationMembership.objects.filter(
            organization=org, status="active", user__is_active=True
        ).select_related("user")
        fields = self.fields
        if action != "capture":
            fields.pop("supplier_submitted_at")
        text = lambda label: forms.CharField(label=label, max_length=500)
        key = lambda: forms.CharField(
            max_length=128, initial=uuid4, widget=forms.HiddenInput
        )
        rev = lambda qs=revisions: choice(qs, "نسخه پیشنهاد", describe=revision_label)
        comp = lambda qs=comparisons: choice(qs, "مقایسه", describe=comparison_label)
        member = lambda: choice(
            members,
            "عضو فعال",
            describe=lambda x: x.user.get_full_name() or x.user.username,
        )
        if action == "capture":
            invitations = m.RequestForQuotationInvitation.objects.filter(
                organization=org,
                rfq_version__rfq=rfq,
                rfq_version__version_number=rfq.current_version_number,
            ).select_related("supplier")
            fields.update(
                {
                    "invitation": choice(
                        invitations,
                        "دعوت‌نامه",
                        describe=lambda x: x.supplier.display_name,
                    ),
                    "source_file": forms.FileField(
                        label="اصل فایل دریافتی برای ثبت رسید",
                        help_text="رسید از خود فایل محاسبه می‌شود. فایل در این مرحله نگهداری نمی‌شود؛ اصل آن را برای نگهداری حفاظت‌شده پس از بستن استعلام حفظ کنید.",
                    ),
                    "source_channel": forms.ChoiceField(
                        label="مسیر دریافت",
                        choices=[
                            x
                            for x in m.QuoteSourceChannel.choices
                            if x[0] != "external_portal"
                        ],
                    ),
                    "idempotency_key": key(),
                }
            )
        elif action == "attach_evidence":
            fields["quote_revision"] = rev(revisions.filter(status="submitted"))
            fields["evidence_type"] = forms.ChoiceField(
                label="نوع مدرک", choices=m.QuoteEvidenceType.choices
            )
            fields["upload"] = forms.FileField(label="فایل اصل یا پیوست")
            fields["idempotency_key"] = key()
        elif action in {
            "submit",
            "withdraw",
            "request_opening",
            "grant_access",
            "prepare_admissibility",
        }:
            targets = confidential if action == "prepare_admissibility" else revisions
            if action == "submit" and not (context and context.get("quote_revision")):
                targets = targets.filter(status="captured")
            elif action == "withdraw" and not (
                context and context.get("quote_revision")
            ):
                targets = targets.filter(status__in=["captured", "submitted"])
            elif action in {"request_opening", "grant_access"}:
                targets = targets.filter(status="submitted", is_late=False)
            fields["quote_revision"] = rev(targets)
            if action in {"request_opening", "grant_access"}:
                fields["reason"] = text("دلیل")
            if action == "grant_access":
                fields["membership"] = member()
                fields["membership"].queryset = members.exclude(user=actor)
            if action == "prepare_admissibility":
                fields.update(
                    {
                        "state": forms.ChoiceField(
                            label="نتیجه پذیرش",
                            choices=[
                                x
                                for x in m.QuoteEligibilityState.choices
                                if x[0] != "unreviewed"
                            ],
                        ),
                        "reason_code": forms.ChoiceField(
                            label="مبنای پذیرش",
                            choices=m.QuoteAdmissibilityReasonCode.choices,
                        ),
                        "rationale": text("شرح مستند"),
                    }
                )
            fields["idempotency_key"] = key()
        elif action == "approve_opening":
            fields["opening_request"] = choice(
                m.QuoteOpeningRequest.objects.filter(
                    organization=org, quote_revision__in=revisions
                ),
                "درخواست گشایش",
                describe=lambda x: f"{revision_label(x.quote_revision)} · {x.reason}",
            )
        elif action == "revoke_access":
            fields["grant"] = choice(
                m.QuoteConfidentialAccessGrant.objects.filter(
                    organization=org,
                    quote_revision__in=revisions,
                    **(
                        {}
                        if context and context.get("grant")
                        else {"revocation__isnull": True}
                    ),
                ),
                "دسترسی فعال",
                describe=lambda x: (
                    f"{revision_label(x.quote_revision)} · {x.membership.user.username}"
                ),
            )
            fields["reason"] = text("دلیل لغو")
        elif action == "approve_admissibility":
            fields["preparation"] = choice(
                m.QuoteAdmissibilityPreparation.objects.filter(
                    organization=org, quote_revision__in=confidential
                ),
                "آماده‌سازی پذیرش",
                describe=lambda x: (
                    f"{revision_label(x.quote_revision)} · {x.get_proposed_state_display()}"
                ),
            )
            fields["supersedes"] = choice(
                m.QuoteAdmissibilityDecision.objects.filter(
                    organization=org,
                    quote_revision__in=confidential,
                    superseded_by__isnull=True,
                ),
                "تصحیح تصمیم پیشین",
                required=False,
                describe=lambda x: (
                    f"{revision_label(x.quote_revision)} · {x.get_state_display()}"
                ),
            )
        elif action == "prepare_comparison":
            fields["scope"] = choice(
                m.RFQCommercialScope.objects.filter(
                    organization=org,
                    rfq_version__rfq=rfq,
                    rfq_version__version_number=rfq.current_version_number,
                ),
                "دامنه تجاری حاکم",
                describe=scope_label,
            )
            fields["supersedes"] = choice(
                comparisons.filter(finalized_at__isnull=False),
                "جانشینی مقایسه پیشین",
                required=False,
                describe=comparison_label,
            )
            fields["idempotency_key"] = key()
        elif action in {"appoint_evaluator", "finalize_comparison", "prepare_award"}:
            fields["comparison"] = comp(
                comparisons.filter(finalized_at__isnull=False)
                if action == "prepare_award"
                else comparisons.filter(finalized_at__isnull=True)
            )
            if action == "appoint_evaluator":
                fields["membership"] = member()
            if action == "finalize_comparison":
                fields["reason"] = text("دلیل نهایی‌سازی")
            if action == "prepare_award":
                fields.update(
                    {
                        "outcome": forms.ChoiceField(
                            label="نتیجه انتخاب", choices=m.SourcingAwardOutcome.choices
                        ),
                        "reason": text("دلیل تصمیم"),
                        "evidence": text("شاهد تصمیم"),
                        "tie_resolution": forms.BooleanField(
                            label="تصمیم صریح و مستند درباره تساوی", required=False
                        ),
                        "idempotency_key": key(),
                    }
                )
        elif action in {"evaluate", "declare_conflict"}:
            fields["appointment"] = choice(
                m.EvaluatorAppointment.objects.filter(
                    organization=org,
                    comparison__in=comparisons,
                    membership__user=actor,
                    revoked_at__isnull=True,
                    comparison__finalized_at__isnull=True,
                ),
                "انتصاب ارزیابی من",
                describe=lambda x: comparison_label(x.comparison),
            )
            if action == "evaluate":
                fields["input"] = choice(
                    m.CommercialComparisonInput.objects.filter(
                        organization=org, comparison__in=comparisons
                    ),
                    "ورودی مقایسه",
                    describe=lambda x: (
                        f"{comparison_label(x.comparison)} · {revision_label(x.quote_revision)}"
                    ),
                )
                fields["recommendation"] = text("بررسی مستند")
            fields["evidence"] = text("شاهد")
        elif action == "dispose_conflict":
            fields["conflict"] = choice(
                m.EvaluatorConflictDeclaration.objects.filter(
                    organization=org,
                    appointment__comparison__in=comparisons,
                    superseded_by__isnull=True,
                ),
                "تعارض اعلام‌شده",
                describe=lambda x: (
                    f"{comparison_label(x.appointment.comparison)} · {x.evidence}"
                ),
            )
            fields["approved"] = forms.TypedChoiceField(
                label="تصمیم درباره تعارض",
                choices=[("yes", "تأیید"), ("no", "رد")],
                coerce=lambda x: x == "yes",
            )
            fields["reason"] = text("دلیل تصمیم")
        elif action == "finalize_award":
            fields["preparation"] = choice(
                m.SourcingAwardPreparation.objects.filter(
                    organization=org, comparison__in=comparisons
                ),
                "انتخاب آماده‌شده",
                describe=lambda x: (
                    f"{comparison_label(x.comparison)} · {x.get_outcome_display()} · {x.reason}"
                ),
            )
            fields["supersedes"] = choice(
                m.SourcingAward.objects.filter(
                    organization=org,
                    comparison__in=comparisons,
                    superseded_by__isnull=True,
                ),
                "جانشینی انتخاب پیشین",
                required=False,
                describe=lambda x: (
                    f"{comparison_label(x.comparison)} · {x.get_outcome_display()}"
                ),
            )
        # Contextual parents are selected from the same scoped queryset and pinned
        # on POST. A URL or hidden value never supplies authority.
        self.context_objects = {}
        for name, field in fields.items():
            if (
                isinstance(field, forms.ModelChoiceField)
                and context
                and context.get(name)
            ):
                try:
                    target = field.queryset.get(pk=context[name])
                except (ValueError, ObjectDoesNotExist, ValidationError):
                    raise Http404("مرجع مجاز این مرحله یافت نشد.") from None
                field.queryset = field.queryset.filter(pk=target.pk)
                field.initial = target.pk
                field.widget = forms.HiddenInput()
                self.context_objects[name] = field.label_from_instance(target)
        if action == "evaluate" and "appointment" in self.context_objects:
            appointment = fields["appointment"].queryset.get()
            fields["input"].queryset = fields["input"].queryset.filter(
                comparison=appointment.comparison
            )
        for field in fields.values():
            if isinstance(field, forms.ChoiceField) and not isinstance(
                field, forms.ModelChoiceField
            ):
                field.choices = [("", "انتخاب کنید"), *field.choices]


class ComparisonInputForm(forms.Form):
    offered_quantity = forms.DecimalField(
        label="مقدار پیشنهادی", max_digits=18, decimal_places=4, min_value=0
    )
    unit_price = forms.DecimalField(
        label="قیمت واحد", max_digits=18, decimal_places=4, required=False
    )
    line_amount = forms.DecimalField(
        label="مبلغ ردیف", max_digits=18, decimal_places=4, required=False
    )
    currency = forms.RegexField(r"^[A-Za-z]{3}$", label="ارز ادعاشده", max_length=3)
    explicit_discount = forms.DecimalField(
        label="تخفیف صریح", max_digits=18, decimal_places=4, min_value=0
    )
    source_locator = forms.CharField(label="مرجع دقیق منبع", max_length=500)
    is_alternate = forms.BooleanField(label="پیشنهاد جایگزین", required=False)
    alternate_basis = forms.CharField(
        label="مبنای پیشنهاد جایگزین", max_length=500, required=False
    )

    def __init__(self, *args, rfq, actor, scope=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["quote_revision_id"] = choice(
            confidential_revisions(rfq=rfq, actor=actor)
            .filter(
                rfq_version__version_number=rfq.current_version_number,
                status="submitted",
                is_late=False,
                admissibility_decisions__state="admissible",
                admissibility_decisions__superseded_by__isnull=True,
            )
            .distinct()
            .select_related("envelope__supplier"),
            "نسخه پیشنهادی",
            describe=revision_label,
        )
        self.order_fields(["quote_revision_id", *self.fields])


class AwardAllocationForm(forms.Form):
    quantity = forms.DecimalField(
        label="مقدار تخصیص", max_digits=18, decimal_places=4, min_value=0
    )

    def __init__(self, *args, rfq, actor, comparison=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["comparison_input_id"] = choice(
            m.CommercialComparisonInput.objects.filter(
                organization=rfq.organization,
                comparison__in=comparison_records(rfq=rfq, actor=actor).filter(
                    finalized_at__isnull=False
                ),
                **({"comparison": comparison} if comparison else {}),
            ),
            "ورودی انتخاب",
            describe=lambda x: (
                f"{comparison_label(x.comparison)} · {revision_label(x.quote_revision)}"
            ),
        )
        self.order_fields(["comparison_input_id", "quantity"])


ComparisonInputs = formset_factory(
    ComparisonInputForm,
    extra=1,
    min_num=1,
    validate_min=True,
    max_num=100,
    validate_max=True,
)
AwardAllocations = formset_factory(
    AwardAllocationForm, extra=1, max_num=100, validate_max=True
)
