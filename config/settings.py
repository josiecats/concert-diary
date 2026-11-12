"""Django settings for Concert Diary (v1 prototype)."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    SETLISTFM_CLIENT=(str, "mock"),
    SETLISTFM_API_KEY=(str, ""),
    GOOGLE_CLIENT_ID=(str, ""),
    GOOGLE_CLIENT_SECRET=(str, ""),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="dev-only-insecure-key-change-me")
DEBUG = env("DEBUG", default=True)
# "*" while developing, so a phone on the same Wi-Fi can open http://<your-mac's-IP>:8000.
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"] if DEBUG else ["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# Render sets RENDER_EXTERNAL_HOSTNAME (e.g. concert-diary.onrender.com) on every web service.
RENDER_EXTERNAL_HOSTNAME = env("RENDER_EXTERNAL_HOSTNAME", default="")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")

if not DEBUG:
    if SECRET_KEY.startswith("dev-only"):
        raise environ.ImproperlyConfigured("Set SECRET_KEY in the environment when DEBUG is off.")
    # Render terminates HTTPS at its proxy and forwards plain HTTP.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=3600)
    SECURE_CONTENT_TYPE_NOSNIFF = True

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "accounts",
    "shows",
    "maps",
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
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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

DATABASES = {"default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)

CACHES = {
    "default": env.cache("CACHE_URL", default="locmemcache://concert-diary"),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# allauth: email + password sign-up with a required, unique username (US-1).
ACCOUNT_LOGIN_METHODS = {"email", "username"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"  # prototype only
ACCOUNT_USERNAME_VALIDATORS = "accounts.validators.username_validators"
ACCOUNT_USERNAME_BLACKLIST = ["admin", "accounts", "settings", "onboarding", "search", "diary"]
ACCOUNT_SIGNUP_REDIRECT_URL = "/onboarding/"
LOGIN_REDIRECT_URL = "/"
LOGIN_URL = "account_login"
ACCOUNT_LOGOUT_REDIRECT_URL = "/"

# Google OAuth (US-1). Credentials come from .env only; with no client ID the
# provider has no app, and the log-in/sign-up pages show a disabled button.
GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = env("GOOGLE_CLIENT_SECRET")
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APPS": (
            [{"client_id": GOOGLE_CLIENT_ID, "secret": GOOGLE_CLIENT_SECRET, "key": ""}]
            if GOOGLE_CLIENT_ID
            else []
        ),
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    }
}
# Google users still choose their own username for /u/<username>, then land on onboarding.
SOCIALACCOUNT_AUTO_SIGNUP = False
SOCIALACCOUNT_LOGIN_ON_GET = False

# Prototype: password-reset emails print to the runserver console.
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
# WhiteNoise serves static files in production (compressed, with cache-busting hashed names).
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        if DEBUG
        else "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

# Errors go to stdout so they show up in Render's logs.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# setlist.fm: "mock" reads fixtures/demo_shows.json; "real" calls the API (not built yet).
SETLISTFM_CLIENT = env("SETLISTFM_CLIENT")
SETLISTFM_API_KEY = env("SETLISTFM_API_KEY")
DEMO_SHOWS_FIXTURE = BASE_DIR / "fixtures" / "demo_shows.json"
