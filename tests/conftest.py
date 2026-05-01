import os
import django

# Гарантируем, что pytest знает настройки ДО загрузки Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

django.setup()