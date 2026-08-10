"""感染管控 — patient timeline search, term curation, and tube mapping.

Every query here goes through the ORM.  The original module built SQL by
interpolating request parameters into f-strings, so a value like
``1' OR '1'='1`` changed the meaning of the statement; the ORM parameterises
each value instead.  All JSON endpoints are POST + CSRF-protected and return
lists of objects rather than the original parallel arrays.
"""

from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from accounts.models import Section
from accounts.permissions import (
    blocked_in_demo,
    demo_readable,
    gated,
    should_mask_names,
)
from clinical.models import (
    Bacteria,
    ClinicalEvent,
    Division,
    ExamReport,
    MedType,
    Patient,
    Tube,
    VitalMeasurement,
    Ward,
)
from clinical.vitals import FEVER_THRESHOLD, classify

from .models import (
    CategoryPoolEntry,
    ConversionCategory,
    ConversionEntry,
    InfectionCategory,
    Token,
)

# The 查詢 page is the public showcase surface; everything else stays behind
# a login even in demo mode, and writes are refused outright.
search_public = demo_readable(Section.INFECTION)
infection_gated = gated(Section.INFECTION)
infection_write = blocked_in_demo(Section.INFECTION)


def _parse_date(value):
    """Return a ``YYYY-MM-DD`` string or ``None`` if it is blank/invalid."""
    from datetime import datetime

    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), '%Y-%m-%d').date()
    except (ValueError, AttributeError):
        return None


def _patient_label(patient, mask):
    return patient.masked_name if mask else patient.name


# -- 查詢 (Search) -----------------------------------------------------------


@ensure_csrf_cookie
@search_public
def search(request):
    """The 查詢 page.

    ``ensure_csrf_cookie`` is needed because this page is reachable without
    logging in: nothing else would hand out a CSRF cookie, and the page's own
    POST requests would then be rejected.
    """
    return render(request, 'infection/search.html')


@require_GET
@search_public
def search_filters(request):
    """Dropdown options for the filter panel."""
    return JsonResponse({
        'wards': [
            {'code': ward.code, 'name': ward.name}
            for ward in Ward.objects.order_by('code')
        ],
        'divisions': [
            {'code': division.code, 'name': division.name}
            for division in Division.objects.order_by('code')
        ],
        'bacteria': [
            {'id': item.id, 'name': item.name, 'is_commensal': item.is_commensal}
            for item in Bacteria.objects.order_by('name')
        ],
    })


@require_POST
@search_public
def patient_list(request):
    """Chart numbers matching the filter panel.

    The original built five nested ``INNER JOIN`` sub-selects from interpolated
    strings; the same intersection is expressed here as chained filters.
    """
    events = ClinicalEvent.objects.all()

    start = _parse_date(request.POST.get('start_date'))
    end = _parse_date(request.POST.get('end_date'))
    if start:
        events = events.filter(exec_date__date__gte=start)
    if end:
        events = events.filter(exec_date__date__lte=end)

    ward = request.POST.get('ward', '').strip()
    if ward:
        events = events.filter(ward__code=ward)

    division = request.POST.get('division', '').strip()
    if division:
        events = events.filter(division__code=division)

    bacteria_id = request.POST.get('bacteria', '').strip()
    if bacteria_id.isdigit():
        events = events.filter(bacteria_id=int(bacteria_id))

    if request.POST.get('inpatient_only') == 'true':
        events = events.filter(med_type__event_category=MedType.Category.ADMISSION)

    mask = should_mask_names(request.user)
    patients = (
        Patient.objects.filter(id__in=events.values('patient_id'))
        .order_by('chart_no')
        .distinct()
    )
    return JsonResponse({'patients': [
        {
            'chart_no': patient.chart_no,
            'name': _patient_label(patient, mask),
            'ward': patient.ward.name if patient.ward else '',
        }
        for patient in patients
    ]})


