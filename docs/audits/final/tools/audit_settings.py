from config.settings.browser_qa import *  # noqa
from pathlib import Path
MEDIA_ROOT = Path("/tmp/claude-0/audit/media")
STORAGES = {"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}
MIDDLEWARE = [m for m in MIDDLEWARE if "whitenoise" not in m]
