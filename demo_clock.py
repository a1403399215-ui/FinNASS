"""Explicit demo snapshot clock; does not modify measurement timestamps."""
import os
from datetime import datetime, timezone


def demo_mode_enabled():
    value = os.environ.get('DEMO_MODE', 'true').strip().lower()
    if value not in {'true', 'false', '1', '0'}:
        raise ValueError('DEMO_MODE must be true, false, 1 or 0')
    return value in {'true', '1'}


def as_utc(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Dataset timestamps must contain a UTC offset')
    return result.astimezone(timezone.utc).replace(microsecond=0)


def resolve_clock(latest_observed_at, demo_mode, server_time=None):
    server_time = server_time or datetime.now(timezone.utc)
    if server_time.tzinfo is None:
        raise ValueError('server_time must contain a timezone')
    server_time = server_time.astimezone(timezone.utc).replace(microsecond=0)
    latest = as_utc(latest_observed_at) if latest_observed_at else None
    window_end = latest if demo_mode and latest is not None else server_time
    return {
        'clock_mode': 'demo' if demo_mode else 'live',
        'window_end': window_end.isoformat(timespec='seconds'),
        'data_as_of': latest.isoformat(timespec='seconds') if latest else None,
        'server_time': server_time.isoformat(timespec='seconds'),
    }