@require_POST
@search_public
def patient_timeline(request):
    """Timeline rows for one patient, filtered by the tab checkboxes."""
    chart_no = request.POST.get('chart_no', '').strip()
    patient = get_object_or_404(Patient, chart_no=chart_no)

    categories = []
    if request.POST.get('admission') == 'true':
        categories.append(MedType.Category.ADMISSION)
    if request.POST.get('nursing') == 'true':
        categories.append(MedType.Category.NURSING)
    if request.POST.get('tube') == 'true':
        categories.append(MedType.Category.TUBE)
    if request.POST.get('vital') == 'true':
        categories.append(MedType.Category.VITAL)
    if not categories:
        categories = [MedType.Category.ADMISSION]

    events = (
        ClinicalEvent.objects
        .filter(patient=patient, med_type__event_category__in=categories)
        .select_related('med_type', 'ward', 'division', 'bacteria', 'vital_sign')
        .order_by('exec_date')
    )

    start = _parse_date(request.POST.get('start_date'))
    end = _parse_date(request.POST.get('end_date'))
    if start:
        events = events.filter(exec_date__date__gte=start)
    if end:
        events = events.filter(exec_date__date__lte=end)

    # Reports are counted per row so the timeline can show which entries have
    # something to open, without a query per row.
    report_counts = dict(
        ExamReport.objects
        .filter(event__in=events)
        .values_list('event_id')
        .annotate(total=Count('id'))
    )

    rows = []
    for event in events:
        vital = getattr(event, 'vital_sign', None)
        temperature = vital.temperature if vital else None
        rows.append({
            'id': event.id,
            'exec_date': event.exec_date.strftime('%Y-%m-%d %H:%M'),
            'type_name': event.med_type.type_name,
            'category': event.med_type.event_category,
            'ward': event.ward.name if event.ward else '',
            'division': event.division.name if event.division else '',
            'bacteria': event.bacteria.name if event.bacteria else '',
            'is_commensal': bool(event.bacteria and event.bacteria.is_commensal),
            'order_no': event.order_no,
            'temperature': str(temperature) if temperature else '',
            # 38.0°C is the usual clinical threshold for fever.
            'has_fever': bool(temperature and temperature >= FEVER_THRESHOLD),
            'blood_pressure': vital.blood_pressure if vital else '',
            'pulse': vital.pulse if vital else '',
            'spo2': vital.spo2 if vital else '',
            'report_count': report_counts.get(event.id, 0),
        })

    mask = should_mask_names(request.user)
    return JsonResponse({
        'patient': {
            'chart_no': patient.chart_no,
            'name': _patient_label(patient, mask),
            'gender': patient.get_gender_display(),
            'ward': patient.ward.name if patient.ward else '',
        },
        'events': rows,
    })


@require_POST
@search_public
def vital_chart(request):
    """The patient's consolidated vital-sign chart.

    Every reading for the patient in time order, gathered from all their
    records — this is the view a reviewer reads, not the readings of any one
    note.  Each cell carries a ``high``/``low``/``''`` status so the table can
    mark abnormal values without the template re-deriving the thresholds.
    """
    patient = get_object_or_404(Patient, chart_no=request.POST.get('chart_no', ''))

    rows = VitalMeasurement.objects.filter(patient=patient)

    start = _parse_date(request.POST.get('start_date'))
    end = _parse_date(request.POST.get('end_date'))
    if start:
        rows = rows.filter(measured_at__date__gte=start)
    if end:
        rows = rows.filter(measured_at__date__lte=end)

    fields = ('pulse', 'respiration', 'spo2', 'temperature', 'systolic', 'diastolic')

    payload = []
    for row in rows.order_by('measured_at'):
        cells = {}
        for field in fields:
            value = getattr(row, field)
            cells[field] = {
                'value': '' if value is None else str(value),
                'status': classify(field, value),
            }
        payload.append({
            'measured_at': row.measured_at.strftime('%Y-%m-%d %H:%M:%S'),
            **cells,
        })

    return JsonResponse({
        'chart_no': patient.chart_no,
        'measurements': payload,
        'abnormal_count': sum(
            1 for r in payload for f in fields if r[f]['status']
        ),
    })


