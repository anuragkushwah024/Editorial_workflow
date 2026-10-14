from rest_framework.routers import DefaultRouter

from .views import SectionViewSet

router = DefaultRouter()
router.register("sections", SectionViewSet, basename="section")

urlpatterns = router.urls
