from rest_framework import generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import User
from .permissions import IsEditor
from .serializers import LoginSerializer, UserSerializer


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer


@api_view(["GET"])
def me(request):
    """Who am I? Used by the frontend on page load to restore the session."""
    return Response(UserSerializer(request.user).data)


class WriterListView(generics.ListAPIView):
    """Editors need the list of writers to assign them to sections."""

    serializer_class = UserSerializer
    permission_classes = [IsEditor]

    def get_queryset(self):
        return User.objects.filter(role=User.Role.WRITER, is_active=True)


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """Cheap endpoint for uptime checks and for waking a sleeping free-tier host."""
    return Response({"status": "ok"})
