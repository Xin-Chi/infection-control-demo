from django.contrib import admin

from .models import (
    DiseaseGroup, ExamStudy, PatientDisease, ResearchTopic, StageConfirmation, StageDefinition,
)


@admin.register(StageConfirmation)
class StageConfirmationAdmin(admin.ModelAdmin):
    list_display = ('patient', 'stage', 'reviewer', 'confirmed_at')
    list_filter = ('stage__topic', 'reviewer')


admin.site.register([ResearchTopic, DiseaseGroup, PatientDisease, ExamStudy, StageDefinition])
