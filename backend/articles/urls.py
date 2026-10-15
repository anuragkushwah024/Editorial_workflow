from rest_framework.routers import DefaultRouter

from .views import ArticleViewSet, RevisionViewSet

router = DefaultRouter()
router.register("articles", ArticleViewSet, basename="article")
router.register("revisions", RevisionViewSet, basename="revision")

urlpatterns = router.urls
