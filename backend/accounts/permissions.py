from django.conf import settings
from rest_framework.permissions import SAFE_METHODS, BasePermission


def is_demo_user(user):
    return (
        bool(settings.DEMO_USERNAME)
        and user.is_authenticated
        and user.get_username() == settings.DEMO_USERNAME
    )


class DemoReadOnly(BasePermission):
    message = "The demo account is read-only. Create your own account to upload or delete documents."

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or not is_demo_user(request.user)
