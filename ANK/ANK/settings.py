"""
Django settings for ANK project.

- Django 5.2
- Channels + Daphne + channels-redis (Railway Redis)
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
    # ASGI server for Channels
    "daphne",
    # Django
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
]

# ---------------------------
# Middleware
# Order matters:
# - SecurityMiddleware should be early
# - WhiteNoise after SecurityMiddleware
# - corsheaders ideally very high to handle CORS before common
# ---------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # Dev-only CSRF bypass (guarded below)
    # "Events.temp.DevCsrfBypassMiddleware",  # enabled only if DEBUG
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Enable dev-only CSRF bypass if you truly need it locally.
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
        # To use session auth in dev, uncomment below:
        # "DEFAULT_AUTHENTICATION_CLASSES": [
        #     "rest_framework.authentication.SessionAuthentication",
        # ],
        # "DEFAULT_PERMISSION_CLASSES": [
        #     "rest_framework.permissions.IsAuthenticated",
        # ],
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
# Database
# - Uses Postgres if DATABASE_URL is set (Railway)
# - Falls back to SQLite locally
# ---------------------------
if os.getenv("RAILWAY_ENVIRONMENT_ID") or os.getenv("DATABASE_URL"):
    if not DEBUG and not os.getenv("DATABASE_URL"):
        raise ImproperlyConfigured("DATABASE_URL must be set in production")
    DATABASES = {
        "default": dj_database_url.parse(
            os.getenv("DATABASE_URL"),
            conn_max_age=600,
            ssl_require=not DEBUG,
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
# - ALLOWED_HOSTS must be hostnames only
# - CORS/CSRF origins must be absolute URLs with scheme
# ---------------------------
# ALLOWED_HOSTS = hosts_env(
#     "DJANGO_ALLOWED_HOSTS",
#     # Default: your Railway app host; add others as needed
#     "ank-backend-production.up.railway.app,.railway.app",
#     "main.d1h4duu4ni1dhm.amplifyapp.com",
# )
ALLOWED_HOSTS = hosts_env("DJANGO_ALLOWED_HOSTS", "*")


CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://ank-test.vercel.app",
    "https://main.d1h4duu4ni1dhm.amplifyapp.com",
]


CSRF_TRUSTED_ORIGINS = csv_env(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,https://*.railway.app,https://ank-test.vercel.app,https://main.d1h4duu4ni1dhm.amplifyapp.com",
    "https://main.d1h4duu4ni1dhm.amplifyapp.com",
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
# Channels (Redis in prod; in-memory fallback for local)
# ---------------------------
REDIS_URL = os.getenv("REDIS_URL", "")

if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [
                    {
                        "address": REDIS_URL,  # e.g. rediss://:<token>@endpoint:6379/0
                        "ssl": True,
                        "ssl_cert_reqs": None,  # relax for now; tighten later with a CA bundle
                    }
                ],
            },
        }
    }
else:
    if not DEBUG:
        raise ImproperlyConfigured("REDIS_URL must be set in production for Channels")
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}


# if REDIS_URL:
#     CACHES = {
#         "default": {
#             "BACKEND": "django_redis.cache.RedisCache",
#             "LOCATION": REDIS_URL,
#             "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
#             "TIMEOUT": 300,
#         }
#     }

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
else:
    SESSION_COOKIE_SAMESITE = "None"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SAMESITE = "None"
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = False
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 7  # 1 week; raise once verified
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# ---------------------------
# Logging — keep console visible on Railway
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


# """
# Django settings for ANK project.

# Generated by 'django-admin startproject' using Django 5.2.3.

# For more information on this file, see
# https://docs.djangoproject.com/en/5.2/topics/settings/

# For the full list of settings and their values, see
# https://docs.djangoproject.com/en/5.2/ref/settings/
# """

# from pathlib import Path
# from datetime import timedelta
# import os
# from dotenv import load_dotenv
# import dj_database_url

# # Load environment variables from .env file
# load_dotenv()

# # Build paths inside the project like this: BASE_DIR / 'subdir'.
# BASE_DIR = Path(__file__).resolve().parent.parent


# # SECURITY WARNING: keep the secret key used in production secret!
# SECRET_KEY = os.getenv("SECRET_KEY")

# # SECURITY WARNING: don't run with debug turned on in production!
# DEBUG = os.getenv("DEBUG", "False") == "True"


