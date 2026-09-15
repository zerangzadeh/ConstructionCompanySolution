import uuid
from collections.abc import Mapping, MutableMapping
from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import (
    AccountConnectionRequestStatus,
    BusinessPermissionCode,
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationAccountConnectionRequest,
    OrganizationMembership,
    OrganizationRole,
    OrganizationSettings,
    OrganizationStatus,
)
from core.identifiers import canonicalize_lower_identifier

ACTIVE_ORGANIZATION_SESSION_KEY = "active_organization_id"
_LOGO_UNSET = object()
ORGANIZATION_PROFILE_FIELDS = (
    "name",
    "legal_name",
    "slug",
    "registration_number",
    "national_id",
    "economic_code",
    "phone",
    "email",
    "website",
    "province",
    "city",
    "address",
    "postal_code",
)


def _resolve_active_role(role: OrganizationRole | str) -> OrganizationRole:
    if isinstance(role, OrganizationRole):
        role_definition = role
    else:
        try:
            role_definition = OrganizationRole.objects.get(code=role)
        except OrganizationRole.DoesNotExist as exc:
            raise ValueError("نقش انتخاب‌شده معتبر نیست.") from exc
    if not role_definition.is_active:
        raise ValueError("نقش انتخاب‌شده غیرفعال است.")
    return role_definition


def _validate_role_delegation(
    *,
    actor: User,
    actor_membership: OrganizationMembership | None,
    assigned_role: OrganizationRole,
    current_role: OrganizationRole | None = None,
) -> None:
    """Prevent membership managers from delegating privileges they do not hold."""

    if actor.is_superuser or (
        actor_membership is not None and actor_membership.role_definition.is_owner
    ):
        return
    if actor_membership is None:
        raise PermissionDenied("اجازه واگذاری این نقش را ندارید.")
    actor_permissions = set(
        actor_membership.role_definition.permissions.filter(is_active=True).values_list(
            "code", flat=True
        )
    )
    roles_to_compare = [assigned_role]
    if current_role is not None:
        roles_to_compare.append(current_role)
    for role_definition in roles_to_compare:
        role_permissions = set(
            role_definition.permissions.filter(is_active=True).values_list(
                "code", flat=True
            )
        )
        if not role_permissions.issubset(actor_permissions):
            raise PermissionDenied(
                "نمی‌توانید نقشی با اختیارات بیشتر از نقش خود واگذار یا مدیریت کنید."
            )


@transaction.atomic
def create_organization_account(
    *,
    organization: Organization,
    actor: User,
    username: str,
    temporary_password: str,
    role: OrganizationRole | str,
    first_name: str = "",
    last_name: str = "",
    email: str = "",
    phone_number: str = "",
    national_id: str | None = None,
) -> tuple[User, OrganizationMembership]:
    """Create one tenant account with a mandatory first-login password change."""

    actor_membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ACCOUNTS_CREATE,
        message="اجازه ایجاد حساب کاربری برای این شرکت را ندارید.",
    )
    role_definition = _resolve_active_role(role)
    _validate_role_delegation(
        actor=actor,
        actor_membership=actor_membership,
        assigned_role=role_definition,
    )
    normalized_username = canonicalize_lower_identifier(username)
    if not normalized_username:
        raise ValueError("وارد کردن نام کاربری الزامی است.")
    if User.objects.filter(username=normalized_username).exists():
        raise ValueError(
            "این نام کاربری قابل ایجاد نیست؛ برای حساب موجود درخواست اتصال ثبت کنید."
        )
    user = User(
        username=normalized_username,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        email=email.strip().lower(),
        phone_number=phone_number.strip(),
        national_id=national_id or None,
        is_active=True,
        must_change_password=True,
    )
    try:
        validate_password(temporary_password, user=user)
        user.set_password(temporary_password)
        user.full_clean()
        user.save()
    except (IntegrityError, ValidationError) as exc:
        raise ValueError("اطلاعات حساب یا گذرواژه موقت معتبر نیست.") from exc
    membership = OrganizationMembership.objects.create(
        organization=organization,
        user=user,
        role=role_definition.code,
        role_definition=role_definition,
        status=MembershipStatus.ACTIVE,
        joined_at=timezone.now(),
        assigned_by=actor,
    )
    record_audit_event(
        action=AuditAction.ORGANIZATION_ACCOUNT_CREATED,
        entity_type="user",
        entity_id=user.pk,
        organization=organization,
        actor=actor,
        metadata={"target_username": user.username, "role": role_definition.code},
    )
    return user, membership


