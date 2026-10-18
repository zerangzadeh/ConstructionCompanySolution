"""Own finalized Payroll reads and communication through the shared Workflow."""

from __future__ import annotations

from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import (
    get_active_membership,
    require_business_permission,
)
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import Organization
from apps.workflows.models import (
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowVersion,
    WorkItem,
    WorkItemStatus,
)
from apps.workflows.runtime import (
    complete_work_item,
    list_member_work_items,
    start_workflow,
)
from apps.workforce.ess_services import resolve_ess_subject
from apps.workforce.models import WorkRelationship

from .models import (
    PayrollInquiry,
    PayrollInquiryCategory,
    PayrollInquiryEvidenceLink,
    PayrollInquiryResponse,
    Payslip,
)

SUBJECT = "payroll.inquiry"
DENIED = "اطلاعات مجاز در این شرکت یافت نشد."


def _require(
    *,
    actor: User,
    organization: Organization,
    code: str,
    payslip: Payslip | None = None,
):
    return require_business_permission(
        user=actor,
        organization=organization,
        permission=code,
        project=payslip.run_employee.project if payslip else None,
        site=payslip.run_employee.site if payslip else None,
        allow_any_scope=payslip is None,
        message=DENIED,
    )


def _own_sources(
    *, actor: User, organization: Organization
) -> tuple[tuple[Payslip, WorkRelationship], ...]:
    _require(actor=actor, organization=organization, code=P.PAYROLL_ESS_VIEW)
    subject = resolve_ess_subject(user=actor, organization=organization)
    relationships = tuple(
        WorkRelationship.objects.filter(
            organization=organization,
            person=subject.person,
            legacy_employee_id__isnull=False,
        )
    )
    slips = Payslip.objects.filter(
        organization=organization,
        run_employee__employee_id__in=[
            item.legacy_employee_id for item in relationships
        ],
        run__organization=organization,
        run_employee__organization=organization,
        run__status__in=["finalized", "reversed"],
        run__finalized_at__isnull=False,
        run_employee__status__in=["finalized", "reversed"],
    ).select_related(
        "run__period",
        "run_employee__employee",
        "run_employee__project",
        "run_employee__site",
    )
    result = []
    for slip in slips.order_by("-run__period__ends_on", "-issued_at"):
        # A finalized source must belong to the exact retained employment episode.
        if slip.run_employee.run_id != slip.run_id:
            continue
        episode = next(
            (
                item
                for item in relationships
                if item.legacy_employee_id == slip.run_employee.employee_id
                and item.effective_start <= slip.run.period.ends_on
                and (
                    item.effective_end is None
                    or item.effective_end >= slip.run.period.starts_on
                )
            ),
            None,
        )
        if episode is None:
            continue
        try:
            _require(
                actor=actor,
                organization=organization,
                code=P.PAYROLL_ESS_VIEW,
                payslip=slip,
            )
        except PermissionDenied:
            continue
        result.append((slip, episode))
    return tuple(result)


def _audit_payslip(
    *,
    actor: User,
    organization: Organization,
    slip: Payslip,
    episode: WorkRelationship,
    export: bool = False,
) -> None:
    record_audit_event(
        action=AuditAction.PAYSLIP_EXPORTED if export else AuditAction.PAYSLIP_VIEWED,
        organization=organization,
        actor=actor,
        entity_type="payroll.payslip",
        entity_id=slip.pk,
        metadata={
            "ess": True,
            "run_id": str(slip.run_id),
            "work_relationship_id": str(episode.pk),
            "content_digest": slip.content_digest,
        },
    )


def own_payroll_history(
    *, actor: User, organization: Organization
) -> tuple[Payslip, ...]:
    sources = _own_sources(actor=actor, organization=organization)
    for slip, episode in sources:
        _audit_payslip(
            actor=actor, organization=organization, slip=slip, episode=episode
        )
    return tuple(slip for slip, _ in sources)


def own_payslip(
    *, actor: User, organization: Organization, payslip_id: object, export: bool = False
) -> Payslip:
    source = next(
        (
            (slip, episode)
            for slip, episode in _own_sources(actor=actor, organization=organization)
            if str(slip.pk) == str(payslip_id)
        ),
        None,
    )
    if source is None:
        raise PermissionDenied(DENIED)
    slip, episode = source
    if export:
        _require(
            actor=actor,
            organization=organization,
            code=P.PAYROLL_ESS_EXPORT,
            payslip=slip,
        )
    _audit_payslip(
        actor=actor,
        organization=organization,
        slip=slip,
        episode=episode,
        export=export,
    )
    return slip


