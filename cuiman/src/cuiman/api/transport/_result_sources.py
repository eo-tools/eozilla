"""Volatile source URLs shared by transports for exact JobResults objects.

Deserialization retains the response body but loses its URL. Keep the effective
URL separately as a base for relative references, without modifying results or
keeping them alive. Associations last only while the exact objects remain alive
in this process; copies and manually constructed results have no association.
"""

import weakref
from threading import RLock
from typing import Any

from gavicore.models.core import JobResults

_sources: dict[int, tuple[weakref.ReferenceType[JobResults], str]] = {}
_lock = RLock()


def register_response_href(results: JobResults, href: str) -> None:
    """Retain an effective response URL without taking ownership of results."""
    identity = id(results)

    def discard(reference: weakref.ReferenceType[JobResults]) -> None:
        with _lock:
            source = _sources.get(identity)
            if source is not None and source[0] is reference:
                del _sources[identity]

    with _lock:
        _sources[identity] = (weakref.ref(results, discard), href)


def get_response_href(value: Any) -> str | None:
    """Look up an exact object's source URL across transports without I/O."""
    with _lock:
        source = _sources.get(id(value))
        return source[1] if source is not None and source[0]() is value else None