@transaction.atomic
def request_existing_account_connection(
    *,
    organization: Organization,
    actor: User,
    username: str,
    role: OrganizationRole | str,
) -> OrganizationAccountConnectionRequest | None:
    """Request consent from an exact existing identity without exposing a directory."""

    actor_membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ACCOUNTS_CREATE,
        message="اجازه ثبت درخواست اتصال حساب را ندارید.",
    )
    role_definition = _resolve_active_role(role)
    _validate_role_delegation(
        actor=actor,
        actor_membership=actor_membership,
        assigned_role=role_definition,
    )
    normalized_username = canonicalize_lower_identifier(username)
    try:
        target_user = User.objects.get(
            username=normalized_username,
            is_active=True,
            must_change_password=False,
        )
    except User.DoesNotExist:
        return None
    if OrganizationMembership.objects.filter(
        organization=organization, user=target_user
    ).exists():
        return None
    request_record, created = (
        OrganizationAccountConnectionRequest.objects.get_or_create(
            organization=organization,
            target_user=target_user,
            status=AccountConnectionRequestStatus.PENDING,
            defaults={"role_definition": role_definition, "requested_by": actor},
        )
    )
    if not created:
        return None
    record_audit_event(
        action=AuditAction.ACCOUNT_CONNECTION_REQUESTED,
        entity_type="organization_account_connection_request",
        entity_id=request_record.pk,
        organization=organization,
        actor=actor,
        metadata={
            "target_username": target_user.username,
            "role": role_definition.code,
        },
    )
    return request_record


@transaction.atomic
def respond_to_account_connection_request(
    *,
    target_user: User,
    request_record: OrganizationAccountConnectionRequest,
    accept: bool,
) -> OrganizationAccountConnectionRequest:
    """Accept or reject a pending organization connection as its target identity."""

    locked = (
        OrganizationAccountConnectionRequest.objects.select_for_update()
        .select_related("organization", "role_definition")
        .get(pk=request_record.pk)
    )
    if locked.target_user_id != target_user.pk:
        raise PermissionDenied("این درخواست متعلق به حساب شما نیست.")
    if locked.status != AccountConnectionRequestStatus.PENDING:
        raise ValueError("این درخواست قبلاً پاسخ داده شده است.")
    if not locked.organization.is_active:
        raise PermissionDenied("شرکت فعال نیست.")
    if not locked.role_definition.is_active:
        raise ValueError("نقش پیشنهادی دیگر فعال نیست.")
    if OrganizationMembership.objects.filter(
        organization=locked.organization, user=target_user
    ).exists():
        raise ValueError("این حساب قبلاً به شرکت تخصیص داده شده است.")
    now = timezone.now()
    if accept:
        OrganizationMembership.objects.create(
            organization=locked.organization,
            user=target_user,
            role=locked.role_definition.code,
            role_definition=locked.role_definition,
            status=MembershipStatus.ACTIVE,
            joined_at=now,
            assigned_by=locked.requested_by,
        )
        locked.status = AccountConnectionRequestStatus.ACCEPTED
        action = AuditAction.ACCOUNT_CONNECTION_ACCEPTED
    else:
        locked.status = AccountConnectionRequestStatus.REJECTED
        action = AuditAction.ACCOUNT_CONNECTION_REJECTED
    locked.responded_at = now
    locked.save(update_fields=["status", "responded_at", "updated_at"])
    record_audit_event(
        action=action,
        entity_type="organization_account_connection_request",
        entity_id=locked.pk,
        organization=locked.organization,
        actor=target_user,
        metadata={"target_username": target_user.username},
    )
    return locked


