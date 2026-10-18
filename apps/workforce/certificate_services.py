"""Certificate framework. No renderer, legal text or signature policy ships here."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.db.models import Max

from apps.accounts.models import User
from apps.documents import services as dms
from apps.documents.models import (
    Document,
    DocumentCategory,
    DocumentType,
    DocumentVersion,
)
from apps.organizations.authorization import (
    get_active_membership,
    require_business_permission,
)
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import Organization, OrganizationMembership
from apps.workflows.models import (
    WorkflowInstance,
    WorkflowVersion,
    WorkItem,
    WorkItemStatus,
)
from apps.workflows.runtime import (
    cancel_workflow_for_domain,
    list_member_work_items,
    start_workflow,
)

from .ess_services import resolve_ess_subject
from .models import (
    HRCertificateCancellation,
    HRCertificateGeneration,
    HRCertificateRequest,
    HRCertificateReview,
    HRCertificateType,
    Person,
    WorkRelationship,
)

SUBJECT = "workforce.hr_certificate_review"
DENIED = "اطلاعات مجاز در این شرکت یافت نشد."


@dataclass(frozen=True)
class ActivationReceipt:
    template_version_id: str
    template_sha256: str
    signature_policy_reference: str
    source_reference: str
    renderer_version: str


@dataclass(frozen=True)
class CertificateRenderer:
    resolve_activation: Callable[[HRCertificateType], ActivationReceipt | None]
    render: Callable[..., UploadedFile]
    can_cancel_generated: Callable[..., bool]


# Only deployed platform code can register adapters. No tenant executable code.
# Empty by default: EXT-0019 and official generation activation remain closed.
RENDERERS: dict[str, CertificateRenderer] = {}


def register_renderer(key: str, renderer: CertificateRenderer) -> None:
    if not key or key in RENDERERS:
        raise ValueError("شناسه تطبیق‌دهنده معتبر و یکتا لازم است.")
    RENDERERS[key] = renderer


def require(
    *, actor: User, organization: Organization, code: str
) -> OrganizationMembership:
    return require_business_permission(
        user=actor, organization=organization, permission=code, message=DENIED
    )


def digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def activation(
    certificate_type: HRCertificateType,
) -> tuple[CertificateRenderer, ActivationReceipt]:
    renderer = RENDERERS.get(certificate_type.renderer_key)
    if renderer is None or not certificate_type.template_version_id:
        raise ValidationError("قالب و سیاست امضای مجاز برای تولید فعال نشده است.")
    receipt = renderer.resolve_activation(certificate_type)
    if (
        not isinstance(receipt, ActivationReceipt)
        or receipt.template_version_id != str(certificate_type.template_version_id)
        or receipt.template_sha256 != certificate_type.template_version.sha256
        or not all(
            (
                receipt.signature_policy_reference,
                receipt.source_reference,
                receipt.renderer_version,
            )
        )
    ):
        raise ValidationError("مدرک فعال‌سازی قالب و امضا قابل اتکا نیست.")
    if not certificate_type.template_version.is_available:
        raise ValidationError("نسخه قالب هنوز برای استفاده ایمن در دسترس نیست.")
    return renderer, receipt


def _generator(
    *, actor: User, organization: Organization, certificate_type: HRCertificateType
) -> OrganizationMembership:
    member = require(
        actor=actor, organization=organization, code=P.HR_CERTIFICATES_GENERATE
    )
    if member.pk != certificate_type.generator_id:
        raise PermissionDenied(DENIED)
    for code in (
        P.HR_CERTIFICATES_VIEW,
        P.DOCUMENTS_UPLOAD,
        P.DOCUMENTS_VIEW,
        P.DOCUMENTS_DOWNLOAD,
        P.EMPLOYEES_VIEW,
    ):
        require(actor=actor, organization=organization, code=code)
    return member


@transaction.atomic
def configure_type(
    *,
    actor: User,
    organization: Organization,
    code: str,
    name: str,
    source_map: dict,
    template_version: DocumentVersion | None,
    category: DocumentCategory,
    generator: OrganizationMembership,
    renderer_key: str,
    enabled: bool,
    employee_visible: bool,
    cancellation_before_output: bool,
    reason: str,
    review_version: WorkflowVersion | None = None,
) -> HRCertificateType:
    Organization.objects.select_for_update().get(pk=organization.pk)
    require(actor=actor, organization=organization, code=P.HR_CERTIFICATES_CONFIGURE)
    if generator.organization_id != organization.pk or generator.status != "active":
        raise PermissionDenied(DENIED)
    if template_version:
        document = dms.get_organization_document(
            user=actor,
            organization=organization,
            document_id=str(template_version.document_id),
        )
        dms.get_document_version_for_download(
            document=document, version_id=str(template_version.pk), actor=actor
        )
    if review_version:
        steps = list(review_version.steps.filter(step_type="approval"))
        if (
            len(steps) != 1
            or steps[0].required_permission != P.HR_CERTIFICATES_REVIEW
            or steps[0].configuration.get("decision_policy", "any") != "any"
            or {
                t.domain_command or steps[0].domain_command
                for t in steps[0].outgoing_transitions.all()
            }
            != {SUBJECT + ".accept", SUBJECT + ".reject"}
            or any(
                not t.target_step.is_terminal
                for t in steps[0].outgoing_transitions.select_related("target_step")
            )
        ):
            raise ValidationError(
                "بررسی اختیاری باید یک تصمیم مجاز پذیرش یا رد داشته باشد."
            )
    version = (
        HRCertificateType.objects.filter(
            organization=organization, code=code
        ).aggregate(n=Max("version"))["n"]
        or 0
    ) + 1
    item = HRCertificateType(
        organization=organization,
        code=code,
        name=name,
        version=version,
        enabled=enabled,
        employee_visible=employee_visible,
        cancellation_before_output=cancellation_before_output,
        source_map=source_map,
        template_version=template_version,
        category=category,
        generator=generator,
        renderer_key=renderer_key,
        review_version=review_version,
        created_by=actor,
        reason=reason,
    )
    item.full_clean(validate_constraints=False)
    if enabled:
        activation(item)
        _generator(
            actor=generator.user, organization=organization, certificate_type=item
        )
    item.save()
    return item


def available_types(
    *, actor: User, organization: Organization
) -> tuple[HRCertificateType, ...]:
    require(actor=actor, organization=organization, code=P.HR_CERTIFICATES_REQUEST)
    resolve_ess_subject(user=actor, organization=organization)
    rows = (
        HRCertificateType.objects.filter(organization=organization)
        .select_related("template_version")
        .order_by("code", "-version")
        .distinct("code")
    )
    result = []
    for item in rows:
        if not item.enabled or not item.employee_visible:
            continue
        try:
            activation(item)
        except ValidationError:
            continue
        result.append(item)
    return tuple(result)


def instance_for(item: HRCertificateRequest) -> WorkflowInstance | None:
    return (
        WorkflowInstance.objects.filter(
            organization_id=item.organization_id,
            subject_type=SUBJECT,
            subject_id=item.pk,
            version_id=item.certificate_type.review_version_id,
        ).first()
        if item.certificate_type.review_version_id
        else None
    )


def visible_requests(
    *, actor: User, organization: Organization
) -> tuple[HRCertificateRequest, ...]:
    member = require(
        actor=actor, organization=organization, code=P.HR_CERTIFICATES_VIEW
    )
    person_id = None
    try:
        person_id = resolve_ess_subject(user=actor, organization=organization).person.pk
    except PermissionDenied:
        pass
    assigned = set()
    try:
        require(actor=actor, organization=organization, code=P.HR_CERTIFICATES_REVIEW)
        assigned = set(
            list_member_work_items(
                actor=actor, organization=organization, include_terminal=True
            )
            .filter(instance__subject_type=SUBJECT)
            .values_list("instance__subject_id", flat=True)
        )
    except PermissionDenied:
        pass
    generator = False
    try:
        require(actor=actor, organization=organization, code=P.HR_CERTIFICATES_GENERATE)
        generator = True
    except PermissionDenied:
        pass
    rows = (
        HRCertificateRequest.objects.filter(organization=organization)
        .select_related(
            "certificate_type__template_version",
            "person",
            "work_relationship",
            "generation__document_version",
            "review",
            "cancellation",
        )
        .order_by("-created_at")
    )
    return tuple(
        item
        for item in rows
        if (
            item.person_id == person_id
            and item.requested_by_id == actor.pk
            and item.certificate_type.employee_visible
        )
        or item.pk in assigned
        or (generator and item.certificate_type.generator_id == member.pk)
    )


def get_request(
    *, actor: User, organization: Organization, request_id: object
) -> HRCertificateRequest:
    item = next(
        (
            i
            for i in visible_requests(actor=actor, organization=organization)
            if str(i.pk) == str(request_id)
        ),
        None,
    )
    if item is None:
        raise PermissionDenied(DENIED)
    return item


@transaction.atomic
def submit_request(
    *,
    actor: User,
    organization: Organization,
    type_id: object,
    reason: str,
    idempotency_key: str,
    replaces_id: object | None = None,
) -> HRCertificateRequest:
    member = get_active_membership(user=actor, organization=organization)
    OrganizationMembership.objects.select_for_update().get(pk=member.pk)
    require(actor=actor, organization=organization, code=P.HR_CERTIFICATES_VIEW)
    own = resolve_ess_subject(user=actor, organization=organization)
    kind = next(
        (
            k
            for k in available_types(actor=actor, organization=organization)
            if str(k.pk) == str(type_id)
        ),
        None,
    )
    if kind is None:
        raise ValidationError("نوع گواهی، قالب و سیاست تولید مجاز در دسترس نیست.")
    _generator(
        actor=kind.generator.user, organization=organization, certificate_type=kind
    )
    previous = HRCertificateRequest.objects.filter(
        organization=organization, requested_by=actor, idempotency_key=idempotency_key
    ).first()
    if previous:
        if (
            previous.certificate_type_id != kind.pk
            or previous.reason != reason.strip()
            or str(previous.replaces_id or "") != str(replaces_id or "")
        ):
            raise ValidationError("کلید تکرارپذیری با درخواست قبلی سازگار نیست.")
        return previous
    replaces = None
    if replaces_id:
        replaces = get_request(
            actor=actor, organization=organization, request_id=replaces_id
        )
        if not HRCertificateGeneration.objects.filter(request=replaces).exists():
            raise ValidationError("فقط خروجی موجود می‌تواند مرجع جایگزینی باشد.")
    Person.objects.select_for_update().get(pk=own.person.pk)
    WorkRelationship.objects.select_for_update().get(pk=own.current_relationship.pk)
    own = resolve_ess_subject(user=actor, organization=organization)
    source = {
        "person.first_name": own.person.first_name,
        "person.last_name": own.person.last_name,
        "relationship.employee_number": own.current_relationship.employee_number,
        "relationship.effective_start": own.current_relationship.effective_start.isoformat(),
        "relationship.effective_end": own.current_relationship.effective_end.isoformat()
        if own.current_relationship.effective_end
        else None,
    }
    snapshot = {
        "fields": {key: source[value] for key, value in kind.source_map.items()},
        "person_id": str(own.person.pk),
        "relationship_id": str(own.current_relationship.pk),
        "type_id": str(kind.pk),
    }
    item = HRCertificateRequest.objects.create(
        organization=organization,
        requested_by=actor,
        person=own.person,
        work_relationship=own.current_relationship,
        certificate_type=kind,
        source_snapshot=snapshot,
        source_digest=digest(snapshot),
        reason=reason.strip(),
        idempotency_key=idempotency_key,
        replaces=replaces,
    )
    if kind.review_version_id:
        instance = start_workflow(
            actor=actor,
            organization=organization,
            version_id=kind.review_version_id,
            subject_id=item.pk,
            idempotency_key=f"certificate-review:{item.pk}",
        )
        usable = False
        for task in instance.work_items.filter(
            status__in=[WorkItemStatus.OPEN, WorkItemStatus.CLAIMED]
        ):
            for candidate in task.candidates.filter(is_active=True).select_related(
                "membership__user"
            ):
                try:
                    for permission in (
                        P.HR_CERTIFICATES_VIEW,
                        P.HR_CERTIFICATES_REVIEW,
                        P.WORK_ITEMS_VIEW,
                        P.WORK_ITEMS_CLAIM,
                        P.WORK_ITEMS_ACT,
                    ):
                        require(
                            actor=candidate.membership.user,
                            organization=organization,
                            code=permission,
                        )
                except PermissionDenied:
                    continue
                usable = True
        if instance.status != "active" or not usable:
            raise ValidationError("مسیر بررسی مجاز حل نشد؛ درخواستی ثبت نشد.")
    return item


def _review(
    *,
    subject: HRCertificateRequest,
    actor: User,
    organization: Organization,
    work_item: WorkItem,
    context: dict[str, Any],
    outcome: str,
    **kwargs: Any,
) -> None:
    del kwargs
    member = require(
        actor=actor, organization=organization, code=P.HR_CERTIFICATES_REVIEW
    )
    if (
        work_item.status != WorkItemStatus.CLAIMED
        or work_item.current_assignee_id != member.pk
        or work_item.instance.subject_id != subject.pk
    ):
        raise PermissionDenied(DENIED)
    reason = context.get("employee_visible_reason", "")
    if not isinstance(reason, str) or not reason.strip():
        raise ValidationError(
            "دلیل قابل نمایش بررسی لازم است؛ یادداشت داخلی منتشر نمی‌شود."
        )
    HRCertificateReview.objects.create(
        organization=organization,
        request=subject,
        actor=actor,
        work_item=work_item,
        outcome=outcome,
        reason=reason.strip(),
    )


def accept_review(**kwargs: Any) -> None:
    kwargs.pop("outcome", None)
    return _review(outcome="accepted", **kwargs)


def reject_review(**kwargs: Any) -> None:
    kwargs.pop("outcome", None)
    return _review(outcome="rejected", **kwargs)


def generate_certificate(
    *, actor: User, organization: Organization, request_id: object
) -> HRCertificateGeneration:
    """Own the outer commit so any failed new binary can be compensated."""
    stored_names = []
    upload = None
    try:
        with transaction.atomic(durable=True):
            Organization.objects.select_for_update().get(pk=organization.pk)
            visible = get_request(
                actor=actor, organization=organization, request_id=request_id
            )
            item = (
                HRCertificateRequest.objects.select_for_update(of=("self",))
                .select_related(
                    "certificate_type__template_version",
                    "certificate_type__category",
                    "work_relationship",
                    "requested_by",
                )
                .get(pk=visible.pk, organization=organization)
            )
            OrganizationMembership.objects.select_for_update().get(
                pk=get_active_membership(user=actor, organization=organization).pk
            )
            _generator(
                actor=actor,
                organization=organization,
                certificate_type=item.certificate_type,
            )
            if HRCertificateCancellation.objects.filter(request=item).exists():
                raise ValidationError("درخواست لغوشده خروجی جدید ندارد.")
            previous = HRCertificateGeneration.objects.filter(request=item).first()
            if previous:
                return previous
            current = (
                HRCertificateType.objects.filter(
                    organization=organization, code=item.certificate_type.code
                )
                .order_by("-version")
                .first()
            )
            if (
                current.pk != item.certificate_type_id
                or not current.enabled
                or digest(item.source_snapshot) != item.source_digest
            ):
                raise ValidationError("نسخه نوع یا داده مرجع قابل اتکا نیست.")
            if (
                item.certificate_type.review_version_id
                and not HRCertificateReview.objects.filter(
                    request=item, outcome="accepted"
                ).exists()
            ):
                raise ValidationError("پذیرش مجاز بررسی هنوز ثبت نشده است.")
            OrganizationMembership.objects.select_for_update().get(
                user_id=item.requested_by_id, organization=organization
            )
            Person.objects.select_for_update().get(
                pk=item.person_id, organization=organization
            )
            WorkRelationship.objects.select_for_update().get(
                pk=item.work_relationship_id, organization=organization
            )
            own = resolve_ess_subject(user=item.requested_by, organization=organization)
            if (
                own.person.pk != item.person_id
                or own.current_relationship.pk != item.work_relationship_id
            ):
                raise PermissionDenied(DENIED)
            Document.objects.select_for_update().get(
                pk=item.certificate_type.template_version.document_id,
                organization=organization,
            )
            item.certificate_type.category = (
                DocumentCategory.objects.select_for_update().get(
                    pk=item.certificate_type.category_id, organization=organization
                )
            )
            renderer, receipt = activation(item.certificate_type)
            template = dms.get_organization_document(
                user=actor,
                organization=organization,
                document_id=str(item.certificate_type.template_version.document_id),
            )
            version = dms.get_document_version_for_download(
                document=template,
                version_id=str(item.certificate_type.template_version_id),
                actor=actor,
            )
            template_hash = hashlib.sha256()
            with version.file.open("rb") as template_stream:
                for chunk in iter(lambda: template_stream.read(65536), b""):
                    template_hash.update(chunk)
            if template_hash.hexdigest() != version.sha256:
                raise ValidationError("یکپارچگی نسخه قالب قابل تأیید نیست.")
            try:
                upload = renderer.render(
                    certificate_type=item.certificate_type,
                    source_snapshot=item.source_snapshot,
                    template_version=version,
                    activation_receipt=receipt,
                )
            except Exception as exc:
                raise ValidationError(
                    "تطبیق‌دهنده تولید خروجی معتبر ارائه نکرد."
                ) from exc
            if not isinstance(upload, UploadedFile):
                raise ValidationError("خروجی تطبیق‌دهنده باید فایل DMS معتبر باشد.")
            document = dms.create_document(
                actor=actor,
                organization=organization,
                document_type=DocumentType.OTHER,
                title=f"{item.certificate_type.name} — {str(item.pk)[:8]}",
                upload=upload,
                target=item.work_relationship,
                category=item.certificate_type.category,
                stored_names=stored_names,
                audit_metadata={
                    "certificate_request_id": str(item.pk),
                    "source_digest": item.source_digest,
                },
            )
            output = document.current_version
            actual = hashlib.sha256()
            with output.file.open("rb") as stream:
                for chunk in iter(lambda: stream.read(65536), b""):
                    actual.update(chunk)
            if actual.hexdigest() != output.sha256:
                raise ValidationError("کنترل یکپارچگی ذخیره‌سازی خروجی ناموفق بود.")
            return HRCertificateGeneration.objects.create(
                organization=organization,
                request=item,
                document_version=output,
                template_version=version,
                source_digest=item.source_digest,
                activation_receipt=asdict(receipt),
                actor=actor,
            )
    except Exception:
        for name in stored_names:
            DocumentVersion._meta.get_field("file").storage.delete(name)
        raise
    finally:
        if upload is not None:
            upload.close()


@transaction.atomic
def cancel_request(
    *,
    actor: User,
    organization: Organization,
    request_id: object,
    reason: str,
    idempotency_key: str,
) -> HRCertificateCancellation:
    visible = get_request(actor=actor, organization=organization, request_id=request_id)
    item = (
        HRCertificateRequest.objects.select_for_update(of=("self",))
        .select_related("certificate_type__template_version")
        .get(pk=visible.pk, organization=organization)
    )
    previous = HRCertificateCancellation.objects.filter(request=item).first()
    if previous:
        if previous.actor_id != actor.pk or previous.reason != reason.strip():
            raise ValidationError("لغو قبلی با این درخواست هم‌خوان نیست.")
        return previous
    generated = HRCertificateGeneration.objects.filter(request=item).exists()
    if generated:
        _generator(
            actor=actor,
            organization=organization,
            certificate_type=item.certificate_type,
        )
        require(actor=actor, organization=organization, code=P.HR_CERTIFICATES_CANCEL)
        renderer, _ = activation(item.certificate_type)
        if not renderer.can_cancel_generated(
            certificate_type=item.certificate_type, request=item, actor=actor
        ):
            raise ValidationError("سیاست منبع اجازه لغو خروجی را نمی‌دهد.")
    else:
        require(actor=actor, organization=organization, code=P.HR_CERTIFICATES_REQUEST)
        if (
            item.requested_by_id != actor.pk
            or not item.certificate_type.cancellation_before_output
        ):
            raise PermissionDenied(DENIED)
    instance = instance_for(item)
    if instance and instance.status in {"active", "suspended"}:
        cancel_workflow_for_domain(
            actor=actor,
            organization=organization,
            instance_id=instance.pk,
            command_key=SUBJECT + ".cancel",
            reason=reason,
            idempotency_key=idempotency_key,
            command_context={"employee_visible_reason": reason},
        )
        return HRCertificateCancellation.objects.get(request=item)
    return HRCertificateCancellation.objects.create(
        organization=organization, request=item, actor=actor, reason=reason.strip()
    )


def cancel_review_command(
    *,
    subject: HRCertificateRequest,
    actor: User,
    organization: Organization,
    context: dict[str, Any],
    **kwargs: Any,
) -> None:
    del kwargs
    require(actor=actor, organization=organization, code=P.HR_CERTIFICATES_REQUEST)
    if (
        subject.requested_by_id != actor.pk
        or not subject.certificate_type.cancellation_before_output
        or HRCertificateGeneration.objects.filter(request=subject).exists()
    ):
        raise PermissionDenied(DENIED)
    HRCertificateCancellation.objects.create(
        organization=organization,
        request=subject,
        actor=actor,
        reason=context.get("employee_visible_reason", "").strip(),
    )
