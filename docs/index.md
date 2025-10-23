# Eozilla

A suite of tools around workflow orchestration systems and the
[OGC API - Processes](https://github.com/opengeospatial/ogcapi-processes).

**Note, this project and its documentation is still in an early development stage.**

The Eozilla suite comprises the following packages:

* `cuiman`: A Python client including API, GUI, and CLI for servers 
   compliant with the [OGC API - Processes](https://github.com/opengeospatial/ogcapi-processes).
* `wraptile`: A fast and lightweight HTTP server that implements 
   [OGC API - Processes, Part 1](https://github.com/opengeospatial/ogcapi-processes) for various 
   workflow processing backends, such as Airflow or a local executor.
* `procodile`: A simple Python framework for registering and executing processes.
* `appligator`: An EO application bundler and transformer. 
   (Currently limited to generating [Airflow DAGs](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html).)
* `gavicore`: Common pydantic data models and utilities for the packages above.

Large parts of the work in the Eozilla project has been made possible by the
[ESA DTE-S2GOS project](https://dte-s2gos.rayference.eu/about/).
