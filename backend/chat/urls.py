from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AskView, ConversationViewSet

router = DefaultRouter()
router.register("conversations", ConversationViewSet, basename="conversation")

urlpatterns = [
    path("ask/", AskView.as_view(), name="ask"),
    *router.urls,
]
