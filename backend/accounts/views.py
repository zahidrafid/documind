from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .permissions import is_demo_user
from .serializers import RegisterSerializer, UserSerializer

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def create(self, request, *args, **kwargs):
        if not settings.ALLOW_REGISTRATION:
            return Response(
                {"detail": "Sign-ups are closed right now. Try the demo account instead."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token = Token.objects.create(user=user)
        return Response(
            {"token": token.key, "user": UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


class DemoLoginView(APIView):
    """One-click login to the shared, read-only demo account."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []  # ignore any old token the browser sends
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        user = None
        if settings.DEMO_USERNAME:
            user = User.objects.filter(username=settings.DEMO_USERNAME).first()
        if user is None:
            return Response(
                {"detail": "The demo account isn't available."},
                status=status.HTTP_404_NOT_FOUND,
            )
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": UserSerializer(user).data})


class LogoutView(APIView):
    def post(self, request):
        # Every demo visitor shares one token, so logging out mustn't delete it
        if request.auth and not is_demo_user(request.user):
            request.auth.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)
