# `gavicore.models` Description

This package provides [Pydantic](https://docs.pydantic.dev/latest/concepts/models/)
models for OGC API - Processes, organized by specification part:

- `gavicore.models.core` contains the Part 1: Core models for process
  descriptions, execution requests, jobs, results, and API errors.
- `gavicore.models.dru` contains the Part 2: Deploy, Replace, Undeploy (DRU)
  models for application packages and execution units. It reuses Core models
  such as `Link` and `ProcessDescription`.

Use explicit module imports when selecting a specification part:

```python
from gavicore.models.core import ProcessDescription
from gavicore.models.dru import OgcApplicationPackage
```

Import model classes from the module that owns them. Both model modules support
JSON representations in Jupyter notebooks.
