#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Annotated

from pydantic import Field

from procodile import JobContext, WorkflowRegistry, FromMain, FromStep, Workflow

registry = WorkflowRegistry()

sleep_a_while = registry.get_or_create_workflow("sleep_a_while")

@sleep_a_while.main(id="sleep_a_while", title="Sleepy Process")
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

primes_between = registry.get_or_create_workflow("primes_between")

@primes_between.main(id="primes_between", title="Prime Generator")
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


bigger_workflow = registry.get_or_create_workflow(id="bigger_workflow")

@bigger_workflow.main(
    id="first_step",
    inputs={"id": Field(title="main input")},
    outputs={
        "a": Field(title="main result", description="The result of the main step"),
    },
    description="This is a workflow with several steps and defined dependencies that "
                "execute sequentially.",
    title="A Big Workflow"
)
def first_step(id: str) -> str:
    from procodile_example.workflow_funcs import fun_a

    return fun_a(id)


@bigger_workflow.step(
    id="second_step",
    inputs={"id": FromMain(output="a")},
)
def second_step(id: str) -> str:
    from procodile_example.workflow_funcs import fun_b

    return fun_b(id)


@bigger_workflow.step(
    id="third_step",
)
def third_step(
    id: Annotated[str, FromStep(step_id="second_step", output="return_value")],
) -> Annotated[str, Field(title="Output from Third Step")]:
    from procodile_example.workflow_funcs import fun_c

    return fun_c(id)


@bigger_workflow.step(
    id="fourth_step",
    outputs={
        "some_str": Field(title="Some Str"),
    },
)
def fourth_step(
    id: Annotated[str, FromStep(step_id="third_step", output="return_value")],
) -> str:
    from procodile_example.workflow_funcs import fun_d

    return fun_d(id)


@bigger_workflow.step(
    id="fifth_step",
    inputs={"id2": FromMain(output="a")},
    outputs={
        "some_other_str": Field(title="Some other Str"),
    },
)
def fifth_step(
    id: Annotated[str, FromStep(step_id="third_step", output="return_value")],
    id2: str,
) -> tuple[str, str]:
    from procodile_example.workflow_funcs import fun_e

    return fun_e(id, id2)


@bigger_workflow.step(
    id="sixth_step",
    outputs={
        "final": Field(title="Final output"),
    },
)
def sixth_step(
    id: Annotated[
        tuple[str, str],
        FromStep(step_id="fifth_step", output="some_other_str"),
    ],
    second_input: Annotated[str, FromStep(step_id="fourth_step", output="some_str")],
) -> tuple[tuple[str, str], str]:
    from procodile_example.workflow_funcs import fun_f

    return fun_f(id, second_input)

## This visualizes the `bigger_workflow`
# dot_str = Workflow.visualize_workflow(bigger_workflow)
# src = Source(dot_str)
# src.render("pipeline", format="png", view=True, cleanup=True)
