#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Annotated

from pydantic import Field

from s2gos_common.process import JobContext, ProcessRegistry

registry = ProcessRegistry()


@registry.process(
    id="sleep_a_while",
    title="Sleepy Process",
)
def sleep_a_while(
    duration: Annotated[float, Field(title="Duration in s", gt=0)] = 10.0,
    fail: Annotated[bool, Field(title="Force failure")] = False,
) -> float:
    """
    Sleeps for `duration` seconds.
    Fails on purpose if `fail` is `True` after 50% progress.
    Returns the effective amount of sleep in seconds.
    """
    import time

    ctx = JobContext.get()

    t0 = time.time()
    for i in range(101):
        ctx.report_progress(progress=i)
        if fail and i == 50:
            raise RuntimeError("Woke up too early")
        time.sleep(duration / 100)
    return time.time() - t0


@registry.process(
    id="primes_between",
    title="Prime Generator",
)
def primes_between(
    ctx: JobContext,
    min_val: Annotated[int, Field(title="Minimum value of search range", ge=0)] = 0,
    max_val: Annotated[int, Field(title="Maximum value of search range", ge=0)] = 100,
) -> list[int]:
    """Computes the list of prime numbers within an integer value range."""

    if max_val < 2 or max_val <= min_val:
        raise ValueError("max_val must be greater 1 and greater min_val")

    ctx.report_progress(message="Step 1: Generate sieve up to sqrt(max_val)")
    limit = int(max_val**0.5) + 1
    is_prime_small = [True] * (limit + 1)
    is_prime_small[0:2] = [False, False]
    for i in range(2, int(limit**0.5) + 1):
        if is_prime_small[i]:
            for j in range(i * i, limit + 1, i):
                is_prime_small[j] = False
    small_primes = [i for i, prime in enumerate(is_prime_small) if prime]

    ctx.report_progress(
        message="Step 2: Create the sieve for the range [min_val, max_val]"
    )
    sieve_range = max_val - min_val + 1
    is_prime = [True] * sieve_range

    for p in small_primes:
        # Find the first multiple of p in the range [min_val, max_val]
        start = max(p * p, ((min_val + p - 1) // p) * p)
        for j in range(start, max_val + 1, p):
            is_prime[j - min_val] = False

    for n in range(min_val, min(min_val + 2, max_val + 1)):
        if n < 2:
            is_prime[n - min_val] = False

    ctx.report_progress(message="Done")
    return [min_val + i for i, prime in enumerate(is_prime) if prime]
