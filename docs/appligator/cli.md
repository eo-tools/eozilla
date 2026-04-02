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
* `--skip-build / --no-skip-build`: Skip building the Docker image and only generate DAG files.  [default: skip-build]
* `--secret-name TEXT`: Kubernetes secret name to inject as environment variables into every pod. Repeatable — supply the flag multiple times to add more than one secret (e.g. `--secret-name my-secret --secret-name other-secret`).
* `--dag-name TEXT`: Custom stem for the generated DAG file(s) instead of the process ID. With a single process, produces `<dag-name>.py`. With multiple processes, produces `<dag-name>_<process_id>.py` for each.
* `--cpu-request TEXT`: CPU request applied to every generated pod (e.g. `500m`, `1`).
* `--memory-request TEXT`: Memory request applied to every generated pod (e.g. `256Mi`, `1Gi`).
* `--cpu-limit TEXT`: CPU limit applied to every generated pod (e.g. `2`).
* `--memory-limit TEXT`: Memory limit applied to every generated pod (e.g. `2Gi`).
* `--pvc-mount TEXT`: Mount a PersistentVolumeClaim into every pod. Format: `name:claim_name:mount_path` (e.g. `--pvc-mount output:my-pvc:/mnt/output`). Repeatable.
* `--config-map-mount TEXT`: Mount a ConfigMap into every pod. Format: `name:config_map_name:mount_path` or `name:config_map_name:mount_path:sub_path` (e.g. `--config-map-mount settings:my-cm:/app/settings.yaml:settings.yaml`). Repeatable.
* `--version / --no-version`: Show version and exit.  [default: no-version]
* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.