@transaction.atomic
def configure_inquiry_category(
    *,
    actor: User,
    organization: Organization,
    code: str,
    name: str,
    workflow_version: WorkflowVersion,
    reason: str,
) -> PayrollInquiryCategory:
    _require(
        actor=actor, organization=organization, code=P.PAYROLL_CONFIGURATION_MANAGE
    )
    # Serialize versions on the tenant; no seeded category or implicit grants.
    Organization.objects.select_for_update().get(pk=organization.pk)
    _require(
        actor=actor, organization=organization, code=P.PAYROLL_CONFIGURATION_MANAGE
    )
    version = (
        PayrollInquiryCategory.objects.filter(
            organization=organization, code=code
        ).aggregate(number=Max("version"))["number"]
        or 0
    ) + 1
    if (
        workflow_version.organization_id != organization.pk
        or workflow_version.status != "published"
        or workflow_version.definition.workflow_type.code != SUBJECT
    ):
        raise ValidationError("گردش‌کار منتشرشده و مجاز پرسش حقوق لازم است.")
    decisions = workflow_version.steps.filter(step_type="approval")
    if not decisions.exists() or any(
        item.required_permission != P.PAYROLL_INQUIRIES_RESPOND
        or item.configuration.get("due_hours") is not None
        for item in decisions
    ):
        raise ValidationError(
            "مسیر پاسخ باید مجوز صریح پاسخ‌گویی و بدون زمان‌سنج خودکار داشته باشد."
        )
    for step in decisions:
        if not step.outgoing_transitions.exists() or any(
            (transition.domain_command or step.domain_command)
            != "payroll.inquiry.respond"
            for transition in step.outgoing_transitions.all()
        ):
            raise ValidationError(
                "مسیر هر پاسخ باید فرمان ثبت پاسخ قابل نمایش را فراخوانی کند."
            )
    return PayrollInquiryCategory.objects.create(
        organization=organization,
        code=code,
        name=name,
        version=version,
        workflow_version=workflow_version,
        created_by=actor,
        reason=reason,
    )


def inquiry_instance(inquiry: PayrollInquiry) -> WorkflowInstance | None:
    return WorkflowInstance.objects.filter(
        organization_id=inquiry.organization_id,
        subject_type=SUBJECT,
        subject_id=inquiry.pk,
        version_id=inquiry.category.workflow_version_id,
    ).first()


def visible_inquiries(
    *, actor: User, organization: Organization
) -> tuple[PayrollInquiry, ...]:
    _require(actor=actor, organization=organization, code=P.PAYROLL_INQUIRIES_VIEW)
    own_person_id = None
    own_payslip_ids = set()
    try:
        _require(actor=actor, organization=organization, code=P.PAYROLL_ESS_VIEW)
        own_person_id = resolve_ess_subject(
            user=actor, organization=organization
        ).person.pk
        own_payslip_ids = {
            slip.pk for slip, _ in _own_sources(actor=actor, organization=organization)
        }
    except PermissionDenied:
        pass
    assigned_ids = set()
    try:
        _require(actor=actor, organization=organization, code=P.PAYROLL_RESULTS_VIEW)
        assigned_ids = set(
            list_member_work_items(
                actor=actor, organization=organization, include_terminal=True
            )
            .filter(instance__subject_type=SUBJECT)
            .values_list("instance__subject_id", flat=True)
        )
    except PermissionDenied:
        pass
    rows = PayrollInquiry.objects.filter(organization=organization).select_related(
        "category__workflow_version",
        "payslip__run_employee__project",
        "payslip__run_employee__site",
        "period",
        "person",
        "work_relationship",
    )
    allowed = []
    for item in rows.order_by("-created_at"):
        own = (
            item.requested_by_id == actor.pk
            and item.person_id == own_person_id
            and item.payslip_id in own_payslip_ids
        )
        handler = item.pk in assigned_ids
        if not own and not handler:
            continue
        try:
            _require(
                actor=actor,
                organization=organization,
                code=P.PAYROLL_INQUIRIES_VIEW,
                payslip=item.payslip,
            )
            if not own:
                _require(
                    actor=actor,
                    organization=organization,
                    code=P.PAYROLL_RESULTS_VIEW,
                    payslip=item.payslip,
                )
        except PermissionDenied:
            continue
        allowed.append(item)
    return tuple(allowed)


