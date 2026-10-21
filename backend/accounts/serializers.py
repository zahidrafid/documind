from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password as django_validate_password
from rest_framework import serializers

from .permissions import is_demo_user

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def validate_password(self, value):
        # Uses Django's built-in rules (not too common, not all numbers, etc.)
        django_validate_password(value)
        return value

    def create(self, validated_data):
        # create_user hashes the password; never store it as plain text
        return User.objects.create_user(**validated_data)


class UserSerializer(serializers.ModelSerializer):
    is_demo = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "is_demo"]

    def get_is_demo(self, user):
        return is_demo_user(user)
