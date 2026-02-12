import os

# Stub Strava env vars so strava.api can import without real credentials
os.environ.setdefault("STRAVA_CLIENT_ID", "0")
os.environ.setdefault("STRAVA_CLIENT_SECRET", "fake-secret")
os.environ.setdefault("STRAVA_ACCESS_TOKEN", "fake-token")
os.environ.setdefault("STRAVA_REFRESH_TOKEN", "fake-refresh")

SECRET_KEY = "test-secret-key"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "strava",
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

USE_TZ = True
