"""Base settings shared by every environment."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parents[3]
SRC_DIR = BASE_DIR / "src"


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def database_config() -> dict:
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        parsed = urlparse(url)
        if parsed.scheme in {"postgres", "postgresql"}:
            return {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": parsed.path.lstrip("/") or "clareza",
                "USER": parsed.username or "clareza",
                "PASSWORD": parsed.password or "",
                "HOST": parsed.hostname or "db",
                "PORT": str(parsed.port or 5432),
                "CONN_MAX_AGE": 60,
                "OPTIONS": {"connect_timeout": 5},
            }
        if parsed.scheme == "sqlite":
            return {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": parsed.path or str(BASE_DIR / "db.sqlite3"),
            }
        raise ImproperlyConfigured(f"Unsupported DATABASE_URL scheme: {parsed.scheme}")

    if os.getenv("POSTGRES_DB"):
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", "clareza"),
            "USER": os.getenv("POSTGRES_USER", "clareza"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
            "HOST": os.getenv("POSTGRES_HOST", "db"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,
            "OPTIONS": {"connect_timeout": 5},
        }

    return {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(BASE_DIR / "db.sqlite3"),
    }


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:8000")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.accounts",
    "apps.core",
    "apps.finance",
    "apps.debts",
    "apps.plans",
    "apps.reports",
    "apps.notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.middleware.RequestIDMiddleware",
    "apps.core.middleware.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [SRC_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.app_meta",
                "apps.notifications.context_processors.notifications",
            ],
        },
    },
]

DATABASES = {"default": database_config()}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "core:landing"

LANGUAGE_CODE = "pt-br"
TIME_ZONE = os.getenv("APP_TIME_ZONE", "America/Sao_Paulo")
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [SRC_DIR / "locale"]

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [SRC_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
APP_NAME = os.getenv("APP_NAME", "Clareza Financeira")
APP_VERSION = "0.1.0"
APP_CURRENCY = os.getenv("APP_CURRENCY", "BRL")

# Email: console by default; SMTP is enabled via env in Docker/production.
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "1025"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "nao-responda@clareza.local")

# Cache / Celery
REDIS_URL = os.getenv("REDIS_URL", "").strip()
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "TIMEOUT": 300,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "clareza-local",
        }
    }

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL or "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL or "redis://localhost:6379/2")
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_TRACK_STARTED = True
CELERY_BEAT_SCHEDULE = {
    "materialize-recurrences": {
        "task": "apps.finance.tasks.materialize_recurrences",
        "schedule": 60 * 60 * 24,
    },
    "send-due-reminders": {
        "task": "apps.notifications.tasks.send_due_reminders",
        "schedule": 60 * 60 * 24,
    },
}

# Security defaults (hardened again in production settings)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = int(os.getenv("SESSION_COOKIE_AGE", "3600"))
SESSION_SAVE_EVERY_REQUEST = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = CSRF_TRUSTED_ORIGINS
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

LOGIN_RATE_LIMIT = int(os.getenv("LOGIN_RATE_LIMIT", "5"))
REGISTER_RATE_LIMIT = int(os.getenv("REGISTER_RATE_LIMIT", "10"))
PASSWORD_RESET_RATE_LIMIT = int(os.getenv("PASSWORD_RESET_RATE_LIMIT", "3"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "config.logging.JsonFormatter"},
        "simple": {"format": "%(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json" if os.getenv("LOG_FORMAT") == "json" else "simple",
        }
    },
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "apps": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
