"""Run the API walkthrough with the local test service.

Run from the repository root with ``python -m examples.guides.cuiman.api``.
This submits one job and checks its status once. Importing does not connect.
"""

# --8<-- [start:imports]
from cuiman import Client
from gavicore.models import JobResults, JobStatus, ProcessDescription, ProcessRequest

# --8<-- [end:imports]


# --8<-- [start:create-client]
def create_client() -> Client:
    """Connect to the local test service without authentication."""
    return Client(api_url="http://127.0.0.1:8008", auth={"auth_type": "none"})


# --8<-- [end:create-client]


# --8<-- [start:inspect]
def inspect_process(client: Client, process_id: str) -> ProcessDescription:
    """List processes and return the selected process description."""
    print(client.get_processes().model_dump_json(indent=2))
    process = client.get_process(process_id)
    print(process.model_dump_json(indent=2))
    return process


# --8<-- [end:inspect]


# --8<-- [start:submit]
def submit_process(client: Client, process_id: str, request: ProcessRequest) -> str:
    """Submit once and return the server-assigned job ID."""
    job = client.execute_process(process_id, request=request)
    print(job.model_dump_json(indent=2))
    return job.jobID


# --8<-- [end:submit]


# --8<-- [start:results]
def inspect_results(client: Client, job_id: str) -> JobResults | None:
    """Check once and retrieve results only for a successful job."""
    job = client.get_job(job_id)
    print(job.model_dump_json(indent=2))
    if job.status in (JobStatus.accepted, JobStatus.running):
        print("Check this job again later; do not submit it again.")
        return None
    if job.status != JobStatus.successful:
        print("Job did not succeed. Inspect its status and message before retrying.")
        return None
    results = client.get_job_results(job_id)
    print(results.model_dump_json(indent=2))
    return results


# --8<-- [end:results]


def example_session() -> str:
    """Submit a prime-number job, check once, and always close the client."""
    # --8<-- [start:connect-call]
    client = create_client()
    # --8<-- [end:connect-call]
    try:
        # --8<-- [start:inspect-call]
        process_id = "primes_between"
        inspect_process(client, process_id)
        # --8<-- [end:inspect-call]

        # --8<-- [start:submit-call]
        request = ProcessRequest(inputs={"min_val": 10, "max_val": 80})
        job_id = submit_process(client, process_id, request)
        # --8<-- [end:submit-call]

        # --8<-- [start:results-call]
        results = inspect_results(client, job_id)
        # --8<-- [end:results-call]
        if results is None:
            print(f"Retain this job ID for later: {job_id}")
        return job_id
    finally:
        # --8<-- [start:close]
        client.close()
        # --8<-- [end:close]


# --8<-- [start:failure]
def submit_failure_example(client: Client) -> str:
    """Create a short job that deliberately fails halfway through."""
    return submit_process(
        client,
        "sleep_a_while",
        ProcessRequest(inputs={"duration": 2, "fail": True}),
    )


# --8<-- [end:failure]


if __name__ == "__main__":
    example_session()
