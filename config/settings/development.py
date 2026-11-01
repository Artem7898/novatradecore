"""Local development settings; ingestion still requires a configured service token."""

# pyright: reportConstantRedefinition=false

import os

from .base import *  # noqa: F403

DEBUG = True
SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-development-only-not-for-deployment")
ALLOWED_HOSTS = [
    host.strip() for host in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",") if host.strip()
]
