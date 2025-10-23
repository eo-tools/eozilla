# Eozilla

A suite of tools around workflow orchestration systems and the
[OGC API - Processes](https://github.com/opengeospatial/ogcapi-processes).

**Note, this project and its documentation is still in an early development stage.**

The Eozilla suite comprises the following packages:

* `cuiman`: A Python client including API, GUI, and CLI for servers 
   compliant with _OGC API - Processes_.
* `wraptile`: A fast and lightweight HTTP server that implements _OGC API - Processes_
   for various workflow processing backends, such Airflow or a local executor.
* `procodile`: A simple Python framework for registering and executing processes.
* `appligator`: An EO application bundler and transformer. 
   (Currently limited to generating Airflow DAGs.)
* `gavicore`: Common pydantic data models and utilities for the packages above.

Large parts of the work in the Eozilla project has been made possible by the
[ESA DTE-S2GOS project](https://dte-s2gos.rayference.eu/about/).
