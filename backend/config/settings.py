"""
Django settings for the editorial workflow backend.

Every secret and every deployment-specific value comes from environment
variables (see .env.example). Nothing sensitive is committed to git.
"""

import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load backend/.env when running locally. On Render the variables are set in
# the dashboard, so this file simply won't exist there.
load_dotenv(BASE_DIR / ".env")


def env_list(name, default=""):
    """Read a comma-separated environment variable into a list of strings."""
    raw_value = os.environ.get(name, default)
    items = []
    for part in raw_value.split(","):
        part = part.strip()
        if part != "":
            items.append(part)
    return items


DEV_SECRET_KEY = "dev-only-insecure-key-change-me-before-deploying"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", DEV_SECRET_KEY)
DEBUG = os.environ.get("DJANGO_DEBUG", "False") == "True"
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

# Render sets RENDER=true and RENDER_EXTERNAL_HOSTNAME (e.g. my-api.onrender.com).
ON_RENDER = os.environ.get("RENDER") == "true"
render_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if render_hostname:
    ALLOWED_HOSTS.append(render_hostname)
if ON_RENDER and SECRET_KEY == DEV_SECRET_KEY:
    # Refuse to run in production with the key that is public in this repository.
    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY in the Render environment.")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    # third party
    "rest_framework",
    "corsheaders",
    # our apps
    "accounts",
    "sections",
    "articles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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

WSGI_APPLICATION = "config.wsgi.application"

# Database: one DATABASE_URL, e.g.
#   postgresql://user:password@host:5432/dbname
# We use PostgreSQL everywhere (local and production) because full-text search
# and the immutable-timeline trigger are Postgres features.
# In production this is Supabase's *Session pooler* URL (port 5432): the direct
# connection is IPv6-only and Render's free tier can't reach it. The session
# pooler also keeps psycopg's prepared statements working, which the
# transaction pooler (port 6543) would break. Supabase requires SSL.
DATABASES = {
    "default": dj_database_url.config(
        env="DATABASE_URL",
        default="postgresql://postgres:postgres@localhost:5432/editorial",
        conn_max_age=600,
        conn_health_checks=True,
        ssl_require=os.environ.get("DATABASE_SSL_REQUIRE", "False") == "True",
    )
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
# All datetimes are stored in UTC. The frontend converts to the viewer's zone.
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# WhiteNoise serves the admin's CSS/JS from gunicorn, compressed and with
# long-lived cache headers (file names include a hash of their content).
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Django REST Framework + JWT
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    # Every endpoint requires login unless a view explicitly says otherwise.
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    # The clickable "browsable API" pages only while developing; production
    # answers in JSON only.
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}
if DEBUG:
    REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"].append("rest_framework.renderers.BrowsableAPIRenderer")

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=8),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

# ---------------------------------------------------------------------------
# CORS: the React app runs on a different domain (Vercel), so the API must
# explicitly allow it. Locally Vite runs on port 5173.
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
# The browser hides response headers from another domain unless they are
# listed here. The CSV download reads its file name from this one.
CORS_EXPOSE_HEADERS = ["Content-Disposition"]

# Render terminates HTTPS in front of the app and tells Django with this header.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "")
# The API uses tokens, not cookies; these protect the Django admin's cookies.
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# Errors go to the console, which is what Render's "Logs" tab shows.
# Refused requests (401/403/404, logged by Django as warnings) are normal and
# would only be noise, so django.request only reports real server errors (5xx).
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {"django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False}},
}
