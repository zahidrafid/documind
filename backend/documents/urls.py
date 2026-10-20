from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AskView, DocumentViewSet

router = DefaultRouter()
router.register("documents", DocumentViewSet, basename="document")

urlpatterns = [
    path("ask/", AskView.as_view(), name="ask"),
    *router.urls,
]
