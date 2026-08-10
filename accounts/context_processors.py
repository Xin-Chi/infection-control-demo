"""Template context shared by every page.

Puts the navigation grants in the template context so ``navBar.html`` can show
only the menus a user actually has, without each view passing them in.
"""

from django.conf import settings

from .permissions import granted_sections


def navigation(request):
    return {
        # In demo mode the navigation is trimmed to the single showcase page,
        # so the menu matches what a visitor can actually open.
        'demo_mode': settings.DEMO_MODE,
        'nav_sections': granted_sections(request.user),
        'nav_can_administer': (
            request.user.is_authenticated and request.user.is_superuser
        ),
    }
