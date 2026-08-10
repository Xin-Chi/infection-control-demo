"""Home page, authentication, and the administrator console."""

from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from research.models import ResearchTopic

from .forms import RegisterForm
from .models import Profile, Section, SectionPermission, TopicPermission

# ``user_passes_test`` keeps anonymous users going to the login page rather
# than seeing a 403.
superuser_required = user_passes_test(lambda u: u.is_superuser)


def index(request):
    return render(request, 'home.html')


def register(request):
    if request.user.is_authenticated:
        return redirect('accounts:index')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                # New accounts start inactive; an administrator enables them.
                user = form.save(commit=False)
                user.is_active = False
                user.save()
                Profile.objects.create(
                    user=user,
                    display_name=form.cleaned_data['display_name'],
                    organization=form.cleaned_data['organization'],
                )
            return render(request, 'accounts/register_done.html')
    else:
        form = RegisterForm()

    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:index')

    # AuthenticationForm rejects inactive accounts and applies Django's
    # throttling-friendly error messages, instead of the original
    # authenticate()-and-hope approach.
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        auth_login(request, form.get_user())
        return redirect('accounts:index')

    return render(request, 'accounts/login.html', {'form': form})


@require_POST
@login_required
def logout_view(request):
    # POST-only: a GET logout link can be triggered by any third-party page.
    auth_logout(request)
    return redirect('accounts:index')


# -- Administrator console --------------------------------------------------


@login_required
@superuser_required
def auth_control(request):
    return render(request, 'accounts/auth_control.html', {
        'sections': Section.choices,
    })


@require_GET
@login_required
@superuser_required
def user_list(request):
    users = (
        User.objects.filter(is_superuser=False)
        .select_related('profile')
        .order_by('username')
    )
    return JsonResponse({'users': [
        {
            'username': user.username,
            'display_name': getattr(user.profile, 'display_name', '') if hasattr(user, 'profile') else '',
            'is_active': user.is_active,
        }
        for user in users
    ]})


def _get_managed_user(username):
    """Fetch a non-superuser account by name, or ``None``.

    Superusers are excluded so the console cannot be used to strip another
    administrator's access.
    """
    return User.objects.filter(username=username, is_superuser=False).first()


@require_GET
@login_required
@superuser_required
def user_detail(request):
    user = _get_managed_user(request.GET.get('username', ''))
    if user is None:
        return JsonResponse({'error': '查無此使用者'}, status=404)

    profile, _ = Profile.objects.get_or_create(user=user)
    return JsonResponse({
        'username': user.username,
        'is_active': user.is_active,
        'de_identification': profile.de_identification,
        'can_see_all_reviews': profile.can_see_all_reviews,
        'can_edit_stage_definition': profile.can_edit_stage_definition,
        'sections': list(
            user.section_permissions.values_list('section', flat=True)
        ),
        'topics': list(user.topic_permissions.values_list('topic_id', flat=True)),
    })


@require_GET
@login_required
@superuser_required
def topic_list(request):
    topics = ResearchTopic.objects.order_by('id')
    return JsonResponse({'topics': [
        {'id': topic.id, 'name': topic.name} for topic in topics
    ]})


@require_POST
@login_required
@superuser_required
def toggle_section(request):
    user = _get_managed_user(request.POST.get('username', ''))
    if user is None:
        return JsonResponse({'error': '查無此使用者'}, status=404)

    section = request.POST.get('section', '')
    if section not in {value for value, _label in Section.choices}:
        return JsonResponse({'error': '不支援的功能區塊'}, status=400)

    existing = SectionPermission.objects.filter(user=user, section=section)
    if existing.exists():
        existing.delete()
        granted = False
    else:
        SectionPermission.objects.create(user=user, section=section)
        granted = True

    return JsonResponse({'granted': granted})


@require_POST
@login_required
@superuser_required
def toggle_topic(request):
    user = _get_managed_user(request.POST.get('username', ''))
    if user is None:
        return JsonResponse({'error': '查無此使用者'}, status=404)

    topic = ResearchTopic.objects.filter(pk=request.POST.get('topic_id')).first()
    if topic is None:
        return JsonResponse({'error': '查無此研究主題'}, status=404)

    existing = TopicPermission.objects.filter(user=user, topic=topic)
    if existing.exists():
        existing.delete()
        granted = False
    else:
        TopicPermission.objects.create(user=user, topic=topic)
        granted = True

    return JsonResponse({'granted': granted})


# Only these profile flags may be toggled from the console; anything else in
# the POST body is ignored rather than written through to the model.
TOGGLEABLE_FLAGS = {
    'is_active',
    'de_identification',
    'can_see_all_reviews',
    'can_edit_stage_definition',
}


@require_POST
@login_required
@superuser_required
def toggle_flag(request):
    user = _get_managed_user(request.POST.get('username', ''))
    if user is None:
        return JsonResponse({'error': '查無此使用者'}, status=404)

    flag = request.POST.get('flag', '')
    if flag not in TOGGLEABLE_FLAGS:
        return JsonResponse({'error': '不支援的設定項目'}, status=400)

    if flag == 'is_active':
        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])
        value = user.is_active
    else:
        profile, _ = Profile.objects.get_or_create(user=user)
        value = not getattr(profile, flag)
        setattr(profile, flag, value)
        profile.save(update_fields=[flag])

    return JsonResponse({'value': value})
