# WARNING - THIS IS GENERATED CODE
#   Generator: Eozilla Appligator v0.0.5.dev0
#        Date: 2025-10-23T11:47:13.128899

from airflow.sdk import Param, dag, task

from wraptile.services.local.testing import primes_between


@dag(
    'primes_between',
    dag_display_name='Prime Processor',
    description='Returns the list of prime numbers between a `min_val` and `max_val`.',
    params={
        'min_val': Param(default=0, type='integer', title='Min Val', minimum=0.0),
        'max_val': Param(default=100, type='integer', title='Max Val', maximum=100.0),
    },
    is_paused_upon_creation=False,
)
def primes_between_dag():

    @task(multiple_outputs=False)
    def primes_between_task(params):
        return primes_between(**params)

    task_instance = primes_between_task()  # noqa: F841

primes_between_dag()
