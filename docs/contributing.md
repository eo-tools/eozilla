# Contributing to the project

## Changelog

You can find the complete changelog 
[here](https://github.com/eo-tools/eozilla/blob/main/CHANGES.md). 

## Reporting

If you have suggestions, ideas, feature requests, or if you have identified
a malfunction or error, then please 
[post an issue](https://github.com/eo-tools/eozilla/issues). 

## Contributions

The Eozilla project welcomes contributions of any form as long as you 
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

### Running the Eozilla server with a local test service

Run local test server (or use shorter command `pixi run serve`)

```commandline
wraptile run -- wraptile.services.local.testing:service
```

The dev mode is useful if you are changing server code:

```commandline
wraptile dev -- wraptile.services.local.testing:service
```

Run the Eozilla client Python API

```python
from cuiman import Client

client = Client()
client.get_processes()
client.get_jobs()
```

Run Eozilla client GUI (in Jupyter notebooks)

```python
from cuiman import Client

client = Client()
client.show_app()
```

Run Eozilla client CLI

```commandline
$ cuiman --help
```

### Formatting & code checking

```commandline
pixi run format 
pixi run checks
```

### Testing & Coverage

```commandline
pixi run tests
pixi run coverage
```

### Version syncing

Before a release increase version number in root `pyproject.toml`
then synchronize versions in workspaces `tools/pyproject.toml` using 

```commandline
pixi run sync-versions
```

### Cuiman GUI changes

The cuiman package bundles the [Eozilla App](https://github.com/eo-tools/eozilla-app)
to use it as the client GUI.
Eozilla App is a single page web application (SPA) built with React and TypeScript.
For team development, check out its separate Git repository inside the Eozilla
repository at `eozilla/eozilla-app/`. The repositories remain independent, but
this standard workspace layout lets the app run against the local Eozilla
development service and build into Cuiman:

```text
eozilla/
  eozilla-app/
```

Clone Eozilla (if not already done):

```commandline
git clone https://github.com/eo-tools/eozilla.git
cd ./eozilla
pixi install
```

Then, from the Eozilla repository root, clone and install Eozilla App:

```commandline
git clone https://github.com/eo-tools/eozilla-app.git eozilla-app
cd ./eozilla-app
npm install
```

If you do not have a process API available, you can run the local test server
for development in another terminal (also within the `eozilla-app` folder):

```commandline
npm run eozilla:dev
```

Note, this is equivalent to running the following command `pixi run serve` 
in the `eozilla` folder.

Then run the Eozilla App in a browser using the [vite]() dev server:

```commandline
npm run dev
```

Once you are done, you can bundle a new app build with the 
Eozilla Cuiman package:

```commandline
npm run eozilla:build
```

Substantial Eozilla App code changes must be reflected in the relevant pages
under `docs/eozilla-app/`. Keep the overview, service-provider, schema-form,
and dynamic-expression documentation accurate when changes affect those areas.


### Code generation

Some code is generated (see respective file headers)
from an OpenAPI specification in `tools/openapi.yaml`. 
If this file is changed, code need to be regenerated: 

```commandline
pixi run generate
```

This will generate Eozilla's

- client implementation in `cuiman/src/cuiman/client.py` and CLI documentation `docs/cli.md`
- server routes in `wraptile/src/wraptile/routes.py` and the 
  service interface in `wraptile/src/wraptile/service.py`

### Documentation

The Eozilla documentation is built using the 
[mkdocs](https://www.mkdocs.org/) tool.

With repository root as current working directory:

```bash
mkdocs build
mkdocs serve
mkdocs gh-deploy
```

The documentations of all Eozilla CLIs are generated.
After changing any CLI code, always update their respective 
documentation by running

```bash
pixi run gen-cli-docs
```

Which will output something like the following:
```
Pixi task (gen-cli-docs): python -m tools.gen_cli_docs
Docs saved to: eozilla/docs/cuiman/cli.md
Docs saved to: eozilla/docs/wraptile/cli.md
Docs saved to: eozilla/docs/procodile/cli.md
Docs saved to: eozilla/docs/appligator/cli.md
```

### Releasing

Creating a tagged release on GitHub automatically runs the repository's
`publish-pypi` workflow, which creates packages on PyPI. The publication
of the PyPI packages, in turn, triggers the creation of package update
pull requests in the corresponding conda-forge feedstock repositories.
During the build process, conda-forge tests each package with its current
dependencies, so it's important to merge these PRs in an order corresponding
to the graph of dependencies between eozilla packages. For instance, tests
for procodile 0.1.2 will fail if the corresponding gavicore 0.1.2 package is
not yet published on conda-forge. Merging can be done in four batches:

1. gavicore (dependency of everything)
2. cuiman and procodile (only depend on gavicore)
3. wraptile and appligator (depend on procodile and gavicore)
4. eozilla (depends on everything)

After each merge, it takes some time (usually around an hour) for the updated
package to become available on conda-forge.

## License

The Eozilla project is open source made available under the terms and 
conditions of the [Apache 2.0 license](https://www.apache.org/licenses/LICENSE-2.0.html).
