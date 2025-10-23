# WARNING - THIS IS GENERATED CODE
#   Generator: Eozilla Appligator v0.0.5.dev0
#        Date: 2025-10-23T11:47:13.129617

from airflow.sdk import Param, dag, task

from wraptile.services.local.testing import return_base_model


@dag(
    'return_base_model',
    dag_display_name='BaseModel Test',
    description=None,
    params={
        'scene_spec': Param(type='object', title='SceneSpec', properties={'threshold': {'title': 'Threshold', 'type': 'number'}, 'factor': {'title': 'Factor', 'type': 'number'}}, required=['threshold', 'factor']),
    },
    is_paused_upon_creation=False,
)
def return_base_model_dag():

    @task(multiple_outputs=False)
    def return_base_model_task(params):
        return return_base_model(**params)

    task_instance = return_base_model_task()  # noqa: F841

return_base_model_dag()
