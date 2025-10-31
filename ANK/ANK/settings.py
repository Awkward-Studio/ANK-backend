"""
Django settings for ANK project.

- Django 5.2
- Channels + Daphne + channels-redis
- WhiteNoise for static
- Postgres via dj_database_url in prod
"""

from pathlib import Path
from datetime import timedelta
import os
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv
import dj_database_url

# ---------------------------
# Load .env for local dev
# ---------------------------
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


# ---------------------------
# Helpers
# ---------------------------
def get_bool_env(var_name: str, default: bool = False) -> bool:
    raw = os.getenv(var_name, str(default))
    return raw.lower() in ("1", "true", "yes", "on")


def csv_env(name: str, default: str = "") -> list[str]:
    """Split comma-separated env, strip blanks."""
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]


def hosts_env(name: str, default: str = "") -> list[str]:
    """
    ALLOWED_HOSTS must be hostnames, not schemes.
    This strips http(s):// and any leading/trailing slashes.
    """
    items = csv_env(name, default)
    cleaned = []
    for v in items:
        v = v.replace("https://", "").replace("http://", "").strip().strip("/")
        if v:
            cleaned.append(v)
    return cleaned


# ---------------------------
# Core toggles
# ---------------------------
SECRET_KEY = os.getenv("SECRET_KEY")
DEBUG = get_bool_env("DEBUG", False)
USE_JWT = get_bool_env("USE_JWT", False)

if not DEBUG and not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY must be set when DEBUG=False")

# ---------------------------
# Installed apps
# ---------------------------
INSTALLED_APPS = [
    "daphne",  # ASGI server for Channels
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "corsheaders",
    "whitenoise.runserver_nostatic",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "channels",
    # Project apps
    "Events.apps.EventsConfig",
    "Guest",
    "Staff",
    "CustomField",
    "Logistics",
    "MessageTemplates",
    "Departments.apps.DepartmentsConfig",
]

# ---------------------------
# Middleware
# ---------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Dev-only CSRF bypass if DEBUG
if DEBUG:
    MIDDLEWARE.insert(5, "Events.temp.DevCsrfBypassMiddleware")

# ---------------------------
# URL / WSGI / ASGI
# ---------------------------
ROOT_URLCONF = "ANK.urls"
WSGI_APPLICATION = "ANK.wsgi.application"
ASGI_APPLICATION = "ANK.asgi.application"

# ---------------------------
# REST Framework
# ---------------------------
if USE_JWT:
    REST_FRAMEWORK = {
        "DEFAULT_AUTHENTICATION_CLASSES": [
            "rest_framework_simplejwt.authentication.JWTAuthentication",
        ],
        "DEFAULT_PERMISSION_CLASSES": [
            "rest_framework.permissions.IsAuthenticated",
        ],
        "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    }
else:
    REST_FRAMEWORK = {
        "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    }

SIMPLE_JWT = {
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": True,
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "ANK ENDPOINTS",
    "DESCRIPTION": "All the endpoints for the ANK project.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "ENUM_NAME_OVERRIDES": {
        "Logistics.models.TravelDetail.ARRIVAL_CHOICES": "ArrivalMethodEnum",
        "Logistics.models.TravelDetail.DEPARTURE_CHOICES": "DepartureMethodEnum",
        "Logistics.models.TravelDetail.TRAVEL_CHOICES": "TravelModeEnum",
    },
}

# ---------------------------
# Templates
# ---------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------
# Database (AWS ECS + Secrets)
# ---------------------------
if os.getenv("DATABASE_URL"):
    DATABASES = {
        "default": dj_database_url.parse(
            os.getenv("DATABASE_URL"),
            conn_max_age=600,
            ssl_require=False,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ---------------------------
# Password validation
# ---------------------------
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------
# I18N / TZ
# ---------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------
# Static files (WhiteNoise)
# ---------------------------
STATIC_URL = "static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ---------------------------
# Host/CORS/CSRF
# ---------------------------
ALLOWED_HOSTS = ["*"]

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = csv_env(
    "DJANGO_CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,https://ank-test.vercel.app,https://ank-test-git-omi-awkwards-projects.vercel.app",
)

CSRF_TRUSTED_ORIGINS = csv_env(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    # "http://localhost:3000,http://127.0.0.1:3000,https://ank-test.vercel.app,https://ank-test-git-omi-awkwards-projects.vercel.app",
    "https://*,http://*"
)

CORS_ALLOW_HEADERS = [
    "content-type",
    "authorization",
    "x-requested-with",
    "accept",
    "origin",
    "x-csrftoken",
]

CORS_ALLOW_METHODS = ["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"]

# ---------------------------
# Auth
# ---------------------------
AUTH_USER_MODEL = "Staff.User"

# ---------------------------
# Channels (Redis in prod; fallback for dev)
# ---------------------------
REDIS_URL = os.getenv("REDIS_URL", "")

if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }
else:
    if not DEBUG:
        raise ImproperlyConfigured("REDIS_URL must be set in production for Channels")
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# ---------------------------
# Security / Proxy headers
# ---------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
if DEBUG:
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SECURE = False
    # CSRF_COOKIE_SAMESITE = "Lax"
    # CSRF_COOKIE_SECURE = False
else:
    SESSION_COOKIE_SAMESITE = "None"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SAMESITE = "None"
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = False
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 7
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# ---------------------------
# Logging
# ---------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

# ---------------------------
# Default PK
# ---------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
