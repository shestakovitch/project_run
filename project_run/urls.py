"""
URL configuration for project_run project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from rest_framework.routers import DefaultRouter
from app_run.views import company_details, RunViewSet, UserViewSet, StartRunAPIView, StopRunAPIView, AthleteInfoAPIView, \
    ChallengeAPIView

router = DefaultRouter()
router.register('api/runs', RunViewSet)
router.register('api/users', UserViewSet, basename='user')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/company_details/', company_details),
    path('api/runs/<int:run_id>/start/', StartRunAPIView.as_view()),
    path('api/runs/<int:run_id>/stop/', StopRunAPIView.as_view()),
    path('api/athlete_info/<int:user_id>/', AthleteInfoAPIView.as_view()),
    path('api/challenges/', ChallengeAPIView.as_view()),
    path('', include(router.urls)),  # Всегда последний!
]
