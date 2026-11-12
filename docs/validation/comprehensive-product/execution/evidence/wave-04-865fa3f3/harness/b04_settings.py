import os
from pathlib import Path
from config.settings.base import *

private = Path(os.environ["B04_TMP"]).resolve(strict=True)
dbname = os.environ["B04_DB"]
assert dbname in {"b04_original", "b04_original2", "b04_retest", "b04_technical"}
DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql", "NAME": dbname, "USER": "b04_local",
    "PASSWORD": "", "HOST": "127.0.0.1", "PORT": (private / "db-port.txt").read_text().strip(),
    "OPTIONS": {"sslmode": "disable", "connect_timeout": 5},
    "TEST": {"NAME": "test_b04_migrated"},
}}
SECRET_KEY = (private / "session-secret").read_text().strip()
DEBUG = False
ALLOWED_HOSTS = ["127.0.0.1", "testserver"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_NAME = dbname + "_session"
CSRF_COOKIE_NAME = dbname + "_csrf"
MEDIA_ROOT = private / dbname / "media"
DOCUMENT_PROTECTED_ROOT = private / dbname / "protected"
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": dbname}}
PRODUCT_SURFACE_PROFILE = "MVP"