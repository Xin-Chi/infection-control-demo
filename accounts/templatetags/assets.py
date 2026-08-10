"""Static assets tagged with a version, so browsers pick up edits.

Django's dev server serves CSS and JS with a plain ``Last-Modified`` header.
Browsers are free to reuse a cached copy without revalidating, so an edited
stylesheet can keep rendering from cache — the page then loads new markup
against old rules and the layout collapses.

``{% static_v 'css/app.css' %}`` appends the file's modification time to the
URL, which changes the URL whenever the file changes and leaves the cache
entry for the old URL harmlessly stranded.
"""

from pathlib import Path

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def static_v(path):
    """Return the static URL for ``path`` with a ``?v=<mtime>`` suffix."""
    url = static(path)

    absolute = finders.find(path)
    if not absolute:
        # Collected/remote storage: the storage backend handles versioning.
        return url

    try:
        stamp = int(Path(absolute).stat().st_mtime)
    except OSError:
        return url

    separator = '&' if '?' in url else '?'
    return f'{url}{separator}v={stamp}'