# def get_bool_env(var_name, default=False):
#     val = os.getenv(var_name, str(default))
#     print(f"DEBUG: {var_name}={val} (raw from env)")
#     return val.lower() in ("1", "true", "yes", "on")


# USE_JWT = get_bool_env("USE_JWT", False)
# print("USE_JWT VALUE AT STARTUP:", USE_JWT)

# # Application definition

# INSTALLED_APPS = [
#     "daphne",
#     "django.contrib.admin",
#     "django.contrib.auth",
#     "django.contrib.contenttypes",
#     "django.contrib.sessions",
#     "django.contrib.messages",
#     "django.contrib.staticfiles",
#     "corsheaders",
#     "whitenoise.runserver_nostatic",
#     "rest_framework",
#     "rest_framework_simplejwt",
#     "rest_framework_simplejwt.token_blacklist",  # for logout/blacklist
#     "Events.apps.EventsConfig",
#     "Guest",
#     "Staff",
#     "CustomField",
#     "Logistics",
#     "MessageTemplates",
#     "drf_spectacular",
#     "channels",
# ]

# MIDDLEWARE = [
#     "corsheaders.middleware.CorsMiddleware",
#     "whitenoise.middleware.WhiteNoiseMiddleware",
#     "django.middleware.common.CommonMiddleware",
#     "django.middleware.security.SecurityMiddleware",
#     "django.contrib.sessions.middleware.SessionMiddleware",
#     "Events.temp.DevCsrfBypassMiddleware",
#     "django.middleware.csrf.CsrfViewMiddleware",
#     "django.contrib.auth.middleware.AuthenticationMiddleware",
#     "django.contrib.messages.middleware.MessageMiddleware",
#     "django.middleware.clickjacking.XFrameOptionsMiddleware",
# ]

# # Enable WhiteNoise compression & caching
# STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
# STATICSTORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"


# ROOT_URLCONF = "ANK.urls"

# if USE_JWT:
#     REST_FRAMEWORK = {
#         "DEFAULT_AUTHENTICATION_CLASSES": [
#             "rest_framework_simplejwt.authentication.JWTAuthentication",
#         ],
#         "DEFAULT_PERMISSION_CLASSES": [
#             "rest_framework.permissions.IsAuthenticated",
#         ],
#         "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
#     }
# else:
#     REST_FRAMEWORK = {
#         # "DEFAULT_AUTHENTICATION_CLASSES": [
#         #     "rest_framework.authentication.SessionAuthentication",
#         # ],
#         # "DEFAULT_PERMISSION_CLASSES": [
#         #     "rest_framework.permissions.IsAuthenticated",
#         # ],
#         "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
#     }

# SIMPLE_JWT = {
#     "ROTATE_REFRESH_TOKENS": False,
#     "BLACKLIST_AFTER_ROTATION": True,
#     "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
#     "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
#     "AUTH_HEADER_TYPES": ("Bearer",),
# }

# SPECTACULAR_SETTINGS = {
#     "TITLE": "ANK ENDPOINTS",
#     "DESCRIPTION": "All the endpoints for the ANK project.",
#     "VERSION": "1.0.0",
#     "SERVE_INCLUDE_SCHEMA": False,
#     "ENUM_NAME_OVERRIDES": {
#         "Logistics.models.TravelDetail.ARRIVAL_CHOICES": "ArrivalMethodEnum",
#         "Logistics.models.TravelDetail.DEPARTURE_CHOICES": "DepartureMethodEnum",
#         "Logistics.models.TravelDetail.ARRIVAL_CHOICES": "TravelModeEnum",
#     },
# }

# TEMPLATES = [
#     {
#         "BACKEND": "django.template.backends.django.DjangoTemplates",
#         "DIRS": [],
#         "APP_DIRS": True,
#         "OPTIONS": {
#             "context_processors": [
#                 "django.template.context_processors.request",
#                 "django.contrib.auth.context_processors.auth",
#                 "django.contrib.messages.context_processors.messages",
#             ],
#         },
#     },
# ]

# WSGI_APPLICATION = "ANK.wsgi.application"
# ASGI_APPLICATION = "ANK.asgi.application"


# # Database
# # https://docs.djangoproject.com/en/5.2/ref/settings/#databases

