# Procodile Introduction

Eozilla _Procodile_ is a simple Python framework that
facilitates publishing of your Python functions as OGC processes, 
e.g., via the Eozilla [Wraptile server](../wraptile/introduction.md).

To serve this purpose, it enables the following:

- Registering your workflows comprising an entry-point (main) and
  steps implemented as Python functions.
- Querying and executing the workflow entry points via a dedicated Python API
  and CLI.
- Using YAML and JSON formats based on the interfaces and models
  defined by [OGC API - Processes](https://github.com/opengeospatial/ogcapi-processes).

Herewith it allows later application packaging by 
Eozilla [Appligator](../appligator/introduction.md).

Processor packages developed using the provided CLI can later on be used to
generate Docker images, Airflow DAGs, and optionally OGC Application Packages.
