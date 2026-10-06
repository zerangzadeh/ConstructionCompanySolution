import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Local values remain outside source control; deployed environments use process values.
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "development-only-insecure-key")
DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() == "true"

allowed_hosts = os.getenv("DJANGO_ALLOWED_HOSTS", "")
ALLOWED_HOSTS = [host.strip() for host in allowed_hosts.split(",") if host.strip()]

INSTALLED_APPS: list[str] = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.accounts",
    "apps.organizations",
    "apps.audit",
    "apps.accounting",
    "apps.treasury",
    "apps.subledgers",
    "apps.parties",
    "apps.materials",
    "apps.projects",
    "apps.contracts",
    "apps.billing",
    "apps.estimates",
    "apps.expenses",
    "apps.payments",
    "apps.documents",
    "apps.financials",
    "apps.reporting",
    "apps.daily_reports",
    "apps.workforce",
    "apps.timekeeping",
    "apps.payroll",
    "apps.procurement",
    "apps.inventory",
    "apps.equipment",
    "apps.fixed_assets",
    "apps.safety",
    "apps.quality",
    "apps.compliance",
    "apps.partner_qualification",
    "apps.support",
    "apps.knowledge",
    "apps.workflows",
]

MIDDLEWARE: list[str] = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.ForcePasswordChangeMiddleware",
    "apps.organizations.middleware.OrganizationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "financials:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.organizations.context_processors.business_permissions",
            ],
            "builtins": ["apps.accounts.templatetags.erp_format"],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


def _positive_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        value = int(raw_value)
    except ValueError as error:
        raise ImproperlyConfigured(f"{name} must be a positive integer.") from error
    if value <= 0:
        raise ImproperlyConfigured(f"{name} must be a positive integer.")
    return value


def _database_configuration() -> dict:
    options = {
        "sslmode": os.getenv("DB_SSLMODE", "prefer").strip() or "prefer",
        "connect_timeout": _positive_int_env("DB_CONNECT_TIMEOUT", 10),
    }
    ssl_root_certificate = os.getenv("DB_SSLROOTCERT", "").strip()
    if ssl_root_certificate:
        options["sslrootcert"] = ssl_root_certificate

    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", ""),
        "USER": os.getenv("DB_USER", ""),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
        "OPTIONS": options,
    }


DATABASES: dict = {
    "default": _database_configuration(),
}

LANGUAGE_CODE = "fa"
LANGUAGES = [("fa", "فارسی")]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"
DOCUMENT_PROTECTED_ROOT = Path(
    os.getenv("DOCUMENT_PROTECTED_ROOT", str(BASE_DIR / "protected_documents"))
).resolve()
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
