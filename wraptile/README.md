# DTE-S2GOS controller server

Python gateway server for the ESA DTE-S2GOS synthetic scene generator service.

## Airflow service

Start by running a local Airflow instance with some test DAGs:
```commandline
cd eozilla-airflow
pixi install
pixi run airflow standalone
```

Then run the S2GOS gateway server with the local Airflow instance (assuming
the local Airflow webserver runs on http://localhost:8080):

```commandline
pixi shell
wraptile run -- s2gos_server.services.airflow:service --airflow-password=a8e7f4bb230
```

The possible options are

* `--airflow-base-url=TEXT`: The base URL of the Airflow web API, defaults to 
  `http://localhost:8080`. 
* `--airflow-username=TEXT`: The Airflow username, defaults to `admin`. 
* `--airflow-password=TEXT`: The Airflow password. 
  For an Airflow installation with the simple Auth manager, use the one from
  `.airflow/simple_auth_manager_passwords.json.generated`.


## Local service

Running the S2GOS gateway server with a local service:

```commandline
pixi shell
wraptile run -- s2gos_server.services.local.testing:service --processes --max-workers=5
```

The possible options are

* `--processes` /  `--no-processes`: Whether to use processes or threads, defaults
  to threads.
* `--max-workers=INTEGER`: Maximum number of processes or threads, defaults to 3.

