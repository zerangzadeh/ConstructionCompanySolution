"""Platform operations on login identities, separate from tenant delegation."""

from collections.abc import Mapping
from datetime import datetime, timedelta
from functools import lru_cache
from secrets import token_urlsafe
from uuid import UUID, uuid4

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.contrib.auth.password_validation import (
    CommonPasswordValidator,
    MinimumLengthValidator,
    NumericPasswordValidator,
    UserAttributeSimilarityValidator,
    get_default_password_validators,
    validate_password,
)
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import Exists, OuterRef, Q, QuerySet
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from apps.accounts.forms import PublicPasswordResetRequestForm
from apps.accounts.models import User
from apps.accounts.recovery import account_recovery_tokens
from apps.audit.models import AuditAction, AuditEvent
from apps.audit.services import record_audit_event
from apps.organizations.access_services import (
    lock_platform_duty_change,
    protect_last_platform_admin,
)
from apps.organizations.authorization import (
    is_platform_admin,
    membership_is_tenant_owner,
)
from apps.organizations.models import (
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
    PlatformRoleAssignment,
    PlatformRoleCode,
)
from apps.organizations.platform_grants import lock_platform_admin
from core.identifiers import canonicalize_lower_identifier

P = BusinessPermissionCode
ACCOUNT_AUDIT_ACTIONS = (
    AuditAction.USER_ACCOUNT_CREATED,
    AuditAction.USER_ACCOUNT_UPDATED,
    AuditAction.USER_ACCOUNT_STATUS_CHANGED,
    AuditAction.USER_PASSWORD_RESET_REQUESTED,
    AuditAction.USER_PASSWORD_RESET_COMPLETED,
)
EDITABLE_FIELDS = ("first_name", "last_name", "phone_number")
MAX_TEMPORARY_PASSWORD_LENGTH = 256


@lru_cache(maxsize=1)
def _fallback_temporary_password_validators():
    return (
        MinimumLengthValidator(min_length=12),
        CommonPasswordValidator(),
        NumericPasswordValidator(),
        UserAttributeSimilarityValidator(),
    )


def temporary_password_validators():
    return (
        get_default_password_validators() or _fallback_temporary_password_validators()
    )


def user_management_permissions(actor: User) -> set[str]:
    if not is_platform_admin(actor):
        return set()
    return set(
        BusinessPermission.objects.filter(
            code__in=(
                P.PLATFORM_ADMIN_USERS_VIEW,
                P.PLATFORM_ADMIN_USERS_MANAGE,
                P.PLATFORM_ADMIN_USERS_RECOVER,
            ),
            is_active=True,
        ).values_list("code", flat=True)
    )


def require_user_management_permission(
    actor: User, permission: BusinessPermissionCode = P.PLATFORM_ADMIN_USERS_VIEW
) -> set[str]:
    granted = user_management_permissions(actor)
    if P.PLATFORM_ADMIN_USERS_VIEW not in granted or permission not in granted:
        raise PermissionDenied("اجازه مدیریت کاربران سامانه را ندارید.")
    return granted


def platform_user_directory() -> QuerySet[User]:
    now = timezone.now()
    duties = PlatformRoleAssignment.objects.filter(
        user_id=OuterRef("pk"),
        revoked_at__isnull=True,
    ).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
    return User.objects.annotate(
        platform_admin_effective=Exists(
            duties.filter(
                role=PlatformRoleCode.PLATFORM_ADMIN,
                starts_at__lte=now,
                user__is_active=True,
            )
        ),
        technical_duty=Exists(duties.exclude(role=PlatformRoleCode.PLATFORM_ADMIN)),
        platform_admin_duty=Exists(duties.filter(role=PlatformRoleCode.PLATFORM_ADMIN)),
    )


def protected_account(user: User) -> bool:
    return user.is_staff or user.is_superuser or user.technical_duty


def can_issue_temporary_password(*, actor: User, target: User) -> bool:
    return (
        actor.pk != target.pk
        and target.is_active
        and target.blocked_at is None
        and not protected_account(target)
        and not target.platform_admin_duty
        and target.has_usable_password()
    )


def _locked_target(
    actor: User, user_id: UUID, permission: BusinessPermissionCode
) -> tuple[User, User]:
    lock_platform_duty_change()
    actor = lock_platform_admin(actor)
    require_user_management_permission(actor, permission)
    target = platform_user_directory().select_for_update(of=("self",)).get(pk=user_id)
    if protected_account(target) or target.blocked_at is not None:
        raise PermissionDenied(
            "تغییر این حساب حفاظت‌شده یا مسدود از این مسیر مجاز نیست."
        )
    return actor, target


