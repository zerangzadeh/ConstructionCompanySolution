"""Governed contact requests; Workforce owns values, Workflow owns decisions."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max

from apps.accounts.models import User
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
    complete_work_item,
    list_member_work_items,
    start_workflow,
)

from .ess_services import ESSSubject, resolve_ess_subject
from .models import (
    Employee,
    Person,
    PersonalDataDecision,
    PersonalDataEnrollment,
    PersonalDataRequest,
    WorkRelationship,
)

if TYPE_CHECKING:
    from apps.workflows.personal_workspaces import RequestWorkspaceRow

SUBJECT = "workforce.personal_data_change"
FIELDS = frozenset({"phone_number", "email", "address", "emergency_contact"})
FAMILIES = {
    "phone": "phone_number",
    "email": "email",
    "address": "address",
    "emergency": "emergency_contact",
}
DENIED = "اطلاعات مجاز در این شرکت یافت نشد."


def require(
    *, actor: User, organization: Organization, code: str
) -> OrganizationMembership:
    return require_business_permission(
        user=actor, organization=organization, permission=code, message=DENIED
    )


def _own(*, actor: User, organization: Organization) -> tuple[ESSSubject, Employee]:
    subject = resolve_ess_subject(user=actor, organization=organization)
    relationship = subject.current_relationship
    if not relationship.legacy_employee_id:
        raise PermissionDenied(DENIED)
    employee = Employee.objects.filter(
        pk=relationship.legacy_employee_id,
        organization=organization,
        archived_at__isnull=True,
    ).first()
    if employee is None:
        raise PermissionDenied(DENIED)
    return subject, employee


def instance_for(item: PersonalDataRequest) -> WorkflowInstance | None:
    return WorkflowInstance.objects.filter(
        organization_id=item.organization_id,
        subject_type=SUBJECT,
        subject_id=item.pk,
        version_id=item.enrollment.workflow_version_id,
    ).first()


@transaction.atomic
def configure_enrollment(
    *,
    actor: User,
    organization: Organization,
    family: str,
    source_field: str,
    workflow_version: WorkflowVersion,
    cancellation_allowed: bool,
    reason: str,
) -> PersonalDataEnrollment:
    Organization.objects.select_for_update().get(pk=organization.pk)
    require(actor=actor, organization=organization, code=P.PERSONAL_DATA_CONFIGURE)
    if (
        source_field not in FIELDS
        or family not in {*FAMILIES, "enrolled_contact"}
        or (family in FAMILIES and FAMILIES[family] != source_field)
    ):
        raise ValidationError("فقط فیلد ارتباطی ثبت‌شده قابل درخواست است.")
    if (
        workflow_version.organization_id != organization.pk
        or workflow_version.status != "published"
        or workflow_version.definition.workflow_type.code != SUBJECT
    ):
        raise ValidationError("نسخه منتشرشده مجاز لازم است.")
    if workflow_version.definition.scope:
        raise ValidationError("اطلاعات ارتباطی فرد منبع پروژه یا کارگاه نیست.")
    steps = list(workflow_version.steps.filter(step_type="approval"))
    if (
        len(steps) != 1
        or steps[0].required_permission != P.PERSONAL_DATA_REVIEW
        or steps[0].configuration.get("decision_policy", "any") != "any"
    ):
        raise ValidationError("سیاست به یک تصمیم مجاز پذیرش یا رد نیاز دارد.")
    if any(
        not t.target_step.is_terminal
        for t in steps[0].outgoing_transitions.select_related("target_step")
    ):
        raise ValidationError("پس از یک تصمیم مجاز، درخواست باید نهایی شود.")
    commands = {
        t.domain_command or steps[0].domain_command
        for t in steps[0].outgoing_transitions.all()
    }
    if commands != {SUBJECT + ".accept", SUBJECT + ".reject"}:
        raise ValidationError("هر دو مسیر پذیرش و رد منبع باید صریح باشند.")
    version = (
        PersonalDataEnrollment.objects.filter(
            organization=organization, family=family, source_field=source_field
        ).aggregate(n=Max("version"))["n"]
        or 0
    ) + 1
    return PersonalDataEnrollment.objects.create(
        organization=organization,
        family=family,
        source_field=source_field,
        workflow_version=workflow_version,
        version=version,
        cancellation_allowed=cancellation_allowed,
        reason=reason,
        created_by=actor,
    )


def visible_requests(
    *, actor: User, organization: Organization
) -> tuple[PersonalDataRequest, ...]:
    require(actor=actor, organization=organization, code=P.PERSONAL_DATA_VIEW)
    own_person = None
    try:
        subject, _ = _own(actor=actor, organization=organization)
        own_person = subject.person.pk
    except (PermissionDenied, Employee.DoesNotExist):
        pass
    assigned = set()
    try:
        require(actor=actor, organization=organization, code=P.PERSONAL_DATA_REVIEW)
        require(actor=actor, organization=organization, code=P.EMPLOYEES_VIEW)
        assigned = set(
            list_member_work_items(
                actor=actor, organization=organization, include_terminal=True
            )
            .filter(instance__subject_type=SUBJECT)
            .values_list("instance__subject_id", flat=True)
        )
    except PermissionDenied:
        pass
    rows = (
        PersonalDataRequest.objects.filter(organization=organization)
        .select_related(
            "enrollment__workflow_version",
            "person",
            "work_relationship__legacy_employee",
        )
        .order_by("-created_at")
    )
    return tuple(
        item
        for item in rows
        if (item.requested_by_id == actor.pk and item.person_id == own_person)
        or item.pk in assigned
    )


def get_request(
    *, actor: User, organization: Organization, request_id: object
) -> PersonalDataRequest:
    item = next(
        (
            item
            for item in visible_requests(actor=actor, organization=organization)
            if str(item.pk) == str(request_id)
        ),
        None,
    )
    if item is None:
        raise PermissionDenied(DENIED)
    return item


@transaction.atomic
def submit_change(
    *,
    actor: User,
    organization: Organization,
    enrollment_id: object,
    proposed_value: str,
    reason: str,
    idempotency_key: str,
) -> PersonalDataRequest:
    membership = get_active_membership(user=actor, organization=organization)
    OrganizationMembership.objects.select_for_update().get(pk=membership.pk)
    require(actor=actor, organization=organization, code=P.PERSONAL_DATA_REQUEST)
    require(actor=actor, organization=organization, code=P.PERSONAL_DATA_VIEW)
    subject, employee = _own(actor=actor, organization=organization)
    employee = Employee.objects.select_for_update().get(
        pk=employee.pk, organization=organization
    )
    policy = (
        PersonalDataEnrollment.objects.filter(
            pk=enrollment_id,
            organization=organization,
            workflow_version__status="published",
        )
        .select_related("workflow_version")
        .first()
    )
    if policy is None or policy.source_field not in FIELDS:
        raise ValidationError("فیلد و مسیر مجاز در دسترس نیست.")
    value = Employee._meta.get_field(policy.source_field).clean(
        proposed_value.strip(), employee
    )
    previous = PersonalDataRequest.objects.filter(
        organization=organization, requested_by=actor, idempotency_key=idempotency_key
    ).first()
    if previous:
        if (
            previous.enrollment_id != policy.pk
            or previous.proposed_value != value
            or previous.reason != reason.strip()
        ):
            raise ValidationError("کلید تکرارپذیری برای درخواست دیگری استفاده شده است.")
        return previous
    item = PersonalDataRequest.objects.create(
        organization=organization,
        requested_by=actor,
        person=subject.person,
        work_relationship=subject.current_relationship,
        enrollment=policy,
        previous_value=getattr(employee, policy.source_field),
        proposed_value=value,
        reason=reason.strip(),
        idempotency_key=idempotency_key,
    )
    instance = start_workflow(
        actor=actor,
        organization=organization,
        version_id=policy.workflow_version_id,
        subject_id=item.pk,
        idempotency_key=f"personal-change:{item.pk}",
    )
    usable = False
    for task in instance.work_items.filter(
        status__in=[WorkItemStatus.OPEN, WorkItemStatus.CLAIMED]
    ):
        for candidate in task.candidates.filter(is_active=True).select_related(
            "membership__user"
        ):
            try:
                for code in (
                    P.PERSONAL_DATA_VIEW,
                    P.PERSONAL_DATA_REVIEW,
                    P.EMPLOYEES_VIEW,
                    P.WORK_ITEMS_VIEW,
                    P.WORK_ITEMS_CLAIM,
                    P.WORK_ITEMS_ACT,
                ):
                    require(
                        actor=candidate.membership.user,
                        organization=organization,
                        code=code,
                    )
            except PermissionDenied:
                continue
            usable = True
    if instance.status != "active" or not usable:
        raise ValidationError("مسیر رسیدگی مجاز یافت نشد؛ درخواستی ثبت نشد.")
    return item


@transaction.atomic
def decide_change(
    *,
    actor: User,
    organization: Organization,
    request_id: object,
    work_item_id: object,
    outcome: str,
    reason: str,
    idempotency_key: str,
) -> WorkItem:
    item = get_request(actor=actor, organization=organization, request_id=request_id)
    require(actor=actor, organization=organization, code=P.PERSONAL_DATA_REVIEW)
    if not WorkItem.objects.filter(
        pk=work_item_id,
        organization=organization,
        instance__subject_type=SUBJECT,
        instance__subject_id=item.pk,
    ).exists():
        raise PermissionDenied(DENIED)
    previous = PersonalDataDecision.objects.filter(request=item).first()
    if previous and (
        previous.work_item_id != work_item_id
        or previous.actor_id != actor.pk
        or previous.reason != reason.strip()
    ):
        raise ValidationError("تکرار تصمیم با سابقه ثبت‌شده هم‌خوان نیست.")
    return complete_work_item(
        actor=actor,
        organization=organization,
        work_item_id=work_item_id,
        outcome=outcome,
        idempotency_key=idempotency_key,
        command_context={"employee_visible_reason": reason},
    )


def _decision(
    *,
    subject: PersonalDataRequest,
    actor: User,
    organization: Organization,
    context: dict[str, Any],
    action: str,
    work_item: WorkItem | None = None,
    **kwargs: Any,
) -> None:
    del kwargs
    if subject.organization_id != organization.pk:
        raise PermissionDenied(DENIED)
    reason = context.get("employee_visible_reason", "")
    if not isinstance(reason, str) or not reason.strip():
        raise ValidationError(
            "دلیل قابل نمایش تصمیم لازم است؛ یادداشت داخلی منتشر نمی‌شود."
        )
    if PersonalDataDecision.objects.filter(request=subject).exists():
        raise ValidationError("درخواست قبلاً تعیین تکلیف شده است.")
    if action == "cancelled":
        require(actor=actor, organization=organization, code=P.PERSONAL_DATA_REQUEST)
        if (
            subject.requested_by_id != actor.pk
            or not subject.enrollment.cancellation_allowed
        ):
            raise PermissionDenied(DENIED)
    else:
        membership = require(
            actor=actor, organization=organization, code=P.PERSONAL_DATA_REVIEW
        )
        require(actor=actor, organization=organization, code=P.EMPLOYEES_VIEW)
        if (
            work_item is None
            or work_item.status != WorkItemStatus.CLAIMED
            or work_item.current_assignee_id != membership.pk
            or work_item.instance.subject_id != subject.pk
        ):
            raise PermissionDenied(DENIED)
    if action == "accepted":
        # Exact source/identity revalidation and optimistic comparison under lock.
        # Pin identity and membership through the owning-source mutation.
        OrganizationMembership.objects.select_for_update().get(
            organization=organization, user_id=subject.requested_by_id
        )
        Person.objects.select_for_update().get(
            pk=subject.person_id, organization=organization
        )
        WorkRelationship.objects.select_for_update().get(
            pk=subject.work_relationship_id, organization=organization
        )
        own, employee = _own(actor=subject.requested_by, organization=organization)
        if (
            own.person.pk != subject.person_id
            or own.current_relationship.pk != subject.work_relationship_id
        ):
            raise PermissionDenied(DENIED)
        employee = Employee.objects.select_for_update().get(
            pk=employee.pk, organization=organization
        )
        field = subject.enrollment.source_field
        if field not in FIELDS or getattr(employee, field) != subject.previous_value:
            raise ValidationError(
                "منبع از زمان درخواست تغییر کرده است؛ درخواست جدید لازم است."
            )
        value = Employee._meta.get_field(field).clean(subject.proposed_value, employee)
        setattr(employee, field, value)
        employee.updated_by = actor
        employee.save(update_fields=[field, "updated_by", "updated_at"])
    PersonalDataDecision.objects.create(
        organization=organization,
        request=subject,
        action=action,
        actor=actor,
        work_item=work_item,
        reason=reason.strip(),
    )


def accept_change(**kwargs: Any) -> None:
    return _decision(action="accepted", **kwargs)


def reject_change(**kwargs: Any) -> None:
    return _decision(action="rejected", **kwargs)


def cancel_change_command(**kwargs: Any) -> None:
    return _decision(action="cancelled", **kwargs)


@transaction.atomic
def cancel_change(
    *,
    actor: User,
    organization: Organization,
    request_id: object,
    reason: str,
    idempotency_key: str,
) -> WorkflowInstance:
    item = get_request(actor=actor, organization=organization, request_id=request_id)
    instance = instance_for(item)
    if instance is None:
        raise PermissionDenied(DENIED)
    return cancel_workflow_for_domain(
        actor=actor,
        organization=organization,
        instance_id=instance.pk,
        command_key=SUBJECT + ".cancel",
        reason=reason,
        idempotency_key=idempotency_key,
        command_context={"employee_visible_reason": reason},
    )


def filter_explicit_request_rows(
    *, rows: Sequence[RequestWorkspaceRow], actor: User, organization: Organization
) -> tuple[RequestWorkspaceRow, ...]:
    """The ESS adapter never inherits a conflicting legacy Employee.user link."""
    from apps.payroll.models import PayrollInquiry
    from apps.timekeeping.models import (
        AttendanceCorrectionRequest,
        LeaveMissionRequest,
        OvertimeRequest,
    )

    from .models import WorkRelationship

    subject = resolve_ess_subject(user=actor, organization=organization)
    employee_ids = WorkRelationship.objects.filter(
        organization=organization,
        person=subject.person,
        legacy_employee_id__isnull=False,
    ).values_list("legacy_employee_id", flat=True)
    from .models import HRCertificateRequest
    definitions = {
        "leave": (LeaveMissionRequest, "employee_id"),
        "overtime": (OvertimeRequest, "employee_id"),
        "correction": (AttendanceCorrectionRequest, "attendance__employee_id"),
        "personal_data": (PersonalDataRequest, "work_relationship__legacy_employee_id"),
        "payroll_inquiry": (PayrollInquiry, "work_relationship__legacy_employee_id"),
    }
    allowed = {}
    for key, (model, field) in definitions.items():
        allowed[key] = set(
            model.objects.filter(
                organization=organization,
                requested_by=actor,
                pk__in=[row.source_id for row in rows if row.source_type == key],
                **{field + "__in": employee_ids},
            ).values_list("pk", flat=True)
        )
    allowed["certificate"]=set(HRCertificateRequest.objects.filter(organization=organization,requested_by=actor,person=subject.person,work_relationship__person=subject.person,pk__in=[row.source_id for row in rows if row.source_type=="certificate"]).values_list("pk",flat=True))
    return tuple(
        row for row in rows if row.source_id in allowed.get(row.source_type, set())
    )
