# WARNING - THIS IS GENERATED CODE
#   Generator: Eozilla Appligator v0.0.5.dev0
#        Date: 2025-10-23T11:47:13.128497

from airflow.sdk import Param, dag, task

from wraptile.services.local.testing import sleep_a_while


@dag(
    'sleep_a_while',
    dag_display_name='Sleep Processor',
    description='Sleeps for `duration` seconds. Fails on purpose if `fail` is `True`. Returns the effective amount of sleep in seconds.',
    params={
        'duration': Param(default=10.0, type='number', title='Duration'),
        'fail': Param(default=False, type='boolean', title='Fail'),
    },
    is_paused_upon_creation=False,
)
def sleep_a_while_dag():

    @task(multiple_outputs=False)
    def sleep_a_while_task(params):
        return sleep_a_while(**params)

    task_instance = sleep_a_while_task()  # noqa: F841

sleep_a_while_dag()