def get_inquiry(
    *, actor: User, organization: Organization, inquiry_id: object
) -> PayrollInquiry:
    item = next(
        (
            item
            for item in visible_inquiries(actor=actor, organization=organization)
            if str(item.pk) == str(inquiry_id)
        ),
        None,
    )
    if item is None:
        raise PermissionDenied(DENIED)
    return item


@transaction.atomic
def submit_inquiry(
    *,
    actor: User,
    organization: Organization,
    payslip_id: object,
    category_id: object,
    subject: str,
    description: str,
    idempotency_key: str,
    document_version_ids: tuple[object, ...] = (),
) -> PayrollInquiry:
    slip = own_payslip(actor=actor, organization=organization, payslip_id=payslip_id)
    _require(
        actor=actor,
        organization=organization,
        code=P.PAYROLL_INQUIRIES_REQUEST,
        payslip=slip,
    )
    _require(
        actor=actor,
        organization=organization,
        code=P.PAYROLL_INQUIRIES_VIEW,
        payslip=slip,
    )
    membership = get_active_membership(user=actor, organization=organization)
    type(membership).objects.select_for_update().get(pk=membership.pk)
    _require(
        actor=actor,
        organization=organization,
        code=P.PAYROLL_INQUIRIES_REQUEST,
        payslip=slip,
    )
    source = next(
        (
            episode
            for item, episode in _own_sources(actor=actor, organization=organization)
            if item.pk == slip.pk
        ),
        None,
    )
    if source is None:
        raise PermissionDenied(DENIED)
    try:
        category = (
            PayrollInquiryCategory.objects.select_for_update()
            .select_related("workflow_version__definition__workflow_type")
            .get(
                pk=category_id,
                organization=organization,
                workflow_version__status="published",
            )
        )
    except (PayrollInquiryCategory.DoesNotExist, ValueError, ValidationError) as exc:
        raise ValidationError("دسته و مسیر پاسخ‌گویی مجاز در دسترس نیست.") from exc
    for key, expected in category.workflow_version.definition.scope.items():
        actual = {
            "project_id": slip.run_employee.project_id,
            "site_id": slip.run_employee.site_id,
        }.get(key)
        if str(actual) != str(expected):
            raise PermissionDenied(DENIED)
    existing = PayrollInquiry.objects.filter(
        organization=organization, requested_by=actor, idempotency_key=idempotency_key
    ).first()
    if existing:
        linked = {
            str(value)
            for value in existing.evidence_links.values_list(
                "document_version_id", flat=True
            )
        }
        if (
            existing.payslip_id != slip.pk
            or str(existing.category_id) != str(category_id)
            or existing.subject != subject.strip()
            or existing.description != description.strip()
            or linked != {str(value) for value in document_version_ids}
        ):
            raise ValidationError("کلید تکرارپذیری برای پرسش دیگری استفاده شده است.")
        return existing
    item = PayrollInquiry.objects.create(
        organization=organization,
        requested_by=actor,
        person=source.person,
        work_relationship=source,
        payslip=slip,
        period=slip.run.period,
        category=category,
        subject=subject.strip(),
        description=description.strip(),
        idempotency_key=idempotency_key,
    )
    if document_version_ids:
        from apps.documents import services as dms
        from apps.documents.models import DocumentVersion

        for identifier in set(document_version_ids):
            version = (
                DocumentVersion.objects.filter(pk=identifier, organization=organization)
                .select_related("document")
                .first()
            )
            if version is None:
                raise PermissionDenied(DENIED)
            document = dms.get_organization_document(
                user=actor,
                organization=organization,
                document_id=str(version.document_id),
            )
            dms.get_document_version_for_download(
                document=document, version_id=str(version.pk), actor=actor
            )
            PayrollInquiryEvidenceLink.objects.create(
                organization=organization,
                payroll_inquiry=item,
                document=document,
                document_version=version,
                created_by=actor,
            )
    instance = start_workflow(
        actor=actor,
        organization=organization,
        version_id=category.workflow_version_id,
        subject_id=item.pk,
        idempotency_key=f"payroll-inquiry:{item.pk}",
    )
    active_items = instance.work_items.filter(
        status__in=[WorkItemStatus.OPEN, WorkItemStatus.CLAIMED]
    )
    usable = bool(active_items)
    for task in active_items:
        task_usable = False
        for candidate in task.candidates.filter(is_active=True).select_related(
            "membership__user"
        ):
            try:
                for code in (
                    P.PAYROLL_RESULTS_VIEW,
                    P.PAYROLL_INQUIRIES_VIEW,
                    P.PAYROLL_INQUIRIES_RESPOND,
                    P.WORK_ITEMS_VIEW,
                    P.WORK_ITEMS_CLAIM,
                    P.WORK_ITEMS_ACT,
                ):
                    _require(
                        actor=candidate.membership.user,
                        organization=organization,
                        code=code,
                        payslip=slip,
                    )
            except PermissionDenied:
                continue
            task_usable = True
            break
        usable = usable and task_usable
    if instance.status != WorkflowInstanceStatus.ACTIVE or not usable:
        raise ValidationError("مسیر پاسخ‌گویی مجاز حل نشد؛ پرسشی ثبت نشد.")
    return item


