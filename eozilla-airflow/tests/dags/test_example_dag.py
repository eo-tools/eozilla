from airflow.models import DagBag


def test_dag_loads():
    dagbag = DagBag()
    dag = dagbag.get_dag("Eozilla-Example-DAG")
    assert dag is not None
    assert dag.dag_id == "Eozilla-Example-DAG"
