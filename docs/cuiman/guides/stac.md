# STAC results walkthrough

Cuiman can open one selected job output as a native PySTAC `Item` or
`ItemCollection`. This walkthrough uses the local testing service's inline and
linked STAC processes. The [demo notebook](https://github.com/eo-tools/eozilla/blob/main/notebooks/cuiman-stac.ipynb)
teaches the end-user workflow: submit a process, browse scenes and assets, then
open a data Asset as an xarray Dataset. It uses an ordinary `Client` and the
built-in STAC readers.

## Start the local service

From the repository root, start the service in a separate terminal:

```powershell
pixi run serve
```

It listens on `http://127.0.0.1:8008` and serves generated STAC documents and
small CSV/Zarr products under `/testing-stac`. To keep this demo's files separate,
set `EOZILLA_TESTING_STAC_DIR` to an unused directory **before** starting the
service; the default is `.pixi/testing-stac`. Set
`EOZILLA_TESTING_STAC_URL` if the browser or client reaches the service through a
different hostname, port, or proxy. See [Wraptile's setup](../../wraptile/usage.md#stac-testing-processes)
for both settings and the raw output shapes.

In a second terminal, enter `pixi shell` from the repository root, then run:

```powershell
python -m examples.guides.cuiman.stac
```

Alternatively open `notebooks/cuiman-stac.ipynb` with Jupyter in the Pixi
environment and run its cells in order. Each execution creates two jobs and
their output files. Avoid rerunning the submission cell unless you want more
jobs.

The notebook completes the inline process first: open its Item, call
`client.show_assets(inline_item)` to see its footprint and synthetic preview,
then open `inline_item.assets["data"]` with `data_type=xr.Dataset, engine="zarr"`.
It next runs the linked process, displays its ItemCollection, and opens the
second scene's data Asset. Both grids are inspected and closed after use.
Each process has a separate submission cell; there are no loops over jobs,
custom client classes, or example-module imports.

Run the notebook and demo service on the same machine. Demo Assets include local
file alternates, which Cuiman prefers for reading the Zarr grid and PNG preview.
This avoids requiring HTTP Zarr dependencies for this local walkthrough. Maps
use ipyleaflet and previews use Pillow, both included in the Pixi environment.

## Companion script

The separate [runnable script](https://github.com/eo-tools/eozilla/blob/main/examples/guides/cuiman/stac.py)
also demonstrates client customization for developers.

The script registers a composed opener through `DemoClientConfig` without
changing Cuiman's global defaults. Its predicate selects the `item` and
`item_collection` outputs of the two testing processes; its async transform
marks loaded Items with `demo:reviewed`. The built-in opener still handles
native parsing. Each returned Item is independent of the original job result.

For each job, the example opens the Item and ItemCollection, then calls
`get_job_results(job_id)` to inspect the original five output values. Inline
`item` is JSON in those results; linked `item` is an ordinary Link whose metadata
document is fetched over HTTP only when opened. The example selects the Item's
`report` Asset and passes that exact Asset to Cuiman's pandas reader. It prints
the CSV mean of `1.5`. Opening this Asset does not rerun the STAC transform or
fetch sibling Assets.

The `data` Asset is a small Zarr grid. If you read it from a remote service
using its HTTP location, install the reader's optional `fsspec[http]`
dependencies. The local file alternate is accessible only on the service's
machine or a shared filesystem.

## Display assets in a notebook

Use the client's `show_assets` method to display an Item, a sequence of Items,
or an ItemCollection:

```python
client.show_assets(item)
client.show_assets(items, roles=["data", "metadata"])
client.show_assets(items, previews=False)
```

For an `AsyncClient`, await the method: `await client.show_assets(items)`.

The table includes asset keys, file links, titles, roles, and buttons to copy
asset access expressions. Each scene card shows additional item properties below
its name and date, with a compact geometry map and previews at the upper right.
The map fits the geometry when displayed and resized; panning preserves your
chosen zoom. On narrow screens, the header wraps above the full-width asset table.
Where caller source is available, the copied expression
starts with the supplied argument: `client.show_assets(items[1])` produces
`items[1].assets['asset-key']`. Sequences and ItemCollections add the appropriate
item index before asset access. If the source cannot be recovered, the display
uses `item`, `items`, or `item_collection` as a placeholder to adapt after copying.
The `roles` filter matches any requested role;
`None` shows all assets and an empty iterable matches none.

Assets with `thumbnail`, `overview`, or `visual` roles are opened using the
client's configured result readers and asset access settings. Results with an
HTML or image representation appear
beside the geometry map, or beside the item heading when a map is unavailable. HTTP
images, local files, and supported S3 images can be previewed. Broken links and
unsupported results are skipped. Preview reads may require optional reader
dependencies, such as Pillow for images. Geometry maps require ipyleaflet and
ipywidgets.

The role filter only affects the table. Set `previews=False` to prevent asset
preview reads while retaining geometry previews.

For display without a client, use the async helper directly:

```python
from cuiman.api.assets import display_assets

await display_assets(items, roles="metadata")
```

Without `open_asset`, the helper displays tables and geometry maps and skips
asset previews. Supply a synchronous or asynchronous `open_asset` callable to
enable asset previews, for example `open_asset=client.open_job_result`.

## Try the browser app

With the same testing service running, connect eozilla-app to its processing
API and execute `create_inline_stac` and `create_linked_stac` with
`{"inputs": {"item_count": 2}}`. Inspect the raw output names and values. The
linked `item` and `item_collection` hrefs should open as JSON documents at the
service's `/testing-stac` route in a browser. This checks that the service URL
and browser access are correct. The Python composition transform is registered
only on the branded Cuiman client; it does not modify service output or add a
browser-specific STAC view.

## Finish and clean up

The script closes its client; the notebook's final cell does the same. Stop the
service when finished, then remove only the generated run directories you no
longer need from its configured artifact directory. The service does not delete
them when a client closes. Native PySTAC navigation to subsequently fetched
documents remains lazy and does not invoke the composition transform. Cuiman's
initial opener reads only the selected metadata document, and neither it nor
the transform scans for other products. For more on requested types, Asset
options, and access policy, see [Result openers](openers.md).
