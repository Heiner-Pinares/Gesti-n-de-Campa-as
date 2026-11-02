import os
from pathlib import Path

from dotenv import load_dotenv

from .database import database_config, flag
from .runtime_secrets import secret_key


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEBUG = flag(os.environ, "DEBUG", "false")
SECRET_KEY = secret_key(os.environ, BASE_DIR)
ALLOWED_HOSTS = [value.strip() for value in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if value.strip()]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "portal",
    "validaciones",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {
        "context_processors": [
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
        ]
    },
}]
WSGI_APPLICATION = "config.wsgi.application"
DATABASES = {"default": database_config(os.environ, BASE_DIR)}
AUTH_USER_MODEL = "portal.PortalUser"
AUTHENTICATION_BACKENDS = ["portal.auth_backends.PortalBackend"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "es-pe"
TIME_ZONE = "America/Lima"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
SESSION_COOKIE_NAME = "gestion_campanas_session"
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = flag(os.environ, "COOKIE_SECURE", "false")
CSRF_COOKIE_SECURE = flag(os.environ, "COOKIE_SECURE", "false")
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
CSRF_TRUSTED_ORIGINS = [value.strip() for value in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if value.strip()]
if flag(os.environ, "TRUST_PROXY_HTTPS", "false"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Declaración visible: el código nunca aplica migraciones automáticamente.
AUTO_MIGRATE = flag(os.environ, "AUTO_MIGRATE", "false")


def project_path(name, default):
    value = Path(os.getenv(name, default))
    return value if value.is_absolute() else BASE_DIR / value


CAMPAIGNS_CSV_PATH = project_path(
    "CAMPAIGNS_CSV_PATH", "data/incoming/CFG_CAMPANAS_PORTABILIDAD.csv"
)
BASE_CF_CSV_PATH = project_path(
    "BASE_CF_CSV_PATH", "data/incoming/BASE_CF_BASICO.csv"
)
COMMERCIAL_XLSX_PATH = project_path(
    "COMMERCIAL_XLSX_PATH", "data/incoming/Consolidado de Movil Masivo_Negocios.xlsx"
)
CAMPAIGN_SOURCE = os.getenv("CAMPAIGN_SOURCE", "oracle").strip().lower()
