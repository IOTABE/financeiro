"""Production settings: PostgreSQL required, TLS and hardened cookies."""

from __future__ import annotations

import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403

DEBUG = False

_secret = os.getenv("DJANGO_SECRET_KEY", "")
if not _secret or _secret.startswith("dev-only"):
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set in production.")

SECRET_KEY = _secret
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")  # noqa: F405
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be set in production.")

CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")  # noqa: F405
if not CSRF_TRUSTED_ORIGINS:
    raise ImproperlyConfigured("DJANGO_CSRF_TRUSTED_ORIGINS must be set in production.")

if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":  # noqa: F405
    raise ImproperlyConfigured("Production requires PostgreSQL, not SQLite.")

# Password hashing
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

# Transport and cookies
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)  # noqa: F405
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)  # noqa: F405
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "nao-responda@clareza.local")
