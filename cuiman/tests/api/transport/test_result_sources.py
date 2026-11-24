"""Source provenance survives transport changes without retaining results."""

import gc
import weakref
from concurrent.futures import ThreadPoolExecutor

from cuiman.api.transport import _result_sources as sources
from gavicore.models.core import JobResults


def test_source_lifetime_and_replacement():
    results = JobResults(root={"item": 1})
    identity = id(results)
    reference = weakref.ref(results)
    sources.register_response_href(results, "https://api.test/first")
    previous = sources._sources[identity][0]
    discard = previous.__callback__
    sources.register_response_href(results, "https://api.test/second")
    # A delayed callback must not remove a replacement association.
    discard(previous)
    assert sources.get_response_href(results) == "https://api.test/second"
    del results
    gc.collect()
    assert reference() is None
    assert identity not in sources._sources
    # Repeated cleanup is harmless.
    discard(previous)


def test_sources_are_isolated_by_identity_and_safe_across_threads():
    results = [JobResults(root={"item": 1}) for _ in range(64)]

    def retain(index):
        value = results[index]
        href = f"https://api.test/{index}"
        sources.register_response_href(value, href)
        assert sources.get_response_href(value) == href

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(retain, range(len(results))))
    for index, value in enumerate(results):
        assert sources.get_response_href(value) == f"https://api.test/{index}"
    assert sources.get_response_href(JobResults(root={"item": 1})) is None
    assert sources.get_response_href(None) is None
