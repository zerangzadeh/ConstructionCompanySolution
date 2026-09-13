import uuid
from pathlib import Path
from typing import Any, ClassVar

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

from core.identifiers import canonicalize_lower_identifier
from core.models import TimeStampedModel

MAX_LOGIN_BACKGROUND_SIZE = 8 * 1024 * 1024
MAX_PROFILE_IMAGE_SIZE = 2 * 1024 * 1024
LOGIN_BACKGROUND_SIGNATURES = {
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".webp": (b"RIFF",),
}
LOGIN_BACKGROUND_CONTENT_TYPES = {
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
    ".webp": {"image/webp"},
}
PROFILE_IMAGE_SIGNATURES = LOGIN_BACKGROUND_SIGNATURES
PROFILE_IMAGE_CONTENT_TYPES = LOGIN_BACKGROUND_CONTENT_TYPES


def profile_image_upload_path(instance: "User", filename: str) -> str:
    """Store profile images under a generated, non-user-controlled name."""

    extension = Path(filename).suffix.lower()
    return f"profile-images/{instance.pk}/{uuid.uuid4()}{extension}"


def validate_profile_image(value: object) -> None:
    """Validate profile image size, declared type, extension, and signature."""

    filename = Path(str(getattr(value, "name", ""))).name
    extension = Path(filename).suffix.lower()
    if extension not in PROFILE_IMAGE_SIGNATURES:
        raise ValidationError("تصویر پروفایل باید فایل PNG، JPEG یا WebP باشد.")

    size = getattr(value, "size", 0)
    if size <= 0:
        raise ValidationError("فایل تصویر پروفایل خالی است.")
    if size > MAX_PROFILE_IMAGE_SIZE:
        raise ValidationError("حجم تصویر پروفایل نباید بیشتر از ۲ مگابایت باشد.")

    content_type = getattr(value, "content_type", "")
    if content_type and content_type not in PROFILE_IMAGE_CONTENT_TYPES[extension]:
        raise ValidationError("نوع محتوای تصویر پروفایل با پسوند آن مطابقت ندارد.")

    try:
        position = value.tell()
        header = value.read(12)
        value.seek(position)
    except (AttributeError, OSError):
        return
    valid_signature = any(
        header.startswith(signature)
        for signature in PROFILE_IMAGE_SIGNATURES[extension]
    )
    if extension == ".webp":
        valid_signature = valid_signature and header[8:12] == b"WEBP"
    if not valid_signature:
        raise ValidationError("محتوای فایل تصویر پروفایل معتبر نیست.")


def login_background_upload_path(instance: "LoginPageSettings", filename: str) -> str:
    """Store the public login background under a generated safe name."""

    extension = Path(filename).suffix.lower()
    return f"login-page/{uuid.uuid4()}{extension}"


def validate_login_background(value: object) -> None:
    """Validate the background extension, size, declared type, and signature."""

    filename = Path(str(getattr(value, "name", ""))).name
    extension = Path(filename).suffix.lower()
    if extension not in LOGIN_BACKGROUND_SIGNATURES:
        raise ValidationError("تصویر پس‌زمینه باید فایل PNG، JPEG یا WebP باشد.")

    size = getattr(value, "size", 0)
    if size <= 0:
        raise ValidationError("فایل تصویر پس‌زمینه خالی است.")
    if size > MAX_LOGIN_BACKGROUND_SIZE:
        raise ValidationError("حجم تصویر پس‌زمینه نباید بیشتر از ۸ مگابایت باشد.")

    content_type = getattr(value, "content_type", "")
    if content_type and content_type not in LOGIN_BACKGROUND_CONTENT_TYPES[extension]:
        raise ValidationError("نوع محتوای تصویر پس‌زمینه با پسوند آن مطابقت ندارد.")

    try:
        position = value.tell()
        header = value.read(12)
        value.seek(position)
    except (AttributeError, OSError):
        return
    valid_signature = any(
        header.startswith(signature)
        for signature in LOGIN_BACKGROUND_SIGNATURES[extension]
    )
    if extension == ".webp":
        valid_signature = valid_signature and header[8:12] == b"WEBP"
    if not valid_signature:
        raise ValidationError("محتوای فایل تصویر پس‌زمینه معتبر نیست.")


class AccountStatus(models.TextChoices):
    ACTIVE = "active", "فعال"
    INACTIVE = "inactive", "غیرفعال"
    BLOCKED = "blocked", "مسدود"


