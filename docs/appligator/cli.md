# Appligator CLI

Generate various application formats from your processes.

WARNING: This tool is under development and subject to change anytime.

Currently, it expects a _process registry_ as input, which must be
provided in form a Python module path plus an attribute path separated
by a colon: "my.module.path:my.registry_obj". The type of the registry
must be `procodile.ProcessRegistry`. In the future the tool will be
able to handle other input types.

It is also currently limited to generating DAGs for Airflow 3+.
The plan is to extend it to also output Docker images with or
without metadata such as the OGC CWL standard (= EOAP).

**Usage**:

```console
$ appligator [OPTIONS] [PROCESS_REGISTRY_SPEC]
```

**Arguments**:

* `[PROCESS_REGISTRY_SPEC]`: Process registry specification. For example 'wraptile.services.local.testing:service.process_registry'.

**Options**:

* `--dags-folder PATH`: An Airflow DAGs folder to which to write the outputs.  [default: <eozilla-root>/eozilla-airflow/dags`]
* `--image-name TEXT`: Name of the Docker image which is created from your workflow and required packages that Airflow will use for running the workflows in the registry.
* `--config-file FILE`: Path to an appligator-config.yaml file. Values from the file are used as defaults; any flag passed explicitly on the command line takes precedence.
* `--version / --no-version`: Show version and exit.  [default: no-version]
* `--skip-build / --no-skip-build`: Skip building the Docker image and only generate DAG files.  [default: skip-build]
* `--secret-name TEXT`: Kubernetes secret name to inject as environment variables into every pod (repeatable, e.g. --secret-name my-secret --secret-name other-secret).
* `--dag-name TEXT`: Custom name for the generated DAG file (without .py extension). Defaults to the process ID. If multiple processes are in the registry, each gets a suffix: <dag-name>_<process_id>.py.
* `--cpu-request TEXT`: CPU request for every pod (e.g. '500m', '1').
* `--memory-request TEXT`: Memory request for every pod (e.g. '256Mi', '1Gi').
* `--cpu-limit TEXT`: CPU limit for every pod (e.g. '2').
* `--memory-limit TEXT`: Memory limit for every pod (e.g. '2Gi').
* `--pvc-mount TEXT`: Mount a PersistentVolumeClaim into every pod. Format: name:claim_name:mount_path (e.g. --pvc-mount output:my-pvc:/mnt/output). Repeatable.
* `--config-map-mount TEXT`: Mount a ConfigMap into every pod. Format: name:config_map_name:mount_path or name:config_map_name:mount_path:sub_path (e.g. --config-map-mount settings:my-cm:/app/settings.yaml:settings.yaml). Repeatable.
* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.
