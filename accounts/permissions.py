"""Access-control helpers.

The original site decided what a user could see from ``request.session['au']``,
a list of characters written at login.  Anything that could write to the session
could grant itself access, and a stale session kept access after a permission
was revoked.  Every check here goes to the database instead.
"""

from functools import wraps

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse

from .models import Profile, Section, SectionPermission


def granted_sections(user):
    """Return the set of :class:`Section` values ``user`` may access."""
    if not user.is_authenticated:
        return set()
    if user.is_superuser:
        return {value for value, _label in Section.choices}
    return set(
        SectionPermission.objects.filter(user=user).values_list('section', flat=True)
    )


def has_section(user, section):
    """Is ``user`` allowed into ``section``?"""
    return section in granted_sections(user)


def get_profile(user):
    """Return the user's profile, creating a default one if it is missing."""
    if not user.is_authenticated:
        return None
    profile, _created = Profile.objects.get_or_create(user=user)
    return profile


def should_mask_names(user):
    """Whether patient names must be masked for this user."""
    profile = get_profile(user)
    return True if profile is None else profile.de_identification


def section_required(section):
    """View decorator enforcing access to ``section``.

    Combine with :func:`django.contrib.auth.decorators.login_required`, which
    handles the redirect for anonymous users.
    """

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not has_section(request.user, section):
                raise PermissionDenied('沒有存取此功能區塊的權限')
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


def gated(section):
    """Standard protection: authenticated **and** granted ``section``.

    Used by every page that is not part of the public showcase surface, so
    those pages stay behind a login even while ``DEMO_MODE`` is on.
    """

    def decorator(view):
        return login_required(section_required(section)(view))

    return decorator


def demo_readable(section):
    """Read-only view that the public showcase exposes without an account.

    While ``DEMO_MODE`` is on this is open to anonymous visitors — every record
    is fictional, so there is nothing to gate.  With demo mode off it collapses
    to :func:`gated`, and the same view serves the real application.

    Only apply this to views that read; they must also work for
    ``AnonymousUser`` (patient names fall back to masked display).
    """

    def decorator(view):
        protected = gated(section)(view)

        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if settings.DEMO_MODE:
                return view(request, *args, **kwargs)
            return protected(request, *args, **kwargs)

        return wrapper

    return decorator


def blocked_in_demo(section):
    """Data-modifying view: refused outright while ``DEMO_MODE`` is on.

    The showcase is read-only so one visitor cannot leave the demo data in a
    confusing state for the next.
    """

    def decorator(view):
        protected = gated(section)(view)

        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if settings.DEMO_MODE:
                message = '示範站為唯讀模式，不開放修改資料'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'error': message}, status=403)
                raise PermissionDenied(message)
            return protected(request, *args, **kwargs)

        return wrapper

    return decorator
