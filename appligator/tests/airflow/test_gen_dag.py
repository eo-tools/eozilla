#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import pytest

from appligator.airflow.gen_dag import gen_dag
from procodile import Process


def f(x: int, y: int) -> int:
    return x * y


process = Process.create(function=f, id="f", version="0.0.0", title="Test process")


def test_gen_dag_from_process():
    assert gen_dag(process) == (
        "from airflow.sdk import Param, dag, task\n"
        "\n"
        "from tests.airflow.test_gen_dag import f\n"
        "\n"
        "\n"
        "@dag(\n"
        "    'f',\n"
        "    dag_display_name='Test process',\n"
        "    description=None,\n"
        "    params={\n"
        "        'x': Param(type='integer', title='X'),\n"
        "        'y': Param(type='integer', title='Y'),\n"
        "    },\n"
        "    is_paused_upon_creation=False,\n"
        ")\n"
        "def f_dag():\n"
        "\n"
        "    @task(multiple_outputs=False)\n"
        "    def f_task(params):\n"
        "        return f(**params)\n"
        "\n"
        "    task_instance = f_task()  # noqa: F841\n"
        "\n"
        "f_dag()\n"
    )


def test_gen_dag_from_process_description():
    assert gen_dag(process.description, function_module="a.b.c.d") == (
        "from airflow.sdk import Param, dag, task\n"
        "\n"
        "from a.b.c.d import f\n"
        "\n"
        "\n"
        "@dag(\n"
        "    'f',\n"
        "    dag_display_name='Test process',\n"
        "    description=None,\n"
        "    params={\n"
        "        'x': Param(type='integer', title='X'),\n"
        "        'y': Param(type='integer', title='Y'),\n"
        "    },\n"
        "    is_paused_upon_creation=False,\n"
        ")\n"
        "def f_dag():\n"
        "\n"
        "    @task(multiple_outputs=False)\n"
        "    def f_task(params):\n"
        "        return f(**params)\n"
        "\n"
        "    task_instance = f_task()  # noqa: F841\n"
        "\n"
        "f_dag()\n"
    )


def test_gen_dag_fail():
    with pytest.raises(TypeError, match="unexpected type for process: int"):
        # noinspection PyTypeChecker
        gen_dag(13)

    with pytest.raises(ValueError, match="function_module argument is required"):
        # noinspection PyTypeChecker
        gen_dag(process.description, None)
