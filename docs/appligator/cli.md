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
* `--image-name TEXT`: Name of the Docker image Airflow will use for the generated pods.  [default: appligator_workflow_image:v1]
* `--config-file PATH`: Path to an `appligator-config.yaml` file. Values from the file are used as defaults; any flag passed explicitly on the command line takes precedence.
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

---

## Config file

For production deployments it is more practical to keep all Kubernetes options
in a versioned YAML file rather than passing them as CLI flags on every run.

Create an `appligator-config.yaml` next to your workflow code:

```yaml
image_name: myrepo/myimage:latest
dag_name: my_workflow

secret_names:
  - app-credentials

cpu_request: 500m
memory_request: 1Gi
cpu_limit: "1"
memory_limit: 2Gi

pvc_mounts:
  - name: output
    claim_name: output-pvc
    mount_path: /mnt/output

config_map_mounts:
  - name: app-settings
    config_map_name: app-settings
    mount_path: /opt/pixi/app_settings.yaml
    sub_path: app_settings.yaml   # omit to mount the whole ConfigMap as a directory
```

Then run:

```console
$ appligator my.module:registry --config-file appligator-config.yaml
```

Any flag supplied explicitly on the command line overrides the corresponding
value in the file. For example, to use the same config file but point at a
different image during a one-off test:

```console
$ appligator my.module:registry --config-file appligator-config.yaml \
    --image-name myrepo/myimage:dev
```

All fields in the config file are optional. An empty file (or a file containing
only `{}`) is valid and simply means "no defaults".
