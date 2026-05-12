# Appligator 

Eozilla _Appligator_ is tool that transforms (often bundles) your workflows so 
they can be recognized and executed by specific workflow orchestrators. 

Currently, Appligator can generate [Docker](https://www.docker.com/) images 
and [Apache Airflow](https://airflow.apache.org/) DAGs from processes written with 
[Procodile](../procodile/introduction.md). 

In the future we will also allow targeting other workflow orchestration backends, 
especially by generating
[OGC Earth Observation Application Packages (EOAP)](https://eoap.github.io/) 
for which execution platforms already exist and are currently being developed. 
We also plan to generate Docker images and EOAPs directly from
[Jupyter notebooks](https://jupyter.org/). Transformers targeting different 
workflow orchestrators will be provided as Appligator plugins. 