@transaction.atomic
def provision_user_for_organization(
    *, organization: Organization, user: User, actor: User
) -> OrganizationMembership:
    """Assign a new account to a tenant without granting business access."""

    if not actor.is_authenticated or not actor.is_active or not actor.is_superuser:
        raise PermissionDenied("فقط ادمین سامانه می‌تواند کاربر را به شرکت تخصیص دهد.")
    if not organization.is_active:
        raise PermissionDenied("سازمان فعال نیست.")
    if OrganizationMembership.objects.filter(
        organization=organization,
        user=user,
    ).exists():
        raise ValueError("این کاربر قبلاً به شرکت تخصیص داده شده است.")

    membership = OrganizationMembership.objects.create(
        organization=organization,
        user=user,
        role="",
        role_definition=None,
        status=MembershipStatus.PENDING_ROLE,
        assigned_by=actor,
    )
    record_audit_event(
        action=AuditAction.MEMBERSHIP_PROVISIONED,
        entity_type="organization_membership",
        entity_id=membership.pk,
        organization=organization,
        actor=actor,
        metadata={
            "target_user_id": str(user.pk),
            "target_username": user.username,
        },
    )
    return membership


@transaction.atomic
def update_organization_membership(
    *,
    organization: Organization,
    actor: User,
    membership: OrganizationMembership,
    role: OrganizationRole | str,
    status: str,
) -> OrganizationMembership:
    """Update tenant membership access with authorization and audit evidence."""

    locked_organization = Organization.objects.select_for_update().get(
        pk=organization.pk
    )
    if not locked_organization.is_active:
        raise PermissionDenied("سازمان فعال نیست.")

    role_definition = _resolve_active_role(role)
    if status not in MembershipStatus.values or status == MembershipStatus.PENDING_ROLE:
        raise ValueError("وضعیت عضویت معتبر نیست.")

    locked_membership = (
        OrganizationMembership.objects.select_for_update(of=("self",))
        .select_related("user", "role_definition")
        .get(pk=membership.pk)
    )
    if locked_membership.organization_id != locked_organization.pk:
        raise PermissionDenied("عضویت متعلق به این سازمان نیست.")
    required_permissions = []
    if locked_membership.role_definition_id != role_definition.pk:
        required_permissions.append(BusinessPermissionCode.MEMBERSHIP_CHANGE_ROLE)
    if locked_membership.status != status:
        required_permissions.append(BusinessPermissionCode.MEMBERSHIP_CHANGE_STATUS)
    if not required_permissions:
        required_permissions.append(BusinessPermissionCode.MEMBERSHIP_VIEW)
    actor_membership = None
    for required_permission in required_permissions:
        checked_membership = require_business_permission(
            user=actor,
            organization=locked_organization,
            permission=required_permission,
            message="اجازه مدیریت عضویت‌های این شرکت را ندارید.",
        )
        actor_membership = actor_membership or checked_membership
    actor_is_owner = bool(
        actor_membership and actor_membership.role_definition.is_owner
    )
    if (
        not actor.is_superuser
        and not actor_is_owner
        and (
            (
                locked_membership.role_definition_id is not None
                and locked_membership.role_definition.is_owner
            )
            or role_definition.is_owner
        )
    ):
        raise PermissionDenied("فقط مالک می‌تواند نقش مالک را مدیریت کند.")
    _validate_role_delegation(
        actor=actor,
        actor_membership=actor_membership,
        assigned_role=role_definition,
        current_role=locked_membership.role_definition,
    )

    owner_access_removed = (
        locked_membership.role_definition_id is not None
        and locked_membership.role_definition.is_owner
        and locked_membership.status == MembershipStatus.ACTIVE
        and (not role_definition.is_owner or status != MembershipStatus.ACTIVE)
    )
    if (
        owner_access_removed
        and not OrganizationMembership.objects.filter(
            organization=locked_organization,
            role_definition__is_owner=True,
            status=MembershipStatus.ACTIVE,
        )
        .exclude(pk=locked_membership.pk)
        .exists()
    ):
        raise ValueError("سازمان باید حداقل یک مالک فعال داشته باشد.")

    previous_role = (
        locked_membership.role_definition.code
        if locked_membership.role_definition_id is not None
        else None
    )
    previous_status = locked_membership.status
    now = timezone.now()
    if previous_role != role_definition.code:
        record_audit_event(
            action=AuditAction.MEMBERSHIP_ROLE_CHANGED,
            entity_type="organization_membership",
            entity_id=locked_membership.pk,
            organization=locked_organization,
            actor=actor,
            metadata={
                "target_user_id": str(locked_membership.user_id),
                "target_username": locked_membership.user.username,
                "previous_role": previous_role,
                "new_role": role_definition.code,
            },
        )
    if previous_status != status:
        record_audit_event(
            action=AuditAction.MEMBERSHIP_STATUS_CHANGED,
            entity_type="organization_membership",
            entity_id=locked_membership.pk,
            organization=locked_organization,
            actor=actor,
            metadata={
                "target_user_id": str(locked_membership.user_id),
                "target_username": locked_membership.user.username,
                "previous_status": previous_status,
                "new_status": status,
            },
        )

    locked_membership.role_definition = role_definition
    locked_membership.role = role_definition.code
    locked_membership.status = status
    if status == MembershipStatus.ACTIVE and locked_membership.joined_at is None:
        locked_membership.joined_at = now
    update_fields = ["role", "role_definition", "status", "updated_at"]
    if status == MembershipStatus.ACTIVE and locked_membership.joined_at == now:
        update_fields.append("joined_at")
    locked_membership.save(update_fields=update_fields)

    if (
        previous_status == MembershipStatus.PENDING_ROLE
        and status == MembershipStatus.ACTIVE
        and not locked_membership.user.is_active
    ):
        if locked_membership.user.blocked_at is not None:
            raise PermissionDenied("حساب کاربر مسدود است و قابل فعال‌سازی نیست.")
        locked_membership.user.is_active = True
        locked_membership.user.save(update_fields=["is_active", "updated_at"])
        record_audit_event(
            action=AuditAction.USER_ACCOUNT_STATUS_CHANGED,
            entity_type="user",
            entity_id=locked_membership.user.pk,
            actor=actor,
            metadata={
                "target_username": locked_membership.user.username,
                "previous_status": "inactive",
                "new_status": "active",
            },
        )
    return locked_membership


