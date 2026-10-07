"""Per-process burst protection. The deployment proxy must also enforce limits."""

from collections import OrderedDict
from threading import Lock
from time import monotonic

from ..core.errors import AppError

_windows = OrderedDict()
_lock = Lock()


def submission_limit(principal):
    key = (principal.user_id, principal.organization_id)
    with _lock:
        now = monotonic()
        since, count = _windows.pop(key, (now, 0))
        if now - since >= 60:
            since, count = now, 0
        _windows[key] = (since, count + 1)
        if len(_windows) > 10000:
            _windows.popitem(last=False)
        if count >= 30:
            raise AppError("Too many submissions. Wait a minute and retry.", "rate_limited", 429)