@require_POST
@search_public
def event_report(request):
    """Reports for one timeline row (原「原始報告」側欄).

    Culture reports carry the specimen header and sensitivity panel; nursing
    and vital notes carry narrative text only.  The front-end renders each
    shape differently based on ``kind``.
    """
    event_id = request.POST.get('event_id', '')
    if not str(event_id).isdigit():
        return JsonResponse({'reports': []})

    reports = (
        ExamReport.objects
        .filter(event_id=event_id)
        .prefetch_related('isolates__organism', 'isolates__susceptibilities')
        .order_by('-exec_time')
    )

    payload = []
    for report in reports:
        item = {
            'kind': report.kind,
            'kind_label': report.get_kind_display(),
            'report_no': report.report_no,
            'exec_time': report.exec_time.strftime('%Y-%m-%d %H:%M'),
            'report_date': report.exec_time.strftime('%Y-%m-%d'),
            'content': report.content,
            'raw_text': report.raw_text,
        }
        if report.kind == ExamReport.Kind.CULTURE:
            item.update({
                'test_name': report.test_name,
                'specimen': report.specimen,
                'collected_at': (
                    report.collected_at.strftime('%Y-%m-%d %H:%M')
                    if report.collected_at else ''
                ),
                'received_at': (
                    report.received_at.strftime('%Y-%m-%d %H:%M')
                    if report.received_at else ''
                ),
                'isolates': [
                    {
                        'organism': isolate.organism.name,
                        'growth': isolate.growth,
                        'is_commensal': isolate.organism.is_commensal,
                        'colony_count': isolate.colony_count,
                        'susceptibilities': [
                            {
                                'antibiotic': row.antibiotic,
                                'mic': row.mic,
                                'interpretation': row.interpretation,
                                'label': row.get_interpretation_display(),
                            }
                            for row in isolate.susceptibilities.all()
                        ],
                    }
                    for isolate in report.isolates.all()
                ],
            })
        payload.append(item)

    return JsonResponse({'reports': payload})


# -- 歸類 (Categorize) -------------------------------------------------------


@infection_gated
def categorize(request):
    return render(request, 'infection/categorize.html')


def _category_counts(status):
    """Categories annotated with how many pooled terms sit at ``status``."""
    return (
        InfectionCategory.objects
        .annotate(total=Count('pool_entries', filter=Q(pool_entries__status=status)))
        .filter(total__gt=0)
        .order_by('id')
    )


@require_GET
@infection_gated
def category_list(request):
    """Confirmed and pending category counts, for the two side lists."""
    return JsonResponse({
        'confirmed': [
            {'id': c.id, 'name': c.name, 'total': c.total}
            for c in _category_counts(CategoryPoolEntry.Status.CONFIRMED)
        ],
        'pending': [
            {'id': c.id, 'name': c.name, 'total': c.total}
            for c in _category_counts(CategoryPoolEntry.Status.PENDING)
        ],
    })


@require_POST
@infection_gated
def token_pool(request):
    """Terms in one category, optionally filtered by keyword."""
    category_id = request.POST.get('category_id', '')
    status = request.POST.get('status', 'confirmed')
    keyword = request.POST.get('keyword', '').strip()

    status_value = (
        CategoryPoolEntry.Status.CONFIRMED
        if status == 'confirmed'
        else CategoryPoolEntry.Status.PENDING
    )

    entries = (
        CategoryPoolEntry.objects
        .filter(category_id=category_id, status=status_value)
        .select_related('token')
        .order_by('token__text')
    )
    if keyword:
        # ``icontains`` parameterises the pattern; the original concatenated
        # '%' + keyword + '%' straight into the statement.
        entries = entries.filter(token__text__icontains=keyword)

    return JsonResponse({'tokens': [
        {
            'id': entry.token_id,
            'text': entry.token.text,
            'categorized_count': entry.categorized_count,
        }
        for entry in entries
    ]})


@require_POST
@infection_write
def review_tokens(request):
    """Confirm or abandon pooled terms in bulk."""
    category_id = request.POST.get('category_id', '')
    confirm_ids = [i for i in request.POST.getlist('confirm_ids[]') if i.isdigit()]
    abandon_ids = [i for i in request.POST.getlist('abandon_ids[]') if i.isdigit()]

    base = CategoryPoolEntry.objects.filter(category_id=category_id)
    confirmed = abandoned = 0
    if confirm_ids:
        confirmed = base.filter(token_id__in=confirm_ids).update(
            status=CategoryPoolEntry.Status.CONFIRMED
        )
    if abandon_ids:
        abandoned = base.filter(token_id__in=abandon_ids).update(
            status=CategoryPoolEntry.Status.ABANDONED
        )

    return JsonResponse({'confirmed': confirmed, 'abandoned': abandoned})


@require_GET
@infection_gated
def conversion_categories(request):
    """Curated categories within one pool, with their term counts."""
    pool = request.GET.get('pool', '').strip()
    categories = ConversionCategory.objects.annotate(total=Count('entries'))
    if pool:
        categories = categories.filter(pool=pool)
    return JsonResponse({'categories': [
        {'id': c.id, 'name': c.name, 'pool': c.pool, 'total': c.total}
        for c in categories.order_by('id')
    ]})


@require_POST
@infection_gated
def conversion_tokens(request):
    """Terms already mapped into one curated category."""
    entries = (
        ConversionEntry.objects
        .filter(category_id=request.POST.get('category_id', ''))
        .select_related('token')
        .order_by('token__text')
    )
    return JsonResponse({'tokens': [
        {'id': entry.token_id, 'text': entry.token.text} for entry in entries
    ]})


