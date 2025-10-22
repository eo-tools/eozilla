from airflow.models import DagBag


def test_dag_loads():
    dagbag = DagBag()
    dag = dagbag.get_dag("S2GOS-Example-DAG")
    assert dag is not None
    assert dag.dag_id == "S2GOS-Example-DAG"