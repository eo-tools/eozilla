# STAC results walkthrough

Cuiman can open one selected job output as a native PySTAC `Item` or
`ItemCollection`. This walkthrough uses the local testing service's inline and
linked STAC processes. It also shows how a branded client can reuse the built-in
opener with a small transformation. The maintained sources are the
[runnable script](https://github.com/eo-tools/eozilla/blob/main/examples/guides/cuiman/stac.py)
and [demo notebook](https://github.com/eo-tools/eozilla/blob/main/notebooks/cuiman-stac.ipynb).

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

## What the example opens

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

The `data` Asset is a small Zarr grid. Reading it over HTTP requires the
reader's optional `fsspec[http]` dependencies, which are absent from the default
Pixi environment. Metadata inspection and CSV reading work without them.

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
asset access expressions. The `roles` filter matches any requested role;
`None` shows all assets and an empty iterable matches none.

Assets with `thumbnail`, `overview`, or `visual` roles are opened using the
client's configured result readers and asset access settings. Results with an
HTML or image representation appear
beside the geometry map, or below the table when a map is unavailable. HTTP
images, local files, and supported S3 images can be previewed. Broken links and
unsupported results are skipped. Preview reads may require optional reader
dependencies, such as Pillow for images. Geometry maps require ipyleaflet and
ipywidgets.

The role filter only affects the table. Set `previews=False` to prevent asset
preview reads while retaining geometry previews.

For display without a client, use the async helper directly:

```python
from cuiman.api.assets import show_assets

await show_assets(items, roles="metadata")
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
