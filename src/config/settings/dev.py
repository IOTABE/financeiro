"""Development settings: SQLite by default, console email, relaxed hosts."""

from __future__ import annotations

import os

from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["*"]
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8025",
]

EMAIL_BACKEND = os.getenv(  # noqa: F405
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)

# Fast hashing keeps the test suite quick; production uses the default hashers.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
