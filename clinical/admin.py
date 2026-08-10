from django.contrib import admin

from .models import (
    Bacteria, ClinicalEvent, Division, ExamReport, MedType, Patient, Tube, VitalSign, Ward,
)


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('chart_no', 'name', 'gender', 'birth_date', 'ward')
    search_fields = ('chart_no', 'name')
    list_filter = ('gender', 'ward')


@admin.register(ClinicalEvent)
class ClinicalEventAdmin(admin.ModelAdmin):
    list_display = ('patient', 'exec_date', 'med_type', 'ward', 'bacteria')
    list_filter = ('med_type', 'ward')
    search_fields = ('patient__chart_no', 'patient__name')
    date_hierarchy = 'exec_date'


@admin.register(Tube)
class TubeAdmin(admin.ModelAdmin):
    list_display = ('tube_no', 'name', 'category', 'canonical', 'usage_count')
    list_filter = ('category',)
    search_fields = ('name',)


admin.site.register([Division, Ward, MedType, Bacteria, VitalSign, ExamReport])