# if os.getenv("RAILWAY_ENVIRONMENT_ID", None) or os.getenv("DATABASE_URL", None):
#     DATABASES = {
#         "default": dj_database_url.parse(
#             os.getenv("DATABASE_URL"),
#             conn_max_age=600,
#             ssl_require=not DEBUG,
#         )
#     }
# else:
#     DATABASES = {
#         "default": {
#             "ENGINE": "django.db.backends.sqlite3",
#             "NAME": BASE_DIR / "db.sqlite3",
#         }
#     }

# # Password validation
# # https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

# AUTH_PASSWORD_VALIDATORS = [
#     {
#         "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
#     },
#     {
#         "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
#     },
#     {
#         "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
#     },
#     {
#         "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
#     },
# ]


# # Internationalization
# # https://docs.djangoproject.com/en/5.2/topics/i18n/

# LANGUAGE_CODE = "en-us"

# TIME_ZONE = "UTC"

# USE_I18N = True

# USE_TZ = True


# # Static files (CSS, JavaScript, Images)
# # https://docs.djangoproject.com/en/5.2/howto/static-files/

# STATIC_URL = "static/"
# STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
# STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []
# # Default primary key field type
# # https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

# DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# CORS_ALLOW_ALL_ORIGINS = False
# CORS_ALLOW_CREDENTIALS = True
# CORS_ALLOW_HEADERS = [
#     "content-type",
#     "authorization",
#     "x-requested-with",
#     "accept",
#     "origin",
#     "x-csrftoken",
# ]
# CORS_ALLOW_METHODS = [
#     "GET",
#     "POST",
#     "PATCH",
#     "PUT",
#     "DELETE",
#     "OPTIONS",
# ]


# def csv_env(name, default=""):
#     return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]


# ALLOWED_HOSTS = csv_env(
#     "DJANGO_ALLOWED_HOSTS", "https://ank-backend-production.up.railway.app"
# )
# CORS_ALLOWED_ORIGINS = csv_env(
#     "DJANGO_CORS_ALLOWED_ORIGINS",
#     "http://localhost:3000,http://127.0.0.1:3000,https://ank-test.vercel.app",
# )
# CSRF_TRUSTED_ORIGINS = csv_env(
#     "DJANGO_CSRF_TRUSTED_ORIGINS",
#     "http://localhost:3000,http://127.0.0.1:3000,https://ank-backend-production.up.railway.app,https://ank-test.vercel.app",
# )

# AUTH_USER_MODEL = "Staff.User"

# # -------------------------------------------------------------
# # Channels (Redis in prod; in-memory fallback for easy local dev)
# # -------------------------------------------------------------
# REDIS_URL = os.getenv("REDIS_URL", "")  # set to "redis://127.0.0.1:6379/0" to use Redis

# if REDIS_URL:
#     CHANNEL_LAYERS = {
#         "default": {
#             "BACKEND": "channels_redis.core.RedisChannelLayer",
#             "CONFIG": {"hosts": [REDIS_URL]},
#         }
#     }
# else:
#     # In-memory layer is perfect for LOCAL single-process testing
#     CHANNEL_LAYERS = {
#         "default": {
#             "BACKEND": "channels.layers.InMemoryChannelLayer",
#         }
#     }

# # -------------------------------------------------------------
# # Logging (helps catch signal/consumer errors in console)
# # -------------------------------------------------------------
# LOGGING = {
#     "version": 1,
#     "disable_existing_loggers": False,
#     "handlers": {"console": {"class": "logging.StreamHandler"}},
#     "root": {"handlers": ["console"], "level": "INFO"},
# }

# # Trust X-Forwarded-* from Railway
# SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# USE_X_FORWARDED_HOST = True


# if DEBUG:
#     SESSION_COOKIE_SAMESITE = "Lax"
#     SESSION_COOKIE_SECURE = False
#     CSRF_COOKIE_SAMESITE = "Lax"
#     CSRF_COOKIE_SECURE = False
# else:
#     SESSION_COOKIE_SAMESITE = "None"
#     SESSION_COOKIE_SECURE = True
#     CSRF_COOKIE_SAMESITE = "None"
#     CSRF_COOKIE_SECURE = True
#     SECURE_SSL_REDIRECT = True
#     SECURE_HSTS_SECONDS = 60 * 60 * 24 * 7  # 1 week (raise after verifying)
#     SECURE_HSTS_INCLUDE_SUBDOMAINS = True
#     SECURE_HSTS_PRELOAD = True
