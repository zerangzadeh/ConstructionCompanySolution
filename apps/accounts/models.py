import uuid
from typing import Any

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models


class UserManager(BaseUserManager["User"]):
    """Manager for creating users identified by username."""

    use_in_migrations = True

    def create_user(
        self,
        username: str,
        password: str | None = None,
        email: str = "",
        **extra_fields: Any,
    ) -> "User":
        if not username:
            raise ValueError("The username is required.")

        user = self.model(
            username=username,
            email=self.normalize_email(email) if email else "",
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        username: str,
        password: str | None = None,
        email: str = "",
        **extra_fields: Any,
    ) -> "User":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("A superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("A superuser must have is_superuser=True.")

        return self.create_user(username, password, email=email, **extra_fields)


class User(AbstractUser):
    """Application user identified by a unique username."""

    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )
    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS: list[str] = []  # noqa: RUF012

    objects = UserManager()

    def __str__(self) -> str:
        return self.username
