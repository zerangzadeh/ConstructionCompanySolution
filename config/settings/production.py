import os

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
    return value.lower() in {"1", "true", "yes", "on"}


SECRET_KEY = _required_env("DJANGO_SECRET_KEY")
production_allowed_hosts = _required_env("DJANGO_ALLOWED_HOSTS")
ALLOWED_HOSTS = [
    host.strip() for host in production_allowed_hosts.split(",") if host.strip()
]
for database_setting in ("DB_NAME", "DB_USER", "DB_PASSWORD"):
    _required_env(database_setting)

_required_env("DB_HOST")
database_ssl_mode = _required_env("DB_SSLMODE").lower()
if database_ssl_mode != "verify-full":
    raise ImproperlyConfigured(
        "Production PostgreSQL connections must use DB_SSLMODE=verify-full."
    )

SECURE_SSL_REDIRECT = _env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
SESSION_COOKIE_SECURE = _env_bool("DJANGO_SESSION_COOKIE_SECURE", True)
CSRF_COOKIE_SECURE = _env_bool("DJANGO_CSRF_COOKIE_SECURE", True)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool(
    "DJANGO_HSTS_INCLUDE_SUBDOMAINS",
    True,
)
SECURE_HSTS_PRELOAD = _env_bool("DJANGO_HSTS_PRELOAD", True)
X_FRAME_OPTIONS = "DENY"

if _env_bool("DJANGO_USE_X_FORWARDED_PROTO", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

csrf_trusted_origins = os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in csrf_trusted_origins.split(",") if origin.strip()
]
