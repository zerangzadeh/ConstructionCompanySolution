import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from .base import *

DEBUG = False


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value or value.startswith("replace-with-"):
        raise ImproperlyConfigured(f"{name} must be configured in production.")
    return value


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip().lower()
    if value not in {"1", "true", "yes", "on", "0", "false", "no", "off"}:
        raise ImproperlyConfigured(f"{name} must be a boolean.")
    return value in {"1", "true", "yes", "on"}


SECRET_KEY = _required_env("DJANGO_SECRET_KEY")
if (
    len(SECRET_KEY) < 50
    or len(set(SECRET_KEY)) < 5
    or SECRET_KEY.startswith(("development-", "django-insecure-"))
):
    raise ImproperlyConfigured("Production requires a dedicated strong secret key.")
production_allowed_hosts = _required_env("DJANGO_ALLOWED_HOSTS")
ALLOWED_HOSTS = [
    host.strip() for host in production_allowed_hosts.split(",") if host.strip()
]
if not ALLOWED_HOSTS or any("*" in host for host in ALLOWED_HOSTS):
    raise ImproperlyConfigured("Production requires explicit allowed hosts.")
for database_setting in ("DB_NAME", "DB_USER", "DB_PASSWORD"):
    _required_env(database_setting)

_required_env("DB_HOST")
database_ssl_mode = _required_env("DB_SSLMODE").lower()
if database_ssl_mode != "verify-full":
    raise ImproperlyConfigured(
        "Production PostgreSQL connections must use DB_SSLMODE=verify-full."
    )

SECURE_SSL_REDIRECT = _env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
if not SECURE_SSL_REDIRECT:
    raise ImproperlyConfigured("Production HTTPS redirect must remain enabled.")
SESSION_COOKIE_SECURE = _env_bool("DJANGO_SESSION_COOKIE_SECURE", True)
CSRF_COOKIE_SECURE = _env_bool("DJANGO_CSRF_COOKIE_SECURE", True)
if not SESSION_COOKIE_SECURE or not CSRF_COOKIE_SECURE:
    raise ImproperlyConfigured(
        "Production session and CSRF cookies must use the Secure flag."
    )
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
try:
    SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_HSTS_SECONDS", "31536000"))
except ValueError as error:
    raise ImproperlyConfigured("DJANGO_HSTS_SECONDS must be nonnegative.") from error
if SECURE_HSTS_SECONDS < 0:
    raise ImproperlyConfigured("DJANGO_HSTS_SECONDS must be nonnegative.")
SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool(
    "DJANGO_HSTS_INCLUDE_SUBDOMAINS",
    True,
)
SECURE_HSTS_PRELOAD = _env_bool("DJANGO_HSTS_PRELOAD", True)
X_FRAME_OPTIONS = "DENY"


def _storage_root(name: str) -> Path:
    path = Path(_required_env(name))
    if not path.is_absolute():
        raise ImproperlyConfigured(f"{name} must be an absolute path.")
    resolved = path.resolve()
    if (
        resolved == Path(resolved.anchor)
        or resolved == BASE_DIR
        or resolved in BASE_DIR.parents
    ):
        raise ImproperlyConfigured(f"{name} must be a dedicated storage directory.")
    return resolved


# Deployment hooks select no provider and create no directories. Protected
# documents must never overlap a public static or media serving root.
STATIC_ROOT = _storage_root("DJANGO_STATIC_ROOT")
MEDIA_ROOT = _storage_root("DJANGO_MEDIA_ROOT")
DOCUMENT_PROTECTED_ROOT = _storage_root("DOCUMENT_PROTECTED_ROOT")
_storage_roots = (STATIC_ROOT, MEDIA_ROOT, DOCUMENT_PROTECTED_ROOT)
for index, root in enumerate(_storage_roots):
    for other in _storage_roots[index + 1 :]:
        if root == other or root in other.parents or other in root.parents:
            raise ImproperlyConfigured("Production storage roots must not overlap.")

if _env_bool("DJANGO_USE_X_FORWARDED_PROTO", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

csrf_trusted_origins = os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in csrf_trusted_origins.split(",") if origin.strip()
]

if EMAIL_BACKEND != "django.core.mail.backends.smtp.EmailBackend":
    raise ImproperlyConfigured("Production password recovery requires Django SMTP.")
for email_setting in (
    "DJANGO_EMAIL_HOST",
    "DJANGO_EMAIL_HOST_USER",
    "DJANGO_EMAIL_HOST_PASSWORD",
    "DJANGO_DEFAULT_FROM_EMAIL",
    "DJANGO_CACHE_BACKEND",
    "DJANGO_CACHE_LOCATION",
):
    _required_env(email_setting)
if not EMAIL_USE_TLS:
    raise ImproperlyConfigured("Production password-recovery email must use TLS.")
if CACHES["default"]["BACKEND"] in {
    "django.core.cache.backends.locmem.LocMemCache",
    "django.core.cache.backends.dummy.DummyCache",
}:
    raise ImproperlyConfigured(
        "Production password recovery requires a shared cache backend."
    )