def _audit(*, actor: User, target: User, action: str, **metadata: object) -> None:
    record_audit_event(
        action=action,
        entity_type="user",
        entity_id=target.pk,
        actor=actor,
        metadata={"control_plane": True, **metadata},
    )


@transaction.atomic
def create_platform_user(*, actor: User, data: Mapping[str, str]) -> User:
    lock_platform_duty_change()
    actor = lock_platform_admin(actor)
    require_user_management_permission(actor, P.PLATFORM_ADMIN_USERS_MANAGE)
    target = User(
        username=canonicalize_lower_identifier(data["username"]),
        email=data["email"].strip().lower(),
        **{field: data[field].strip() for field in EDITABLE_FIELDS},
        must_change_password=True,
    )
    if not target.email:
        raise ValidationError(
            {"email": "ایمیل برای دریافت پیوند تعیین گذرواژه الزامی است."}
        )
    if User.objects.filter(email__iexact=target.email).exists():
        raise ValidationError({"email": "این ایمیل پیش‌تر برای یک حساب ثبت شده است."})
    # Only the account holder can set the initial credential through email recovery.
    target.set_password(token_urlsafe(48))
    target.full_clean()
    target.save()
    _audit(actor=actor, target=target, action=AuditAction.USER_ACCOUNT_CREATED)
    return target


def _check_version(target: User, expected_updated_at: datetime) -> None:
    if target.updated_at != expected_updated_at:
        raise ValidationError("حساب تغییر کرده است. صفحه را تازه‌سازی کنید.")


@transaction.atomic
def update_platform_user(
    *,
    actor: User,
    user_id: UUID,
    data: Mapping[str, str],
    expected_updated_at: datetime,
) -> None:
    actor, target = _locked_target(actor, user_id, P.PLATFORM_ADMIN_USERS_MANAGE)
    _check_version(target, expected_updated_at)
    changed = []
    for field in EDITABLE_FIELDS:
        value = data[field].strip()
        if value != getattr(target, field):
            setattr(target, field, value)
            changed.append(field)
    if changed:
        target.full_clean()
        target.save(update_fields=[*changed, "updated_at"])
        _audit(
            actor=actor,
            target=target,
            action=AuditAction.USER_ACCOUNT_UPDATED,
            changed_fields=changed,
        )


def _protect_tenant_owners(target: User) -> None:
    # Use the same organization lock as membership role assignment/revocation.
    organization_ids = target.organization_memberships.filter(
        status=MembershipStatus.ACTIVE
    ).values_list("organization_id", flat=True)
    companies = (
        Organization.objects.select_for_update()
        .filter(
            pk__in=organization_ids,
            deleted_at__isnull=True,
            status__in=(OrganizationStatus.ACTIVE, OrganizationStatus.SUSPENDED),
        )
        .order_by("pk")
    )
    for company in companies:
        candidates = list(
            OrganizationMembership.objects.filter(
                organization=company,
                status=MembershipStatus.ACTIVE,
                user__is_active=True,
            )
            .filter(
                Q(role_definition__is_owner=True)
                | Q(role_assignments__role__code=MembershipRole.TENANT_OWNER)
            )
            .select_related("role_definition")
            .distinct()
        )
        owners = {
            member.user_id
            for member in candidates
            if membership_is_tenant_owner(member)
        }
        if owners == {target.pk}:
            raise PermissionDenied(
                "حساب آخرین مالک فعال یک شرکت قابل غیرفعال‌سازی نیست."
            )


@transaction.atomic
def set_platform_user_active(
    *,
    actor: User,
    user_id: UUID,
    active: bool,
    reason: str,
    expected_updated_at: datetime,
) -> None:
    actor, target = _locked_target(actor, user_id, P.PLATFORM_ADMIN_USERS_MANAGE)
    if not active:
        protect_last_platform_admin(target.pk)
    if actor.pk == target.pk:
        raise PermissionDenied("تغییر وضعیت حساب خود از این مسیر مجاز نیست.")
    if (
        target.platform_admin_duty
        and not BusinessPermission.objects.filter(
            code=P.PLATFORM_ADMIN_MANAGE_OPERATORS, is_active=True
        ).exists()
    ):
        raise PermissionDenied(
            "تغییر وضعیت این حساب به مجوز مدیریت مدیران پلتفرم نیاز دارد."
        )
    _check_version(target, expected_updated_at)
    reason = reason.strip()
    if not reason or len(reason) > 1000:
        raise ValidationError("دلیل عملیات باید بین ۱ تا ۱۰۰۰ نویسه باشد.")
    if target.is_active == active:
        return
    previous = target.account_status
    if not active:
        _protect_tenant_owners(target)
        target.auth_session_revision = uuid4()
    target.is_active = active
    target.save(update_fields=["is_active", "auth_session_revision", "updated_at"])
    _audit(
        actor=actor,
        target=target,
        action=AuditAction.USER_ACCOUNT_STATUS_CHANGED,
        previous_status=previous,
        new_status=target.account_status,
        reason=reason,
    )


