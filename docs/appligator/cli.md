# Appligator CLI

Generate various application formats from your processes.

WARNING: This tool is under development and subject to change anytime.

Currently, it expects a _process registry_ as input, which must be
provided in form a Python module path plus an attribute path separated
by a colon: &quot;my.module.path:my.registry_obj&quot;. The type of the registry
must be `procodile.ProcessRegistry`. In the future the tool will be
able to handle other input types.

It is also currently limited to generating DAGs for Airflow 3+.
The plan is to extend it to also output Docker images with or
without metadata such as the OGC CWL standard (= EOAP).

**Usage**:

```console
$ main [OPTIONS] [PROCESS_REGISTRY_SPEC]
```

**Arguments**:

* `[PROCESS_REGISTRY_SPEC]`: Process registry specification. For example &#x27;wraptile.services.local.testing:service.process_registry&#x27;.

**Options**:

* `--dags-folder PATH`: An Airflow DAGs folder to which to write the outputs.  [default: C:\Users\norma\Projects\eozilla\eozilla-airflow\dags]
* `--image-name TEXT`: Name of the Docker image which is created from your workflow and required packages that Airflow will use for running the workflows in the registry.  [default: appligator_workflow_image:v1]
* `--version / --no-version`: Show version and exit.  [default: no-version]
* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.
