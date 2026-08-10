from django.urls import path

from . import views

app_name = 'research'

urlpatterns = [
    path('warehousing/', views.warehousing, name='warehousing'),
    path('warehousing/diseases/', views.disease_list, name='disease_list'),
    path('warehousing/patients/', views.warehousing_patients, name='warehousing_patients'),
    path('warehousing/studies/', views.patient_studies, name='patient_studies'),
    path('warehousing/export/', views.export_csv, name='export_csv'),

    path('topics/', views.topics, name='topics'),
    path('topics/list/', views.topic_list, name='topic_list'),
    path('topics/patients/', views.topic_patients, name='topic_patients'),

    path('stage/', views.stage_confirm, name='stage_confirm'),
    path('stage/definitions/', views.stage_definitions, name='stage_definitions'),
    path('stage/patient/', views.patient_stage, name='patient_stage'),
    path('stage/save/', views.save_stage, name='save_stage'),
]