@require_POST
@infection_write
def add_to_conversion(request):
    """Map selected terms into a curated category, creating it if needed."""
    name = request.POST.get('name', '').strip()
    pool = request.POST.get('pool', '').strip()
    token_ids = [i for i in request.POST.getlist('token_ids[]') if i.isdigit()]

    if not name or not pool:
        return JsonResponse({'error': '請提供分類名稱與詞庫'}, status=400)

    category, _created = ConversionCategory.objects.get_or_create(name=name, pool=pool)

    added = 0
    for token in Token.objects.filter(id__in=token_ids):
        _entry, created = ConversionEntry.objects.get_or_create(
            category=category, token=token
        )
        if created:
            added += 1
            # Incremented in the database.  The original read the value, added
            # one in Python and wrote it back, losing updates when two
            # reviewers acted at the same time.
            CategoryPoolEntry.objects.filter(token=token).update(
                categorized_count=F('categorized_count') + 1
            )

    return JsonResponse({'category_id': category.id, 'added': added})


@require_POST
@infection_write
def remove_from_conversion(request):
    """Unmap terms, deleting the category once it is empty."""
    category_id = request.POST.get('category_id', '')
    token_ids = [i for i in request.POST.getlist('token_ids[]') if i.isdigit()]

    category = ConversionCategory.objects.filter(pk=category_id).first()
    if category is None:
        return JsonResponse({'error': '查無此分類'}, status=404)

    removed, _ = ConversionEntry.objects.filter(
        category=category, token_id__in=token_ids
    ).delete()
    CategoryPoolEntry.objects.filter(
        token_id__in=token_ids, categorized_count__gt=0
    ).update(categorized_count=F('categorized_count') - 1)

    category_deleted = False
    if not category.entries.exists():
        category.delete()
        category_deleted = True

    return JsonResponse({'removed': removed, 'category_deleted': category_deleted})


# -- 管路確認 / 管路歸類 (Tube mapping) --------------------------------------


@infection_gated
def tube_mapping(request, variant):
    """Shared page for both tube-mapping screens.

    ``variant`` picks which raw-name source is being mapped; the original
    shipped two near-identical apps (``tube`` and ``tube2``) that differed only
    in the hard-coded ``Category=2`` / ``Category=3``.
    """
    category = (
        Tube.Category.VARIANT_A if variant == 'a' else Tube.Category.VARIANT_B
    )
    return render(request, 'infection/tube.html', {
        'variant': variant,
        'variant_label': Tube.Category(category).label,
        'title': '管路確認' if variant == 'a' else '管路歸類',
    })


def _variant_category(variant):
    return Tube.Category.VARIANT_A if variant == 'a' else Tube.Category.VARIANT_B


@require_GET
@infection_gated
def tube_data(request, variant):
    """Raw tube names for this variant plus the canonical list to map onto."""
    category = _variant_category(variant)
    variants = (
        Tube.objects.filter(category=category)
        .select_related('canonical')
        .order_by('tube_no')
    )
    canonical = Tube.objects.filter(category=Tube.Category.CANONICAL).order_by('tube_no')

    return JsonResponse({
        'variants': [
            {
                'tube_no': tube.tube_no,
                'name': tube.name,
                'usage_count': tube.usage_count,
                'canonical_no': tube.canonical.tube_no if tube.canonical else None,
                'canonical_name': tube.canonical.name if tube.canonical else '',
            }
            for tube in variants
        ],
        'canonical': [
            {'tube_no': tube.tube_no, 'name': tube.name} for tube in canonical
        ],
    })


@require_POST
@infection_write
def tube_map(request, variant):
    """Point one raw tube name at a canonical one (or clear the mapping)."""
    category = _variant_category(variant)
    tube = get_object_or_404(
        Tube, tube_no=request.POST.get('tube_no', ''), category=category
    )

    canonical_no = request.POST.get('canonical_no', '').strip()
    if canonical_no:
        tube.canonical = get_object_or_404(
            Tube, tube_no=canonical_no, category=Tube.Category.CANONICAL
        )
    else:
        tube.canonical = None
    tube.save(update_fields=['canonical'])

    return JsonResponse({
        'tube_no': tube.tube_no,
        'canonical_no': tube.canonical.tube_no if tube.canonical else None,
        'canonical_name': tube.canonical.name if tube.canonical else '',
    })