def validate_iranian_national_id(value: str) -> None:
    """Validate a ten-digit Iranian national identification code."""

    if len(value) != 10 or not value.isascii() or not value.isdigit():
        raise ValidationError("کد ملی باید دقیقاً ۱۰ رقم باشد.")
    if len(set(value)) == 1:
        raise ValidationError("کد ملی معتبر نیست.")

    remainder = sum(int(value[index]) * (10 - index) for index in range(9)) % 11
    expected_check_digit = remainder if remainder < 2 else 11 - remainder
    if int(value[-1]) != expected_check_digit:
        raise ValidationError("کد ملی معتبر نیست.")


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
        username = canonicalize_lower_identifier(username)
        if not username:
            raise ValueError("وارد کردن نام کاربری الزامی است.")

        user = self.model(
            username=username,
            email=self.normalize_email(email) if email else "",
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def get_by_natural_key(self, username: str) -> "User":
        """Resolve authentication usernames using their canonical form."""

        return self.get(username=canonicalize_lower_identifier(username))

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
            raise ValueError("کاربر ارشد باید مقدار is_staff=True داشته باشد.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("کاربر ارشد باید مقدار is_superuser=True داشته باشد.")

        return self.create_user(username, password, email=email, **extra_fields)


class User(AbstractUser):
    """Application user identified by a unique username."""

    id = models.UUIDField(
        "شناسه",
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )
    email = models.EmailField("ایمیل", blank=True)
    phone_number = models.CharField("شماره تلفن", max_length=32, blank=True)
    profile_image = models.FileField(
        "تصویر پروفایل",
        upload_to=profile_image_upload_path,
        validators=[validate_profile_image],
        max_length=255,
        blank=True,
        help_text="فرمت PNG، JPEG یا WebP با حداکثر حجم ۲ مگابایت.",
    )
    national_id = models.CharField(
        "کد ملی",
        max_length=10,
        unique=True,
        null=True,
        blank=True,
        validators=[validate_iranian_national_id],
    )
    blocked_at = models.DateTimeField("زمان مسدودسازی", null=True, blank=True)
    created_at = models.DateTimeField("زمان ایجاد", auto_now_add=True)
    updated_at = models.DateTimeField("زمان آخرین به‌روزرسانی", auto_now=True)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS: list[str] = []  # noqa: RUF012

    objects = UserManager()

    class Meta(AbstractUser.Meta):
        verbose_name = "کاربر"
        verbose_name_plural = "کاربران"

    def clean(self) -> None:
        super().clean()
        self.username = canonicalize_lower_identifier(self.username)
        self.national_id = self.national_id or None

    def save(self, *args: object, **kwargs: object) -> None:
        self.username = canonicalize_lower_identifier(self.username)
        self.national_id = self.national_id or None
        if self.blocked_at is not None:
            self.is_active = False
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"is_active"}
        super().save(*args, **kwargs)

    @property
    def account_status(self) -> str:
        """Return the effective authentication status without duplicating state."""

        if self.blocked_at is not None:
            return AccountStatus.BLOCKED
        if self.is_active:
            return AccountStatus.ACTIVE
        return AccountStatus.INACTIVE

    @property
    def account_status_label(self) -> str:
        return str(AccountStatus(self.account_status).label)

    def __str__(self) -> str:
        return self.username


class LoginPageSettings(TimeStampedModel):
    """Singleton content settings for the public login page."""

    id = models.PositiveSmallIntegerField(
        "شناسه",
        primary_key=True,
        default=1,
        editable=False,
    )
    panel_label = models.CharField(
        "برچسب بالای پیام",
        max_length=120,
        blank=True,
        default="سامانه یکپارچه مدیریت ساخت",
    )
    panel_title = models.CharField(
        "عنوان پیام",
        max_length=200,
        blank=True,
        default="کنترل پروژه و مالی، در یک فضای کاری منسجم",
    )
    panel_description = models.TextField(
        "متن توضیحی",
        blank=True,
        default=(
            "دسترسی سریع به پروژه‌ها، قراردادها، برآوردها، گزارش‌های روزانه "
            "و اسناد خصوصی سازمان."
        ),
    )
    panel_footer = models.CharField(
        "پیام پایین پنل",
        max_length=200,
        blank=True,
        default="محیط سازمانی امن و چندمستأجری",
    )
    background_image = models.FileField(
        "تصویر پس‌زمینه صفحه",
        upload_to=login_background_upload_path,
        validators=[validate_login_background],
        max_length=255,
        blank=True,
        help_text="فرمت PNG، JPEG یا WebP با حداکثر حجم ۸ مگابایت.",
    )
    panel_image = models.FileField(
        "تصویر پنل تیرهٔ ورود",
        upload_to=login_background_upload_path,
        validators=[validate_login_background],
        max_length=255,
        blank=True,
        help_text=(
            "این تصویر در بخش تیرهٔ معرفی صفحه ورود نمایش داده می‌شود. "
            "فرمت PNG، JPEG یا WebP با حداکثر حجم ۸ مگابایت."
        ),
    )

    class Meta:
        verbose_name = "تنظیمات صفحه ورود"
        verbose_name_plural = "تنظیمات صفحه ورود"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(id=1),
                name="login_page_settings_is_singleton",
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return "تنظیمات صفحه ورود"
