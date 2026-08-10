"""Reference ranges for vital signs.

Kept in one module so the chart, the timeline marker and anything added later
all flag the same readings.  The bounds are the common adult ward-observation
ranges; a real deployment would make them configurable per unit.

``classify`` returns ``'high'``, ``'low'`` or ``''`` so the template can show
*why* a cell is marked, rather than just that it is unusual.
"""

from decimal import Decimal

# field -> (low bound, high bound); a reading outside the bounds is flagged.
RANGES = {
    'temperature': (Decimal('36.0'), Decimal('38.0')),
    'pulse': (50, 120),
    'respiration': (10, 24),
    'spo2': (90, None),
    'systolic': (90, 180),
    # Diastolic is charted but not flagged on its own: it is read together
    # with the systolic value, which is what the ward acts on.
    'diastolic': (None, None),
}

FEVER_THRESHOLD = RANGES['temperature'][1]


def classify(field, value):
    """Return 'high', 'low' or '' for one reading."""
    if value is None or value == '':
        return ''

    bounds = RANGES.get(field)
    if not bounds:
        return ''

    low, high = bounds
    if high is not None and value >= high:
        return 'high'
    if low is not None and value < low:
        return 'low'
    return ''
