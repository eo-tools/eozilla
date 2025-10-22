# Eozilla Airflow   

Testing Airflow DAGs with Eozilla's Cuiman client and Wraptile server. 

## Setup

This setup creates a minimal local Airflow development environment 
using [pixi](https://pixi.sh).
All packages are currently installed from PyPI as this is the only reliable
way to install Airflow 3.0.
Also, all Airflow configuration is local, namely in `./.airflow`, 
see `AIRFLOW_HOME` variable in `pyproject.toml`.

Windows users: this setup has been successfully tested with 
[WSL2](https://learn.microsoft.com/de-de/windows/wsl/) 2.4.11 
using Ubuntu 24.04.2 LTS. Airflow has no official Windows support. 

```bash
cd projects
git clone https://github.com/eo-tools/eozilla.git
cd eozilla/eozilla-airflow 
```

```bash
pixi install
pixi run install-airflow
```

## Code

```bash
pixi shell
```

Given that [VS Code](https://code.visualstudio.com/download) is installed 

```bash
code .
```

WSL users, see [VS Code with WSL](https://learn.microsoft.com/en-us/windows/wsl/tutorials/wsl-vscode).

## Develop

```bash
pixi run format
pixi run test
pixi run check
pixi run typecheck
```

## Generate DAGs

```bash
pixi run gen-dags
```

## Run Airflow

Run all Airflow services at once:

```bash
pixi run airflow standalone
```

Or run each Airflow service individually:

```bash
pixi run airflow db migrate
pixi run airflow dag-processor
pixi run airflow scheduler
pixi run airflow api-server
```

The Airflow API Server runs at URL http://localhost:8080. To find login credentials, 
search for the log entry `Simple auth manager | Password for user 'admin'`.

If you forgot the username/password, you can look it up in 
`.airflow/simple_auth_manager_passwords.json.generated`.
You can safely delete the file to force creation of a new password.
