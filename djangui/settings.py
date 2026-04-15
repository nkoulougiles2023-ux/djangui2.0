"""
Django settings for DJANGUI 2.0.

Production targets: PostgreSQL + Redis + Celery + Gunicorn on VPS.
"""
from datetime import timedelta
from pathlib import Path

import dj_database_url
from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("SECRET_KEY", default="dev-insecure-key-change-me")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="localhost,127.0.0.1,.vercel.app,.now.sh",
    cast=Csv(),
)
CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="https://*.vercel.app",
    cast=Csv(),
)

AUTH_USER_MODEL = "accounts.User"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # 3rd party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "django_celery_beat",
    "django_celery_results",
    "drf_spectacular",
    # Local
    "apps.accounts",
    "apps.transactions",
    "apps.loans",
    "apps.tontines",
    "apps.investments",
    "apps.rewards",
    "apps.notifications",
    "apps.admin_dashboard",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "djangui.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "djangui.wsgi.application"
ASGI_APPLICATION = "djangui.asgi.application"

DATABASE_URL = config("DATABASE_URL", default="")
if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL, conn_max_age=0, ssl_require=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME", default="djangui"),
            "USER": config("DB_USER", default="djangui"),
            "PASSWORD": config("DB_PASSWORD", default="djangui"),
            "HOST": config("DB_HOST", default="localhost"),
            "PORT": config("DB_PORT", default="5432"),
            "CONN_MAX_AGE": 60,
        }
    }

# During local bootstrap without Postgres, allow SQLite fallback
if config("USE_SQLITE", default=False, cast=bool):
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }

REDIS_URL = config("REDIS_URL", default="")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
else:
    # Serverless / no-Redis fallback (OTP + throttling degrade gracefully)
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "djangui-local",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Douala"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "30/min",
        "user": "120/min",
        "otp_send": "10/min",
        "pin_login": "5/min",
        "loan_create": "3/min",
        "webhook": "60/min",
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# CORS
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:3000",
    cast=Csv(),
)
CORS_ALLOW_CREDENTIALS = True

# Security headers
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
if not DEBUG:
    # Vercel/proxy terminates TLS — trust X-Forwarded-Proto instead of redirecting.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=False, cast=bool)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Celery
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://localhost:6379/1")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default="redis://localhost:6379/2")
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# Business settings (DJANGUI)
DJANGUI = {
    "COMMISSION_RATE": 10.00,           # % total commission
    "PLATFORM_SHARE": 0.40,              # 4% of loan -> platform
    "INVESTOR_SHARE": 0.30,              # 3% of loan -> investors pool
    "GUARANTOR_SHARE": 0.30,             # 3% of loan -> guarantors
    "TONTINE_COMMISSION_RATE": 0.02,     # 2% per round
    "MIN_REPUTATION_TO_BORROW": 20,
    "MAX_ACTIVE_GUARANTEES": 3,
    "MAX_GUARANTEE_PCT_OF_WALLET": 0.80,
    "FIRST_LOAN_CAP": 15_000,
    "LOAN_EXPIRY_HOURS": 48,
    "GRACE_PERIOD_HOURS": 72,
    "LOAN_COOLDOWN_HOURS": 24,
    "DAILY_DEPOSIT_LIMIT": 500_000,
    "DAILY_WITHDRAW_LIMIT": 300_000,
    "OTP_TTL_SECONDS": 300,
    "OTP_MAX_ATTEMPTS": 3,
    "OTP_MAX_SEND_PER_HOUR": 5,
    "PIN_MAX_ATTEMPTS": 3,
    "PIN_LOCK_MINUTES": 30,
    "INVESTMENT_NOTICE_DAYS": 7,
    "INVESTMENT_MIN": 5_000,
    "TONTINE_MIN_CONTRIBUTION": 500,
    "LOAN_MIN_AMOUNT": 1_000,
}

# Reputation bounds / grid
REPUTATION_GRID = [
    (0, 19, 0, 0),
    (20, 39, 10_000, 14),
    (40, 54, 50_000, 30),
    (55, 69, 100_000, 60),
    (70, 84, 200_000, 60),
    (85, 94, 350_000, 90),
    (95, 100, 500_000, 90),
]

# Mobile Money
MOMO = {
    "MTN_API_KEY": config("MTN_MOMO_API_KEY", default=""),
    "MTN_API_USER": config("MTN_MOMO_API_USER", default=""),
    "MTN_SUBSCRIPTION_KEY": config("MTN_MOMO_SUBSCRIPTION_KEY", default=""),
    "MTN_ENV": config("MTN_MOMO_ENV", default="sandbox"),
    "ORANGE_CLIENT_ID": config("ORANGE_MONEY_CLIENT_ID", default=""),
    "ORANGE_CLIENT_SECRET": config("ORANGE_MONEY_CLIENT_SECRET", default=""),
}

# KYC encryption key (base64-encoded 32 bytes)
KYC_ENCRYPTION_KEY = config("KYC_ENCRYPTION_KEY", default="")

# Sentry (optional)
SENTRY_DSN = config("SENTRY_DSN", default="")
if SENTRY_DSN and not DEBUG:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
    )

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "{levelname} {asctime} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "djangui": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "DJANGUI 2.0 API",
    "DESCRIPTION": "Tontine, épargne, prêt instantané & investissement — Cameroun",
    "VERSION": "1.0.0",
}
