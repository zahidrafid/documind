from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("api/health/", health),
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("documents.urls")),
    path("api/", include("chat.urls")),
    path("api-auth/", include("rest_framework.urls")),  # login for the browsable API
]
