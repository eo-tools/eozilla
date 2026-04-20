# Gavicore Overview

The Eozilla _Gavicore_ packages is a small library that provides common 
classes and functions for other Eozilla packages.

It currently comprises the following top-level packages:

- [`models`](./api-models.md) - provides 
  [pydantic](https://pydantic.dev/docs/validation/latest/concepts/models/) 
  model classes for the data models used throughout the 
  [OGC API - Processes, Part 1](https://github.com/opengeospatial/ogcapi-processes) 
  specification.
- [`service`](./api-models.md) - a Python representation of the   
  [OGC API - Processes, Part 1](https://github.com/opengeospatial/ogcapi-processes) 
  interface.
- [`ui`](./api-ui.md) - provides a framework capable of creating user interfaces
  from the [InputDescription][gavicore.models.InputDescription] and 
  [Schema][gavicore.models.Schema] models. 
  See dedicated usage chapters in [GUI Generation](../cuiman/gui-generation.md).
- [`util`](./api-util.md) - various submodules with various reusable utilities.

