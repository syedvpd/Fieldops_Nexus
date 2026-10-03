from django.urls import path

from . import views

app_name = "workspace"
urlpatterns = [
    path("workspace/", views.JobsView.as_view(), name="jobs"),
    path("workspace/<uuid:pk>/", views.JobView.as_view(), name="job"),
    path("workspace/<uuid:pk>/transition/<str:action>/", views.TransitionView.as_view(), name="transition"),
    path("workspace/<uuid:pk>/notes/", views.NoteView.as_view(), name="note"),
    path("workspace/<uuid:pk>/labor/", views.LaborView.as_view(), name="labor"),
    path("workspace/<uuid:pk>/materials/", views.MaterialView.as_view(), name="material"),
    path("workspace/<uuid:pk>/parts/request/", views.PartRequestView.as_view(), name="part_request"),
    path("workspace/<uuid:pk>/parts/<uuid:line>/consume/", views.PartConsumeView.as_view(), name="part_consume"),
    path("workspace/<uuid:pk>/evidence/", views.EvidenceView.as_view(), name="evidence"),
    path("workspace/<uuid:pk>/checklists/<uuid:template>/start/", views.StartInspectionView.as_view(),
         name="inspection_start"),
    path("workspace/inspections/<uuid:pk>/", views.InspectionView.as_view(), name="inspection"),
    path("workspace/inspections/<uuid:pk>/save/", views.InspectionSaveView.as_view(), name="inspection_save"),
    path("workspace/inspections/<uuid:pk>/findings/", views.FindingView.as_view(), name="finding"),
    path("workspace/inspections/<uuid:pk>/evidence/", views.InspectionEvidenceView.as_view(),
         name="inspection_evidence"),
]
