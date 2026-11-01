from django.conf import settings

# Django's helper exposes an untyped default view in its third-party stub.
from django.conf.urls.static import static  # pyright: ignore[reportUnknownVariableType]
from django.contrib import admin
from django.urls import include, path

from config.health import live, ready

urlpatterns = [
    path("health/live/", live, name="health_live"),
    path("health/ready/", ready, name="health_ready"),
    path("admin/", admin.site.urls),
    path("api/v1/trades/", include("trades.api.v1")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