def recovery_delivery_configured() -> bool:
    return bool(
        settings.EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend"
        and settings.EMAIL_HOST
        and settings.DEFAULT_FROM_EMAIL
        and settings.DEFAULT_FROM_EMAIL != "noreply@localhost"
    )


@transaction.atomic
@sensitive_variables("temporary_password")
def set_platform_temporary_password(
    *,
    actor: User,
    user_id: UUID,
    temporary_password: str,
    expected_updated_at: datetime,
) -> None:
    """Replace a regular account credential and require first-login initialization."""
    actor, target = _locked_target(actor, user_id, P.PLATFORM_ADMIN_USERS_RECOVER)
    if not can_issue_temporary_password(actor=actor, target=target):
        raise PermissionDenied("تنظیم گذرواژه موقت برای این حساب مجاز نیست.")
    _check_version(target, expected_updated_at)
    if (
        not temporary_password
        or len(temporary_password) > MAX_TEMPORARY_PASSWORD_LENGTH
    ):
        raise ValidationError("طول گذرواژه موقت مجاز نیست.")
    validate_password(
        temporary_password,
        user=target,
        password_validators=temporary_password_validators(),
    )
    if check_password(temporary_password, target.password):
        raise ValidationError("گذرواژه موقت باید با گذرواژه فعلی حساب متفاوت باشد.")
    target.set_password(temporary_password)
    target.must_change_password = True
    target.auth_session_revision = uuid4()
    target.save(
        update_fields=[
            "password",
            "must_change_password",
            "auth_session_revision",
            "updated_at",
        ]
    )
    _audit(
        actor=actor,
        target=target,
        action=AuditAction.USER_PASSWORD_RESET_COMPLETED,
        channel="temporary_password",
    )


class _TargetedRecoveryForm(PublicPasswordResetRequestForm):
    """Reuse Django's token/email context and defer transport until after commit."""

    message: EmailMessage | None = None

    def __init__(self, target: User):
        super().__init__({"email": target.email})
        self.target = target

    def get_users(self, email: str):
        return iter((self.target,))

    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ) -> None:
        subject = "".join(render_to_string(subject_template_name, context).splitlines())
        body = render_to_string(email_template_name, context)
        self.message = EmailMessage(subject, body, from_email, [to_email])


@transaction.atomic
def prepare_platform_user_recovery(
    *, actor: User, user_id: UUID, domain: str, use_https: bool
) -> EmailMessage | None:
    actor, target = _locked_target(actor, user_id, P.PLATFORM_ADMIN_USERS_RECOVER)
    if target.pk == actor.pk:
        raise PermissionDenied("برای بازیابی حساب خود از صفحه ورود استفاده کنید.")
    form = _TargetedRecoveryForm(target)
    if not target.is_active or not target.has_usable_password() or not form.is_valid():
        raise ValidationError("این حساب فعال با ایمیل معتبر و امکان بازیابی نیست.")
    if (
        User.objects.filter(email__iexact=target.email, is_active=True)
        .exclude(pk=target.pk)
        .exists()
    ):
        raise ValidationError("ایمیل این حساب در میان کاربران فعال یکتا نیست.")
    if not recovery_delivery_configured():
        _audit(
            actor=actor,
            target=target,
            action=AuditAction.USER_PASSWORD_RESET_REQUESTED,
            channel="email",
            delivery="unavailable",
        )
        return None
    if not use_https and not settings.DEBUG:
        raise ValidationError(
            "برای درخواست پیوند بازیابی باید از اتصال امن استفاده کنید."
        )
    recent_cutoff = timezone.now() - timedelta(
        seconds=settings.PASSWORD_RESET_THROTTLE_SECONDS
    )
    if (
        AuditEvent.objects.filter(
            action=AuditAction.USER_PASSWORD_RESET_REQUESTED,
            entity_type="user",
            entity_id=str(target.pk),
            created_at__gte=recent_cutoff,
        )
        .filter(
            Q(metadata__delivery__isnull=True) | ~Q(metadata__delivery="unavailable")
        )
        .exists()
    ):
        raise ValidationError("به‌تازگی برای این حساب درخواست بازیابی ثبت شده است.")
    form.save(
        domain_override=domain,
        use_https=use_https,
        token_generator=account_recovery_tokens,
        email_template_name="accounts/emails/password_reset_email.txt",
        subject_template_name="accounts/emails/password_reset_subject.txt",
    )
    _audit(
        actor=actor,
        target=target,
        action=AuditAction.USER_PASSWORD_RESET_REQUESTED,
        channel="email",
    )
    return form.message
