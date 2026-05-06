#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from airflow.models import DagBag


def test_dag_loads():
    dagbag = DagBag()
    dag = dagbag.get_dag("Eozilla-Example-DAG")
    assert dag is not None
    assert dag.dag_id == "Eozilla-Example-DAG"
