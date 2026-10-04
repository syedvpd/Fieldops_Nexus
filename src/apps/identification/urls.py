from django.urls import path

from . import views

app_name = "identification"
urlpatterns = [
    path("identification/scan/", views.ScanPageView.as_view(), name="scan"),
    path("s/<str:token>/", views.ResolveView.as_view(), name="resolve"),
    path("identification/assets/<uuid:asset_id>/panel/", views.AssetPanelView.as_view(), name="panel"),
    path("identification/assets/<uuid:asset_id>/panel/<str:action>/", views.AssetPanelActionView.as_view(),
         name="panel_action"),
    path("identification/assets/<uuid:asset_id>/label/", views.LabelPageView.as_view(), name="label"),
    path("identification/assets/<uuid:asset_id>/<str:kind>.<str:fmt>", views.LabelImageView.as_view(),
         name="image"),
]
