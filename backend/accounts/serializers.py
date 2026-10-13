from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "full_name", "role"]


class LoginSerializer(TokenObtainPairSerializer):
    """Standard JWT login (email + password), but the response also carries
    the user's profile so the frontend doesn't need a second request."""

    def validate(self, attrs):
        # Emails are stored lower-case, so match them case-insensitively.
        attrs["email"] = attrs["email"].strip().lower()
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data
