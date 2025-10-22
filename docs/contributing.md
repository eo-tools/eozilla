# Contributing to the project

## Changelog

You can find the complete changelog 
[here](https://github.com/eo-tools/eozilla/blob/main/CHANGES.md). 

## Reporting

If you have suggestions, ideas, feature requests, or if you have identified
a malfunction or error, then please 
[post an issue](https://github.com/eo-tools/eozilla/issues). 

## Contributions

The S2GOS client project welcomes contributions of any form as long as you 
respect our 
[code of conduct](https://github.com/eo-tools/eozilla/blob/main/CODE_OF_CONDUCT.md)
and follow our 
[contribution guide](https://github.com/eo-tools/eozilla/blob/main/CONTRIBUTING.md).

If you'd like to submit code or documentation changes, we ask you to provide a 
pull request (PR) 
[here](https://github.com/eo-tools/eozilla/pulls). 
For code and configuration changes, your PR must be linked to a 
corresponding issue. 

## Development

### Setup

Before you start, make sure you have [pixi](https://pixi.sh) installed.

Checkout sources

```commandline
git clone https://github.com/eo-tools/eozilla.git
cd ./eozilla
```

Create a new Python environment and activate it:

```commandline
pixi install 
pixi shell
```

### Running the S2GOS controller tools

Run local test server

```commandline
s2gos-server run -- s2gos_server.services.local.testing:service
```

The dev mode is useful if you are changing server code:

```commandline
s2gos-server dev s2gos_server.services.local.testing:service
```

Run client API

```python
from s2gos_client import Client

client = Client()
client.get_processes()
client.get_jobs()
```

Run client GUI (in Jupyter notebooks)

```python
from s2gos_client.gui import Client

client = Client()
client.show()
client.show_jobs()
```

Run client CLI

```commandline
$ s2gos-client --help
```

### Formatting & Linting

```commandline
pixi run isort .
pixi run ruff format 
pixi run ruff check
```

### Testing & Coverage

```commandline
pixi run test
pixi run coverage
```

### Version syncing

Before a release increase version number in root `pyproject.toml`
then synchronize versions in workspaces `tools/pyproject.toml` using 

```commandline
pixi run sync-versions
```

### Code generation

Some code is generated (see respective file headers)
from an OpenAPI specification in `tools/openapi.yaml`. 
If this file is changed, code need to be regenerated: 

```commandline
pixi run generate
```

This will generate S2GOS'

- [pydantic](https://docs.pydantic.dev/) models in `gavicore/src/s2gos_common/models.py` 
(uses [datamodel-code-generator](https://koxudaxi.github.io/datamodel-code-generator/))
- client implementation in `s2gos-client/src/s2gos_client/client.py` and CLI documentation `docs/cli.md`
- server routes in `s2gos-server/src/s2gos_server/routes.py` and the 
  service interface in `s2gos-server/src/s2gos_server/service.py`

### Documentation

The S2GOS client's documentation is built using the 
[mkdocs](https://www.mkdocs.org/) tool.

With repository root as current working directory:

```bash
mkdocs build
mkdocs serve
mkdocs gh-deploy
```

After changing the CLI code, always update its documentation `docs/cli.md` 
by running

```bash
pixi run gen-client
```

## License

The S2GOS client is open source made available under the terms and conditions of the 
[Apache 2.0 license](https://www.apache.org/licenses/LICENSE-2.0.html).