def get_organization_settings(*, organization: Organization) -> OrganizationSettings:
    """Return settings, safely restoring a missing compatibility row if needed."""

    settings_record, _ = OrganizationSettings.objects.get_or_create(
        organization=organization,
        defaults={
            "timezone": organization.timezone,
            "currency": organization.currency,
        },
    )
    return settings_record


@transaction.atomic
def update_organization_settings(
    *,
    organization: Organization,
    updated_by: User,
    timezone_name: str,
    currency: str,
    fiscal_year_start_month: int,
    fiscal_year_start_day: int | None = None,
    language: str | None = None,
    project_code_prefix: str | None = None,
    contract_code_prefix: str | None = None,
    site_code_prefix: str | None = None,
    document_code_prefix: str | None = None,
    logo: object = _LOGO_UNSET,
    profile_data: Mapping[str, str] | None = None,
) -> OrganizationSettings:
    """Update active-company identity and settings through one atomic boundary."""

    locked_organization = Organization.objects.select_for_update().get(
        pk=organization.pk
    )
    if not locked_organization.is_active:
        raise PermissionDenied("سازمان فعال نیست.")
    require_business_permission(
        user=updated_by,
        organization=locked_organization,
        permission=BusinessPermissionCode.COMPANY_SETTINGS_CHANGE,
        message="اجازه به‌روزرسانی تنظیمات این شرکت را ندارید.",
    )

    settings_record = get_organization_settings(organization=locked_organization)
    settings_record.timezone = timezone_name
    settings_record.currency = currency
    settings_record.fiscal_year_start_month = fiscal_year_start_month
    if fiscal_year_start_day is not None:
        settings_record.fiscal_year_start_day = fiscal_year_start_day
    if language is not None:
        settings_record.language = language
    if project_code_prefix is not None:
        settings_record.project_code_prefix = project_code_prefix
    if contract_code_prefix is not None:
        settings_record.contract_code_prefix = contract_code_prefix
    if site_code_prefix is not None:
        settings_record.site_code_prefix = site_code_prefix
    if document_code_prefix is not None:
        settings_record.document_code_prefix = document_code_prefix
    if logo is not _LOGO_UNSET:
        settings_record.logo = logo
    settings_record.full_clean()
    settings_update_fields = [
        "timezone",
        "currency",
        "fiscal_year_start_month",
        "fiscal_year_start_day",
        "language",
        "project_code_prefix",
        "contract_code_prefix",
        "site_code_prefix",
        "document_code_prefix",
        "updated_at",
    ]
    if logo is not _LOGO_UNSET:
        settings_update_fields.append("logo")
    settings_record.save(update_fields=settings_update_fields)

    if profile_data is not None:
        for field_name in ORGANIZATION_PROFILE_FIELDS:
            if field_name in profile_data:
                setattr(locked_organization, field_name, profile_data[field_name])
    locked_organization.timezone = settings_record.timezone
    locked_organization.currency = settings_record.currency
    locked_organization.updated_by = updated_by
    locked_organization.full_clean()
    locked_organization.save(
        update_fields=[
            *ORGANIZATION_PROFILE_FIELDS,
            "timezone",
            "currency",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.ORGANIZATION_SETTINGS_UPDATED,
        entity_type="organization_settings",
        entity_id=settings_record.pk,
        organization=locked_organization,
        actor=updated_by,
        metadata={
            "timezone": settings_record.timezone,
            "currency": settings_record.currency,
            "fiscal_year_start_month": settings_record.fiscal_year_start_month,
            "fiscal_year_start_day": settings_record.fiscal_year_start_day,
            "language": settings_record.language,
            "project_code_prefix": settings_record.project_code_prefix,
            "contract_code_prefix": settings_record.contract_code_prefix,
            "site_code_prefix": settings_record.site_code_prefix,
            "document_code_prefix": settings_record.document_code_prefix,
        },
    )
    return settings_record


@transaction.atomic
def create_organization_with_owner(
    *,
    owner: User,
    name: str,
    slug: str,
    legal_name: str = "",
    registration_number: str = "",
    national_id: str = "",
    economic_code: str = "",
    phone: str = "",
    email: str = "",
    website: str = "",
    province: str = "",
    city: str = "",
    address: str = "",
    postal_code: str = "",
    timezone_name: str = "UTC",
    currency: str = "USD",
    logo: object = None,
    language: str = "fa",
    fiscal_year_start_month: int = 1,
    fiscal_year_start_day: int = 1,
    project_code_prefix: str = "PRJ",
    contract_code_prefix: str = "CTR",
    site_code_prefix: str = "SITE",
    document_code_prefix: str = "DOC",
) -> Organization:
    """Create an organization and its active owner membership atomically."""

    if not owner.is_authenticated or owner._state.adding or not owner.is_active:
        raise ValueError("کاربر واردشده به سامانه الزامی است.")

    organization = Organization(
        name=name,
        legal_name=legal_name,
        slug=canonicalize_lower_identifier(slug),
        registration_number=registration_number,
        national_id=national_id,
        economic_code=economic_code,
        phone=phone,
        email=email,
        website=website,
        province=province,
        city=city,
        address=address,
        postal_code=postal_code,
        timezone=timezone_name,
        currency=currency,
        created_by=owner,
        updated_by=owner,
    )
    organization.full_clean()
    organization.save()
    settings_record = OrganizationSettings(
        organization=organization,
        logo=logo,
        language=language,
        timezone=timezone_name,
        currency=currency,
        fiscal_year_start_month=fiscal_year_start_month,
        fiscal_year_start_day=fiscal_year_start_day,
        project_code_prefix=project_code_prefix,
        contract_code_prefix=contract_code_prefix,
        site_code_prefix=site_code_prefix,
        document_code_prefix=document_code_prefix,
    )
    settings_record.full_clean()
    settings_record.save()
    owner_role = OrganizationRole.objects.get(
        code=MembershipRole.COMPANY_OWNER,
        is_active=True,
        is_owner=True,
    )
    OrganizationMembership.objects.create(
        organization=organization,
        user=owner,
        role=MembershipRole.COMPANY_OWNER,
        role_definition=owner_role,
        status=MembershipStatus.ACTIVE,
        joined_at=timezone.now(),
        assigned_by=None,
    )
    record_audit_event(
        action=AuditAction.ORGANIZATION_CREATED,
        entity_type="organization",
        entity_id=organization.pk,
        organization=organization,
        actor=owner,
        metadata={"name": organization.name},
    )
    from apps.procurement.workflow import (
        ensure_purchase_request_compatibility_workflow,
    )

    transaction.on_commit(
        lambda: ensure_purchase_request_compatibility_workflow(
            organization=organization,
            actor=owner,
        )
    )
    return organization


def create_organization_by_system_admin(
    *,
    actor: User,
    owner: User,
    name: str,
    slug: str,
    legal_name: str = "",
    registration_number: str = "",
    national_id: str = "",
    economic_code: str = "",
    phone: str = "",
    email: str = "",
    website: str = "",
    province: str = "",
    city: str = "",
    address: str = "",
    postal_code: str = "",
    timezone_name: str = "UTC",
    currency: str = "USD",
    logo: object = None,
    language: str = "fa",
    fiscal_year_start_month: int = 1,
    fiscal_year_start_day: int = 1,
    project_code_prefix: str = "PRJ",
    contract_code_prefix: str = "CTR",
    site_code_prefix: str = "SITE",
    document_code_prefix: str = "DOC",
) -> Organization:
    """Create a tenant only when requested by the global system administrator."""

    if (
        not actor.is_authenticated
        or actor._state.adding
        or not actor.is_active
        or not actor.is_superuser
    ):
        raise PermissionDenied("فقط ادمین سامانه می‌تواند شرکت جدید ایجاد کند.")

    return create_organization_with_owner(
        owner=owner,
        name=name,
        slug=slug,
        legal_name=legal_name,
        registration_number=registration_number,
        national_id=national_id,
        economic_code=economic_code,
        phone=phone,
        email=email,
        website=website,
        province=province,
        city=city,
        address=address,
        postal_code=postal_code,
        timezone_name=timezone_name,
        currency=currency,
        logo=logo,
        language=language,
        fiscal_year_start_month=fiscal_year_start_month,
        fiscal_year_start_day=fiscal_year_start_day,
        project_code_prefix=project_code_prefix,
        contract_code_prefix=contract_code_prefix,
        site_code_prefix=site_code_prefix,
        document_code_prefix=document_code_prefix,
    )


def get_valid_memberships(user: Any) -> QuerySet[OrganizationMembership]:
    """Return active memberships for active, non-deleted organizations."""
    if not getattr(user, "is_authenticated", False):
        return OrganizationMembership.objects.none()
    return (
        OrganizationMembership.objects.filter(
            user=user,
            status=MembershipStatus.ACTIVE,
            organization__status=OrganizationStatus.ACTIVE,
            organization__deleted_at__isnull=True,
            organization__archived_at__isnull=True,
            role_definition__is_active=True,
        )
        .select_related("organization", "role_definition")
        .order_by("organization__name")
    )


def get_organization_members(
    *,
    user: User,
    organization: Organization,
    include_inactive: bool = False,
) -> QuerySet[OrganizationMembership]:
    """Return active members only after validating active tenant access."""

    require_business_permission(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.MEMBERSHIP_VIEW,
        message="اجازه مشاهده اعضای این شرکت را ندارید.",
    )
    memberships = OrganizationMembership.objects.filter(organization=organization)
    if not include_inactive:
        memberships = memberships.filter(status=MembershipStatus.ACTIVE)
    return memberships.select_related("user", "role_definition").order_by(
        "user__username"
    )


def resolve_active_organization(
    user: Any,
    organization_id: str | uuid.UUID | None = None,
) -> Organization | None:
    """Resolve an organization the user is allowed to access."""
    memberships = get_valid_memberships(user)
    if organization_id is not None:
        try:
            normalized_id = uuid.UUID(str(organization_id))
        except (TypeError, ValueError, AttributeError):
            return None
        membership = memberships.filter(organization_id=normalized_id).first()
        return membership.organization if membership else None
    if memberships.count() != 1:
        return None
    membership = memberships.first()
    return membership.organization if membership else None


def resolve_session_organization(
    user: Any,
    session: MutableMapping[str, Any],
) -> Organization | None:
    """Resolve and validate the organization stored in the current session."""

    organization_id = session.get(ACTIVE_ORGANIZATION_SESSION_KEY)
    organization = resolve_active_organization(user, organization_id)
    if organization is None and organization_id is not None:
        clear_active_organization(session)
    return organization


def set_active_organization(
    session: MutableMapping[str, Any],
    organization: Organization,
) -> None:
    """Store a validated organization identifier in the current session."""
    session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(organization.pk)


def clear_active_organization(session: MutableMapping[str, Any]) -> None:
    """Remove the active organization from the current session."""
    session.pop(ACTIVE_ORGANIZATION_SESSION_KEY, None)
