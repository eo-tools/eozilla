# Appligator Usage

## Installation

Eozilla Appligator is distributed by the Python package `appligator`.
Depending on your package manager, use one of the following:

```bash
pip install appligator
```

```bash
conda install appligator
```

```bash
pixi add appligator
```

## Overview

Appligator takes a [Procodile](../procodile/index.md) `ProcessRegistry` and
transforms its workflows into artifacts that can be run by workflow orchestrators.
Currently Appligator targets [Apache Airflow](https://airflow.apache.org/) and
produces two kinds of output:

- **Airflow DAG files** — standalone Python DAG definitions ready to drop into
  an Airflow DAGs folder, with each workflow step executed as a
  `KubernetesPodOperator` task.
- **Docker images** — container images carrying your workflow code and its
  dependencies (optional, controlled by `--skip-build` / `--no-skip-build`).

---

## Usage Recipe

### 1. Define a process registry

Follow the [Procodile usage guide](../procodile/usage.md) to create a
`ProcessRegistry` with one or more workflows. For example, in
`my_app/processes.py`:

```python
from procodile import ProcessRegistry

registry = ProcessRegistry()

@registry.main(id="my_workflow")
def my_workflow(path: str, factor: float = 1.0) -> dict:
    ...
```

### 2. Generate Airflow DAG files

Point `appligator` at the registry using the `module.path:attribute` notation
and choose a destination DAGs folder:

```commandline
appligator my_app.processes:registry \
    --dags-folder /path/to/airflow/dags \
    --image-name myrepo/myimage:latest
```

For each process in the registry, Appligator writes a standalone Python DAG
file to `--dags-folder`. The file name defaults to `<process_id>.py`; use
`--dag-name` to override it. With multiple processes and a custom name, each
file gets a `<dag-name>_<process_id>.py` suffix.

### 3. Build the Docker image

By default, `--skip-build` is active and no image is built. To build the image
as part of the same run, add `--no-skip-build`:

```commandline
appligator my_app.processes:registry \
    --dags-folder /path/to/airflow/dags \
    --image-name myrepo/myimage:latest \
    --no-skip-build
```

For production, build a pixi-based image separately using
[`appligator.airflow.gen_dockerfile.generate`](gen_dockerfile.md).
This produces a lean, reproducible two-stage image and lets you control when
and how the build happens (e.g. in a CI pipeline).

---

## Kubernetes configuration

Appligator forwards several Kubernetes settings to every generated
`KubernetesPodOperator` task.

### Resource requests and limits

```commandline
appligator my_app.processes:registry \
    --image-name myrepo/myimage:latest \
    --cpu-request 500m --memory-request 1Gi \
    --cpu-limit 2 --memory-limit 4Gi
```

### Secrets

Inject Kubernetes secrets as environment variables into every pod.
The flag is repeatable:

```commandline
appligator my_app.processes:registry \
    --image-name myrepo/myimage:latest \
    --secret-name app-credentials \
    --secret-name other-secret
```

### Persistent Volume Claims

Mount a PVC into every pod using `name:claim_name:mount_path`. Repeatable:

```commandline
appligator my_app.processes:registry \
    --image-name myrepo/myimage:latest \
    --pvc-mount output:my-output-pvc:/mnt/output
```

### ConfigMaps

Mount a ConfigMap using `name:config_map_name:mount_path` or
`name:config_map_name:mount_path:sub_path`. Repeatable:

```commandline
appligator my_app.processes:registry \
    --image-name myrepo/myimage:latest \
    --config-map-mount settings:app-settings:/app/settings.yaml:settings.yaml
```

---

## Using a config file

For repeated or production runs it is more practical to keep all options in a
versioned YAML file rather than spelling them out on the command line every time.

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

```commandline
appligator my_app.processes:registry --config-file appligator-config.yaml
```

Any flag supplied explicitly on the command line overrides the corresponding
value from the file:

```commandline
appligator my_app.processes:registry \
    --config-file appligator-config.yaml \
    --image-name myrepo/myimage:dev
```

All fields in the config file are optional. An empty file (or a file
containing only `{}`) is valid and simply means "no defaults".
