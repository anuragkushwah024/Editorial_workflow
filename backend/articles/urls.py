from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ArticleViewSet, RevisionViewSet, alerts, dashboard, dismiss_alert

router = DefaultRouter()
router.register("articles", ArticleViewSet, basename="article")
router.register("revisions", RevisionViewSet, basename="revision")

urlpatterns = router.urls + [
    path("dashboard/", dashboard, name="dashboard"),
    path("alerts/", alerts, name="alerts"),
    path("alerts/dismiss/", dismiss_alert, name="alerts-dismiss"),
]
