from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("me/", views.me, name="me"),
    path("writers/", views.WriterListView.as_view(), name="writer-list"),
    path("editors/", views.EditorListView.as_view(), name="editor-list"),
]