@transaction.atomic
def respond_inquiry(
    *,
    actor: User,
    organization: Organization,
    inquiry_id: object,
    work_item_id: object,
    outcome: str,
    body: str,
    idempotency_key: str,
) -> None:
    item = get_inquiry(actor=actor, organization=organization, inquiry_id=inquiry_id)
    _require(
        actor=actor,
        organization=organization,
        code=P.PAYROLL_INQUIRIES_RESPOND,
        payslip=item.payslip,
    )
    work_item = WorkItem.objects.filter(
        pk=work_item_id,
        organization=organization,
        instance__subject_type=SUBJECT,
        instance__subject_id=item.pk,
    ).first()
    if work_item is None:
        raise PermissionDenied(DENIED)
    completed = complete_work_item(
        actor=actor,
        organization=organization,
        work_item_id=work_item.pk,
        outcome=outcome,
        idempotency_key=idempotency_key,
        command_context={"employee_visible_response": body},
    )
    # A multi-actor step may not reach its threshold on this action. Retain this
    # explicit response too, atomically with the authoritative completion.
    append_workflow_response(
        subject=item,
        actor=actor,
        organization=organization,
        work_item=completed,
        context={"employee_visible_response": body},
        idempotency_key=idempotency_key,
    )


def append_workflow_response(
    *,
    subject: PayrollInquiry,
    actor: User,
    organization: Organization,
    work_item: WorkItem,
    context: dict[str, Any],
    idempotency_key: str,
    **kwargs: Any,
) -> None:
    del kwargs
    _require(
        actor=actor,
        organization=organization,
        code=P.PAYROLL_INQUIRIES_RESPOND,
        payslip=subject.payslip,
    )
    membership = get_active_membership(user=actor, organization=organization)
    if (
        work_item.organization_id != organization.pk
        or work_item.instance.subject_id != subject.pk
        or work_item.status not in {WorkItemStatus.CLAIMED, WorkItemStatus.COMPLETED}
        or work_item.current_assignee_id != membership.pk
    ):
        raise PermissionDenied(DENIED)
    body = context.get("employee_visible_response")
    if not isinstance(body, str) or not body.strip():
        raise ValidationError(
            "پاسخ قابل نمایش به کارمند باید صریح باشد؛ یادداشت داخلی منتشر نمی‌شود."
        )
    previous = PayrollInquiryResponse.objects.filter(
        inquiry=subject, idempotency_key=idempotency_key
    ).first()
    if previous:
        if previous.body != body.strip() or previous.work_item_id != work_item.pk:
            raise ValidationError("کلید تکرارپذیری پاسخ با سابقه هم‌خوان نیست.")
        return
    PayrollInquiryResponse.objects.create(
        organization=organization,
        inquiry=subject,
        work_item=work_item,
        responded_by=actor,
        body=body.strip(),
        idempotency_key=idempotency_key,
    )
