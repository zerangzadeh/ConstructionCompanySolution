from collections.abc import Mapping

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event


@transaction.atomic
def update_personal_settings(*, user: User, data: Mapping[str, object]) -> User:
    """Update the explicit self-service profile fields for one user."""

    locked_user = User.objects.select_for_update().get(pk=user.pk)
    old_image_name = locked_user.profile_image.name
    for field_name in ("first_name", "last_name", "email", "phone_number"):
        setattr(locked_user, field_name, data[field_name])
    locked_user.profile_image = data["profile_image"]
    locked_user.full_clean(exclude=["password"])
    locked_user.save(
        update_fields=[
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "profile_image",
            "updated_at",
        ]
    )

    new_image_name = locked_user.profile_image.name
    if old_image_name and old_image_name != new_image_name:
        storage = locked_user.profile_image.storage
        transaction.on_commit(lambda: storage.delete(old_image_name))
    return locked_user


@transaction.atomic
def change_personal_password(
    *, user: User, current_password: str, new_password: str
) -> User:
    """Change an authenticated user's password through a focused service."""

    locked_user = User.objects.select_for_update().get(pk=user.pk)
    if not locked_user.check_password(current_password):
        raise ValidationError(
            "گذرواژه فعلی در همین لحظه تغییر کرده است؛ دوباره تلاش کنید."
        )
    locked_user.set_password(new_password)
    locked_user.save(update_fields=["password", "updated_at"])
    return locked_user


@transaction.atomic
def initialize_personal_password(*, user: User, new_password: str) -> User:
    """Replace a temporary password and release the first-login restriction."""

    locked_user = User.objects.select_for_update().get(pk=user.pk)
    if not locked_user.must_change_password:
        raise ValidationError("تغییر اجباری گذرواژه برای این حساب فعال نیست.")
    locked_user.set_password(new_password)
    locked_user.must_change_password = False
    locked_user.save(update_fields=["password", "must_change_password", "updated_at"])
    record_audit_event(
        action=AuditAction.USER_PASSWORD_INITIALIZED,
        entity_type="user",
        entity_id=locked_user.pk,
        actor=locked_user,
        metadata={"target_username": locked_user.username},
    )
    return locked_user
