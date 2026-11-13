import os
from pathlib import Path
from config.settings.base import *
private = Path(__file__).resolve().parent
DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "integration_frozen", "USER": "gate_local", "PASSWORD": "", "HOST": "127.0.0.1", "PORT": (private/"db-port.txt").read_text(), "OPTIONS": {"sslmode": "disable", "connect_timeout": 5}, "TEST": {"NAME": os.environ.get("GATE_TEST_DB", "test_integration_gate")}}}
SECRET_KEY = (private/"session-secret").read_text()
DEBUG = False
ALLOWED_HOSTS = ["127.0.0.1", "testserver"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
SESSION_COOKIE_NAME = "sessionid"
CSRF_COOKIE_NAME = "gate_csrf"
MEDIA_ROOT = private/"media"
DOCUMENT_PROTECTED_ROOT = private/"protected"
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "integration_gate"}}
PRODUCT_SURFACE_PROFILE = "MVP"
