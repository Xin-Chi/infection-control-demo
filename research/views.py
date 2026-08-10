"""癌症研究 — cohort lists, exam records, and stage confirmation.

The original ``warehousing`` and ``pool`` apps were near-duplicates that also
walked the filesystem looking for ``.h5`` image files on every row.  The demo
carries no pixel data, so the shared list logic lives in one place here.
"""

import csv

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Exists, OuterRef, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from accounts.models import Section
from accounts.permissions import (
    blocked_in_demo,
    gated,
    get_profile,
    should_mask_names,
)
from clinical.models import Patient

from .models import (
    DiseaseGroup,
    ExamStudy,
    PatientDisease,
    ResearchTopic,
    StageConfirmation,
    StageDefinition,
)

# Not part of the public showcase surface: these pages need a signed-in
# reviewer (their own annotations drive what they see).
research_gated = gated(Section.RESEARCH)
research_write = blocked_in_demo(Section.RESEARCH)


def _visible_topics(user):
    """Topics this user may work on.

    Superusers see everything; everyone else sees only granted topics.  The
    original ran ``username like '<name>%'`` against the permission table, so
    a user called ``bob`` also matched ``bobby``'s grants.
    """
    if user.is_superuser:
        return ResearchTopic.objects.order_by('id')
    return ResearchTopic.objects.filter(permissions__user=user).order_by('id').distinct()


def _patient_payload(patient, mask):
    return {
        'chart_no': patient.chart_no,
        'name': patient.masked_name if mask else patient.name,
        'gender': patient.get_gender_display(),
        'ward': patient.ward.name if patient.ward else '',
    }


# -- 入庫清單 (Warehousing) --------------------------------------------------


@research_gated
def warehousing(request):
    return render(request, 'research/warehousing.html')


@require_GET
@research_gated
def disease_list(request):
    diseases = DiseaseGroup.objects.annotate(total=Count('patients')).order_by('id')
    return JsonResponse({'diseases': [
        {'id': d.id, 'name': d.name, 'total': d.total} for d in diseases
    ]})


@require_POST
@research_gated
def warehousing_patients(request):
    """Patients in a disease group, with their exam-record counts."""
    disease_id = request.POST.get('disease_id', '')
    patients = (
        Patient.objects
        .filter(diseases__disease_id=disease_id)
        .annotate(study_count=Count('events__studies', distinct=True))
        .select_related('ward')
        .order_by('chart_no')
        .distinct()
    )

    mask = should_mask_names(request.user)
    rows = []
    for patient in patients:
        payload = _patient_payload(patient, mask)
        payload['study_count'] = patient.study_count
        rows.append(payload)

    return JsonResponse({'patients': rows, 'total': len(rows)})


@require_POST
@research_gated
def patient_studies(request):
    """Exam records for one patient (metadata only — no image data)."""
    patient = get_object_or_404(Patient, chart_no=request.POST.get('chart_no', ''))
    studies = (
        ExamStudy.objects
        .filter(event__patient=patient)
        .select_related('event', 'event__med_type')
        .order_by('event__exec_date')
    )
    return JsonResponse({'studies': [
        {
            'exec_date': study.event.exec_date.strftime('%Y-%m-%d'),
            'type_name': study.event.med_type.type_name,
            'study_id': study.study_id,
            'series_id': study.series_id,
            'description': study.description,
            'series_description': study.series_description,
            'slice_count': study.slice_count,
            'hospital': study.hospital,
        }
        for study in studies
    ]})


@require_GET
@research_gated
def export_csv(request):
    """Download the current disease group's exam records as CSV."""
    disease = get_object_or_404(DiseaseGroup, pk=request.GET.get('disease_id', ''))
    studies = (
        ExamStudy.objects
        .filter(event__patient__diseases__disease=disease)
        .select_related('event', 'event__patient', 'event__med_type')
        .order_by('event__patient__chart_no', 'event__exec_date')
    )

    response = HttpResponse(content_type='text/csv')
    response.charset = 'utf-8-sig'
    # Derived from the group's primary key, so a crafted name cannot inject
    # header fields into the response.
    response['Content-Disposition'] = (
        f'attachment; filename="warehousing_{disease.pk}.csv"'
    )

    mask = should_mask_names(request.user)
    writer = csv.writer(response)
    writer.writerow(['病歷號', '姓名', '檢查日期', '項目', '檢查編號', '序列編號', '影像張數'])
    for study in studies:
        patient = study.event.patient
        writer.writerow([
            patient.chart_no,
            patient.masked_name if mask else patient.name,
            study.event.exec_date.strftime('%Y-%m-%d'),
            study.event.med_type.type_name,
            study.study_id,
            study.series_id,
            study.slice_count,
        ])
    return response


# -- 研究主題 (Topic cohort) -------------------------------------------------


@research_gated
def topics(request):
    return render(request, 'research/topics.html')


