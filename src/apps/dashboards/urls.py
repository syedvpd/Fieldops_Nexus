from django.urls import path

from . import views

app_name = "dashboards"
urlpatterns = [
    path("dashboards/", views.IndexView.as_view(), name="index"),
    path("dashboards/my-work/", views.MineView.as_view(), name="mine"),
]
