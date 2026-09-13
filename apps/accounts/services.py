from collections.abc import Mapping

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.models import User


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