@require_GET
@research_gated
def topic_list(request):
    topics_qs = _visible_topics(request.user).annotate(
        patient_count=Count('stage_definitions__confirmations__patient', distinct=True)
    )
    return JsonResponse({'topics': [
        {
            'id': topic.id,
            'name': topic.name,
            'description': topic.description,
            'patient_count': topic.patient_count,
        }
        for topic in topics_qs
    ]})


@require_POST
@research_gated
def topic_patients(request):
    """Patients under a topic, split by whether this user has reviewed them.

    ``filter`` accepts ``all`` / ``pending`` / ``reviewed``.
    """
    topic = get_object_or_404(_visible_topics(request.user), pk=request.POST.get('topic_id', ''))
    stage_filter = request.POST.get('filter', 'all')

    reviewed_by_me = StageConfirmation.objects.filter(
        patient=OuterRef('pk'), stage__topic=topic, reviewer=request.user
    )
    patients = (
        Patient.objects
        .filter(diseases__isnull=False)
        .annotate(reviewed=Exists(reviewed_by_me))
        .select_related('ward')
        .order_by('chart_no')
        .distinct()
    )

    if stage_filter == 'pending':
        patients = patients.filter(reviewed=False)
    elif stage_filter == 'reviewed':
        patients = patients.filter(reviewed=True)

    mask = should_mask_names(request.user)
    rows = []
    for patient in patients:
        payload = _patient_payload(patient, mask)
        payload['reviewed'] = patient.reviewed
        rows.append(payload)

    counts = Patient.objects.filter(diseases__isnull=False).distinct().aggregate(
        total=Count('id', distinct=True),
    )
    reviewed_total = (
        StageConfirmation.objects
        .filter(stage__topic=topic, reviewer=request.user)
        .values('patient_id')
        .distinct()
        .count()
    )

    return JsonResponse({
        'patients': rows,
        'total': counts['total'] or 0,
        'reviewed': reviewed_total,
        'pending': (counts['total'] or 0) - reviewed_total,
    })


# -- 確認病患階段 (Stage confirmation) ---------------------------------------


@research_gated
def stage_confirm(request):
    profile = get_profile(request.user)
    return render(request, 'research/stage_confirm.html', {
        'can_edit_stage_definition': bool(profile and profile.can_edit_stage_definition),
    })


@require_POST
@research_gated
def stage_definitions(request):
    topic = get_object_or_404(_visible_topics(request.user), pk=request.POST.get('topic_id', ''))
    stages = topic.stage_definitions.order_by('order', 'id')
    return JsonResponse({'stages': [
        {'id': stage.id, 'name': stage.name, 'order': stage.order} for stage in stages
    ]})


@require_POST
@research_gated
def patient_stage(request):
    """Which stage this user has recorded for a patient under a topic."""
    topic = get_object_or_404(_visible_topics(request.user), pk=request.POST.get('topic_id', ''))
    patient = get_object_or_404(Patient, chart_no=request.POST.get('chart_no', ''))

    profile = get_profile(request.user)
    confirmations = StageConfirmation.objects.filter(
        patient=patient, stage__topic=topic
    ).select_related('stage', 'reviewer')

    # Reviewers only see their own labels unless explicitly granted otherwise,
    # so one reviewer's judgement cannot bias another's.
    if not (profile and profile.can_see_all_reviews) and not request.user.is_superuser:
        confirmations = confirmations.filter(reviewer=request.user)

    return JsonResponse({'confirmations': [
        {
            'stage_id': c.stage_id,
            'stage_name': c.stage.name,
            'reviewer': c.reviewer.username,
            'note': c.note,
            'confirmed_at': c.confirmed_at.strftime('%Y-%m-%d %H:%M'),
            'is_mine': c.reviewer_id == request.user.id,
        }
        for c in confirmations.order_by('-confirmed_at')
    ]})


@require_POST
@research_write
def save_stage(request):
    """Record (or clear) this user's stage judgement for a patient."""
    topic = get_object_or_404(_visible_topics(request.user), pk=request.POST.get('topic_id', ''))
    patient = get_object_or_404(Patient, chart_no=request.POST.get('chart_no', ''))
    stage_id = request.POST.get('stage_id', '')

    # A reviewer may only write their own row — reviewer is taken from the
    # session, never from the request body.
    StageConfirmation.objects.filter(
        patient=patient, stage__topic=topic, reviewer=request.user
    ).delete()

    if not stage_id:
        return JsonResponse({'stage_id': None})

    stage = get_object_or_404(StageDefinition, pk=stage_id, topic=topic)
    StageConfirmation.objects.create(
        patient=patient,
        stage=stage,
        reviewer=request.user,
        note=request.POST.get('note', '')[:500],
    )
    return JsonResponse({'stage_id': stage.id, 'stage_name': stage.name})
