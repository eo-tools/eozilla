# PySTAC Job Results and Asset Opening

Status: proposed design for a new implementation branch from `main`. This is a
self-contained alternative to the generic resource/resolver design. Creating this
document changes neither the existing implementation nor its specification.

The baseline inspected on 2026-10-08 is local `main` at
`7c06deaee8d95225bb9b90e9c7f55853a883a4ed`. Implementation must inspect the actual
branch baseline again rather than assume that code from another feature branch
is present. In particular, a separately proposed Procodile schema-reference fix
must not be assumed to have landed.

Requirements below define Cuiman behavior. External references describe PySTAC
or STAC capabilities; they do not imply that those libraries already implement
the proposed Cuiman integration. Names explicitly marked illustrative are not
additional public API commitments.

## 1. Purpose and scope

OGC API - Processes outputs commonly describe EO products such as datacubes,
Zarr datasets, and cloud-optimized GeoTIFFs. Use PySTAC's familiar objects for
STAC metadata, navigation, and Asset selection, and use Cuiman's existing opener
framework to read selected data.

The public workflow is **open STAC output → inspect/select with PySTAC → open
Asset**:

```python
item = client.open_job_result(job_id, output_name="result")
asset = item.assets["data"]
dataset = client.open_job_result(asset, chunks="auto")
```

There are two meanings of opening: the first call reads a metadata document into
a native PySTAC object; the second reads the explicitly selected Asset into the
requested Python representation. Opening a STAC output must not select its first
Asset, assemble a datacube, or read Asset payloads automatically.

Initial scope includes native STAC objects, an optional built-in STAC opener,
the Asset overload, STAC transformation, reader-option resolution, and scoped
access. Ordinary outputs remain supported through the existing opener framework.
No generic resource model, resolver registry, resource listing, capability
snapshot model, or Cuiman pagination API is required for this workflow.

Uniform listing and diagnostics across arbitrary outputs, notebook presentation,
CLI/App inspection, and previews remain future extension options in section 9.
Their deferral must not make STAC transformation optional.

## 2. Integration with the main-branch opener framework

Reuse the existing `JobResultOpener`, `JobResultOpenerRegistry`, `ClientConfig`,
optional-module handling, and ordered dispatch. Add a built-in
`StacJobResultOpener` under `cuiman.api.opener.impl`, following the existing
separation between optional wrappers and concrete implementations where useful.
Application extensions continue to use `extra_job_result_openers` and
`register_job_result_opener()`; retain configuration-class isolation, later
registration precedence, and idempotent unregister callbacks.

The baseline opener methods are `is_usable()`, `accept_job_result(ctx)`, and
`open_job_result(ctx)`. Both client argument forms must use one opener contract.
Extend the existing context so it can describe one authoritative selected target
and optional source facts. Prefer a single `JobResultContext` if renaming is
useful; do not add separate job, Asset, transformation, and runtime contexts.
There is no requirement to preserve legacy custom-opener implementation details
in this 0.x redesign, but avoid unrelated contract changes.

The context must support the receiving client configuration, selected value or
Asset, effective location and format, requested return type, reader options,
and optional job/output/process/schema facts. An Asset obtained independently
has no mandatory producing-job information. Do not fabricate a job or a
`JobResults` entry to open it. A small private normalization helper is acceptable;
ordinary callers must not construct another selected-target model.

Baseline integration points:

- [Opener and dispatch](https://github.com/eo-tools/eozilla/blob/7c06deaee8d95225bb9b90e9c7f55853a883a4ed/cuiman/src/cuiman/api/opener/opener.py)
- [Opener context](https://github.com/eo-tools/eozilla/blob/7c06deaee8d95225bb9b90e9c7f55853a883a4ed/cuiman/src/cuiman/api/opener/context.py)
- [Client methods](https://github.com/eo-tools/eozilla/blob/7c06deaee8d95225bb9b90e9c7f55853a883a4ed/cuiman/src/cuiman/api/client_mixin.py)
- [Client configuration](https://github.com/eo-tools/eozilla/blob/7c06deaee8d95225bb9b90e9c7f55853a883a4ed/cuiman/src/cuiman/api/config.py)

## 3. Preserve original outputs and overload one client method

`get_job_results(job_id)` continues to return the original `JobResults` mapping.
Preserve names and values, including Links, qualified values, inline objects,
arrays, scalars, and null. Parsing and transformation create independent objects;
neither may replace original outputs, promote Asset keys into that mapping, or
combine unrelated outputs into a synthetic STAC container.

Add equivalent typing overloads to `Client` and `AsyncClient`:

| First argument | Behavior | Other arguments |
| --- | --- | --- |
| `str` | Identify a job, wait for success, retrieve results, select an original output, and dispatch an opener. | Existing job options plus `data_type`, `media_type`, and reader options. |
| `pystac.Asset` | Open exactly the supplied Asset through the receiving client's configured readers. | `data_type`, `media_type`, and reader options. |

Name the first parameter `job_id_or_asset`, preserving positional calls and
supporting `open_job_result(job_id_or_asset="123")`. Strings always identify jobs, even when they
look like URLs. Other unsupported argument types raise `TypeError`; native
Items/Collections are returned values, not additional opening overloads.

The job form retains polling, timeout, status errors for failure/dismissal, and
processing API errors. Without `output_name`, a single output can be selected
automatically; multiple outputs require explicit selection. Do not silently
prefer `return_value` over other outputs. A missing output or ambiguity must
produce a clear error before invoking a reader. Explicit null remains a valid
selected output, distinct from an absent output.

The Asset form performs no job lookup, polling, process-description lookup,
STAC rediscovery, transformation, or sibling selection. An Asset obtained from
another client or directly from PySTAC is equally valid. Use the receiving
client's configuration and access policy. Neither a private client association
nor provenance can authorize access.

`output_name`, `poll_interval`, and `timeout` are job-only arguments. Exclude them
from the Asset typing overload and reject them at runtime before I/O or dispatch
when explicitly supplied, including explicit defaults or `None`. Use omitted-
argument handling internally to distinguish omission from explicit values.
Asset read/metadata time limits belong to configured access policy, not these
job-polling arguments.

The Asset's own location, format, and metadata are authoritative. Never use its
owner's GeoJSON format or producing output's schema as the selected data format.
Preserve media-type parameters. A call-level `media_type` override affects
opening without mutating the Asset. Suffix detection ignores URL query strings;
supported native paths and file URIs must work on Windows, including spaces.

## 4. Native STAC opening and optional dependency

`StacJobResultOpener` is usable only when `pystac` is installed. Register it as a
built-in optional opener without importing PySTAC during ordinary Cuiman import.
Provide an optional installation extra, tentatively `cuiman[stac]`; keep ordinary
readers usable without PySTAC. Do not add `pystac-client`, `xpystac`, or another
STAC/data integration dependency as part of this proposal.

Return the appropriate native object:

| Selected STAC representation | Returned object | Initial work |
| --- | --- | --- |
| Item | `pystac.Item` | Parse the Item and its embedded Asset metadata. |
| ItemCollection | `pystac.ItemCollection` | Parse embedded Items and retain additional document fields. |
| Collection | `pystac.Collection` | Parse dataset metadata, navigation links, and concrete Collection Assets. |
| Catalog | `pystac.Catalog` | Parse container metadata and navigation links. |

These are PySTAC objects, not a new Cuiman dataclass. ItemCollection is separate
from `STACObject`; handle its parsing explicitly rather than assume that the
generic STAC-object reader covers it. Consult the supported PySTAC version's
[API](https://pystac.readthedocs.io/en/stable/api/pystac.html) and
[ItemCollection contract](https://pystac.readthedocs.io/en/stable/api/item_collection.html).

Concrete Collection Assets are openable. Collection `item_assets` definitions
describe possible Item Assets and must not be mistaken for concrete targets.
Keep unknown extension fields available through PySTAC. Core parsing must work
without xarray, GeoPandas, pandas, or image libraries. PySTAC metadata support
does not itself read a Zarr array, a COG, or a whole datacube.

Prefer process output schema evidence when available, then structural evidence
and supported media-type hints. Recognize inline and qualified STAC values and
linked metadata, including raw dictionaries produced by deserialization. Generic
GeoJSON/JSON must not be assumed to be STAC. Do not require project-specific
process IDs, output names, Asset keys, hostnames, or proprietary link relations.
Schema lookup failure must not prevent structurally recognizable STAC opening.
Schema evidence is a hint, not proof that the returned document matches it.

Acceptance checks must respect `data_type` and perform no network, Asset access,
credential acquisition, or transformation. A linked JSON/GeoJSON value may be a
STAC candidate; metadata reading and definitive parsing happen during opening.
Ordinary JSON/GeoJSON must remain eligible for appropriate existing readers.
If strong STAC evidence or an explicit PySTAC return type applies, malformed
metadata must yield a clear STAC opening failure rather than silently return an
unrelated representation. Parser failures must remain available in grouped
opening errors when another candidate is tried.

Allow `data_type=pystac.Item`, `pystac.ItemCollection`, `pystac.Collection`, or
`pystac.Catalog` to request the corresponding native result. An incompatible
document must fail rather than be coerced. Because Collection inherits Catalog,
subtype matching needs an explicit tested policy; assignable matching is the
default recommendation. Automatic opening returns the actual supported type.
An explicit STAC request with PySTAC missing must explain the missing dependency.

## 5. Location handling, metadata I/O, and navigation

Initial STAC opening reads only the selected document. It must not follow parent,
root, Collection-member, child, or next-page links automatically, probe Asset
existence, list storage keys, or download data/preview payloads. Use PySTAC's
standard [StacIO](https://pystac.readthedocs.io/en/stable/api/stac_io.html) for
metadata reads and native navigation. Applications may supply a native StacIO
through a runtime client factory; custom metadata access policy belongs to that
implementation. Do not introduce a separate Cuiman fetch/response/document stack.
Acceptance must not introduce a duplicate fetch. Response-size, timeout, and
request-count limits are an optional future extension described in section 9.1.

Resolve linked references from the supplied document URI, preferring an
unambiguous absolute self-document link when available. PySTAC's default I/O does
not expose the effective response URI after redirects. Metadata whose relative
references depend on a changed redirect location must advertise an absolute self
link or use an application I/O implementation that supplies an appropriate base.
Do not claim automatic effective-redirect tracking in the initial implementation.
For inline Items, use an unambiguous absolute self link or an explicitly known
containing result-document base. If the transport cannot supply that base,
report the limitation instead of guessing after redirects. An embedded Item's
relative references follow its containing ItemCollection unless an explicit,
applicable base is supplied; unrelated self links must not redirect those Assets.
Establish these bases without modifying the original JSON and retain source facts
separately when normalizing the returned objects.

Asset opening must resolve the supplied Asset against its owner when needed.
PySTAC provides [Asset.get_absolute_href()](https://pystac.readthedocs.io/en/stable/api/asset.html#pystac.asset.Asset.get_absolute_href)
for this purpose. Missing owner/base
information for a relative Asset must produce a clear error rather than reuse
the processing service URL. Preserve signed URLs and their query parameters;
do not refresh them by retrieving or selecting a different Asset.

Returned objects use normal PySTAC navigation. Remote navigation is an explicit
user action and may perform synchronous I/O, including on objects returned by
`AsyncClient`. Initial async opening must not block the event loop with synchronous
network/file reads: run synchronous PySTAC reads off the event loop. Cancellation
of the awaiting task propagates; an already running worker read may continue
until PySTAC completes it. Do not
promise asynchronous PySTAC navigation or automatic STAC API pagination/search.
Retain advertised next-page information without claiming all Items are loaded.

A per-object/per-client I/O policy must be retained for subsequently resolved
links when Cuiman supplies one. Avoid changing PySTAC's global default I/O to
configure one client. Direct navigation outside a Cuiman operation has its own
PySTAC/application policy; the initial implementation adds no metadata budgets.
Transformations of subsequently fetched objects are discussed
explicitly in section 6 rather than implied by initial opening.

## 6. Required STAC transformation

Applications must be able to reuse the built-in STAC opener and transform its
parsed result before it is returned. Transformation is part of the initial
design, not dependent on future uniform listings. Support enrichment, location or
format rewriting, and expansion of configured products into additional native
Assets or embedded Items. The result remains a native supported PySTAC object;
do not introduce transformed-resource wrappers.

Provide an ordered chain of developer-supplied callables with the conceptual
signature `async transform(stac, ctx) -> stac`. A callable receives the parsed
object and the same operation context, including optional process/output facts.
Each subsequent callable receives the preceding result. The composing opener
owns the chain, any process/service acceptance predicate, and its external
configuration. There is no client-wide transformer registry or resolver registry.
External configuration format and acquisition remain application concerns.

Support composition without copying the parser and without requiring inheritance.
A small helper that creates a registerable composed opener class is sufficient;
`compose_stac_opener()` below is an illustrative name/signature. Subclass hooks
can also be supported, using the same parsing and transformation path.

```python
async def add_known_products(stac, ctx):
    # Application logic uses native PySTAC operations on an independent copy.
    # Configuration supplies paths, formats, roles, and product metadata.
    return enrich_from_process_configuration(stac, ctx.process_description)


ProductStacOpener = compose_stac_opener(
    StacJobResultOpener,
    transformers=(add_known_products,),
    accepts=matches_product_process,
)


class ProductClientConfig(ClientConfig):
    extra_job_result_openers = (ProductStacOpener,)
```

The predicate scopes application rules to relevant source facts; the ordinary
built-in handles unrelated STAC outputs. Acceptance runs only the predicate and
base acceptance, not transformation or configuration expansion. Reusing the base
must not parse/fetch metadata twice or apply the same chain recursively. Explicit
caller options cannot load transformer code named by remote metadata.

### Configured folder Assets

For an Item whose `products` Asset points at a folder, external configuration may
declare `rasters/ndvi.tif` and `reports/summary.csv`. Add independent native Assets
to the returned Item while retaining its original folder Asset. For example:

```text
item.assets["products"]                  -> file:///C:/results/products
item.assets["products/rasters/ndvi"]      -> file:///C:/results/products/rasters/ndvi.tif
item.assets["products/reports/summary"]   -> file:///C:/results/products/reports/summary.csv
```

This is a flat native Asset mapping. The slash-separated keys are declared stable
keys, not a new directory-tree API. Set each derived Asset's owner correctly.
Each entry supplies its own title, roles, media type, and optional validated
reader/storage metadata. Retain non-secret derivation metadata identifying the
source Asset key, declared relative path, and configuration identity/revision
when available. Application fields must be namespaced and must not overwrite
standard STAC fields. Neither directory entries nor possible `item_assets`
definitions are automatically readable data Assets.

First resolve the folder Asset relative to the containing STAC document; then
join configured paths using that explicit folder base, even without a trailing
separator. Support native paths, file URIs, and hierarchical storage URIs through
location-aware joining, not string concatenation. Absolute entries retain their
explicit locations and do not inherit credentials or signed query parameters
from the folder. Missing/ambiguous bases and conflicting declared keys must be
reported instead of guessed or overwritten.

Build from declared configuration without directory scans, existence checks,
storage enumeration, Asset credential acquisition, or payload reads. The returned
Assets describe configured products; they do not prove an exhaustive directory
inventory or successful access. The original `JobResults` and source STAC JSON
are unchanged, even though the returned native object intentionally has additional
Assets.

### Ownership, failure, and repeated use

Transform independent copies. PySTAC objects are mutable, so a transformer must
not alter cached parsed sources or earlier returned objects. Copy loaded metadata
and owned Assets safely without following unresolved links. PySTAC `clone()` does
not deep-copy every linked target; blindly using a recursive graph copy is also
unsuitable if it fetches remote objects. The implementation must test these
boundaries explicitly against the supported PySTAC version; see
[STACObject copying](https://pystac.readthedocs.io/en/stable/api/stac_object.html#pystac.stac_object.STACObject.clone).

Retain unaffected original Assets and successful configured siblings when one
declared entry fails; report a sanitized `ClientWarning` for recoverable failures.
A whole-stage failure must not leak partial mutations into its input. Invalid
return types, lost ownership, or unusable document structure are opening errors.
Do not silently return a differently interpreted document after a required
transformation fails. No generic structured diagnostic model is required yet;
exceptions and warnings must still distinguish parsing, transformation, and data
access failures and avoid credential-bearing exception text.

Transformations are recomputed for each job-output opening. Stable declared keys
and configuration revision prevent duplicates and stale derived products. Changes
of effective URL or credentials must not change product selection. Cached sources,
if used, are untransformed and access-scoped. Opening a selected Asset never
reruns transformations; authorized location renewal must retain that exact target
and its declared relative path.

Initial transformations apply to the document and embedded Items loaded during
the explicit output opening. Native PySTAC navigation does not automatically
invoke Cuiman hooks for subsequently fetched documents. An application requiring
that behavior must supply an explicit composed I/O/opening policy which applies
the same chain once per newly parsed document with appropriate source context.
Such a policy must preserve lazy traversal and must not imply that every remote
Item was produced by the current job. Generic automatic navigation transformation
is a future extension, not an undocumented promise of this hook.

## 7. Extension metadata, reader options, and scoped access

Use PySTAC's extension support to expose EO/datacube/projection/raster/storage
metadata. Cuiman reader adapters translate only understood, versioned metadata
into actual reader arguments. Preserve unknown fields for inspection without
claiming every extension affects opening. Inspection of
[Datacube metadata](https://pystac.readthedocs.io/en/stable/api/extensions/datacube.html)
does not automatically select variables, combine Assets, or assemble a dataset.

The [Xarray Assets adapter](https://pystac.readthedocs.io/en/stable/api/extensions/xarray_assets.html)
exposes `xarray:open_kwargs` and `xarray:storage_options`, but the
[extension is deprecated](https://github.com/stac-extensions/xarray-assets#deprecation-notice).
Support these only as validated compatibility inputs. Prefer applicable portable
metadata, including the [Storage extension](https://github.com/stac-extensions/storage),
for new producer descriptions. Eozilla `x-options` is also an optional validated
compatibility input, not a requirement for STAC support. No new mandatory STAC
extension is introduced.

Effective non-secret options follow this precedence, lowest first:

1. Reader defaults inferred from the selected target's supported format/metadata.
2. Accepted producer hints; standardized, versioned hints take precedence over
   equivalent legacy `x-options` when both are supplied.
3. Receiving-client overrides scoped to the selected target and opener.
4. Explicit caller options.

Only declared option mappings merge by key. Scalars/lists replace; `None` clears
inherited settings. Preserve unrelated backend/storage settings when overriding
chunking. Normalize storage aliases per option layer before applying precedence,
including xarray's `backend_kwargs.storage_options`. Inputs and effective options
must be independent for every candidate; failed readers cannot mutate another's
settings. Effective non-secret settings and their sources should be inspectable
through the shared context without requiring capability models.

Validate remote hints against a reader-specific schema before use. Unsupported
or invalid hints remain in the native metadata and produce sanitized warnings;
they are not passed as unrestricted keyword arguments. Producer suggestions must
not force a reader, bypass `data_type`, import arbitrary code, or authorize a new
credential endpoint.

Separate process API credentials, metadata-host credentials, and Asset-store
credentials. Never forward process tokens to arbitrary STAC/Asset hosts or across
unauthorized redirects. Acquire Asset access only after an opener accepts the
selected Asset and immediately before reading. Missing credentials do not remove
the Asset from its native owning object; reading reports the access error.

Caller-supplied credential sets take precedence over configured providers and
replace credentials atomically, including session tokens. Otherwise use the
configured or ambient access mechanism within its authorized scope. Keep resolved
keys/tokens/sessions/providers outside PySTAC fields and serialization. Producer-
supplied signed hrefs remain locations; do not copy their secrets into derivation
fields, warnings, or logs. Receiving credentials cannot be authorized by owner
metadata, transformer provenance, or a caller's association with a producing job.

For a selected S3 Zarr Asset, the effective reader call may be:

```python
xr.open_dataset(
    asset_href,
    engine="zarr",
    chunks="auto",
    backend_kwargs={
        "consolidated": True,
        "storage_options": runtime_storage_options,
    },
)
```

This illustrates the reader boundary, not code executed during STAC parsing or
transformation. Cuiman retains existing data readers rather than introducing a
STAC-specific implementation of each reader.

## 8. Required operations and applicable earlier requirements

| Earlier requirement | Treatment in this design |
| --- | --- |
| R1: inspect all original outputs | Keep `get_job_results()` and existing raw-output inspection, with no STAC reads. |
| R2: inspect/select Items | Open the selected output as native Item/ItemCollection/Collection/Catalog and use PySTAC. Preserve lazy navigation; do not promise automatic pagination. |
| R3: inspect Assets, titles, roles, format, and reader availability | Native Asset mappings expose keys/titles/roles/media types now. Uniform tables and non-reading availability assessment are retained as a future extension, not properties injected into PySTAC. |
| R4: target-specific hints/access/caller overrides | Required now, using validated STAC metadata and runtime reader/access configuration. |
| R5: arbitrary values use unified discovery | Preserve raw values and custom opening now; generic discovery/listing is a future extension. Never manufacture STAC for ordinary values. |
| R6: reuse parsing with transformation and configured folder products | Required now through composed STAC openers and native-object transformation. Generic non-STAC transformation is deferred. |
| P1: previews independently of opening | Future optional enhancement; never fetch preview payloads merely to inspect metadata. |
| Python/CLI/App consistency | Preserve the raw OGC contract now. Uniform presentation/action adapters are future extensions with explicit runtime boundaries. |

The ordinary user only needs the client and PySTAC's native API. Developer
composition, contexts, and access policy remain extension/configuration concerns.
Use Asset keys within the selected owner rather than invent opaque resource IDs.
Repeated `data` keys in different Items are naturally disambiguated by selecting
the Item first. PySTAC's missing-key/navigation behavior should remain familiar.

## 9. Optional future extensions

### 9.1. Bounded metadata I/O

An optional future extension may address a **2 MiB response limit**, a
**10-second per-fetch timeout**, and **at most 16 metadata requests per Cuiman
opening operation**, including redirects. These are proposed configurable Cuiman
policy defaults, not STAC requirements or mandatory initial behavior.

If implemented, enforce byte/time bounds during reads rather than after buffering,
share reads within one operation, and report exceeded limits as opening errors.
Never silently truncate a native ItemCollection. Keep any bounded I/O policy
compatible with native PySTAC StacIO, per-client customization, async cancellation,
and existing parsing/navigation. Effective redirect tracking and explicit scoped
redirect credentials can be addressed with that optional transport policy.
Native navigation should have an explicit budget lifetime; an initial-opening
budget must not be presented as a whole-catalog crawl guarantee. Metadata limits
must not be confused with Asset payload reader limits.

### 9.2. Uniform inspection and diagnostics

Replacing the generic resource API loses one uniform listing and diagnostic
presentation across STAC and arbitrary outputs. Retain that capability as an
explicit future option, layered over this opening contract when real consumers
need it. It is not a prerequisite for the initial Python implementation.

A future adapter could present raw outputs, native STAC objects/Assets, and
application-defined non-STAC targets through consistent notebook, CLI, and App
views. Keep the native `open_job_result(job_id | Asset)` workflow available;
do not replace PySTAC objects with mandatory wrappers to obtain presentation.
Asset rows should show owner/output context, key/title fallback, all roles,
full media type, and optional additional datatype metadata. Missing metadata is
unspecified rather than guessed; unsupported Assets remain visible.

Reuse `is_usable()` and acceptance to assess every configured reader without
payload reads or Asset credential acquisition. Distinguish available (candidate
exists), unavailable (completed check found none), and unknown (pending/failed
assessment), with candidate identifiers and sanitized reasons scoped to runtime,
requested return type, and configuration. Assess transformed targets; refresh
after relevant configuration changes. Keep preview assessment independent.
Do not store environment-specific capability snapshots in STAC `extra_fields`.

Optional structured diagnostics should distinguish empty, unsupported, failed,
partial, and deferred views while preserving raw outputs and successful siblings.
Portable presentation data must exclude sessions, credential providers, and
resolved credentials. Rendering/selection of loaded metadata must perform no
network or payload I/O and must escape untrusted titles/descriptions. Paginated
views, if added, need explicit bounded loading and context-bound continuation;
native ItemCollection content alone is not proof of exhaustive discovery.

CLI/App adapters can independently expose original outputs, Items, and Assets,
including direct Asset-oriented views when useful. A standalone browser cannot
execute Python openers or PySTAC; it needs browser adapters or an explicitly
advertised Python companion service. Define result display/export and credential
scope before promising Python-backed actions. Existing processing proxies must
not be assumed to proxy arbitrary metadata or Asset URLs. Changes to the actual
browser app must update its relevant architecture/usage documentation.

Preview, if added, is an explicit bounded action with cancellation and failure
feedback. An Item thumbnail must not be presented as the preview of an unrelated
Asset. Failure or absence of preview must not block inspection or opening.
General non-STAC transformation and automatic transformation during native remote
navigation can be considered separately without recreating the entire former
resource/resolver architecture in the initial work.

## 10. Acceptance criteria

1. Original results containing a STAC output, ordinary file Link, and inline/null
   values retain their mapping before and after opening/transformation.
2. Inline, qualified, and linked STAC representations return the correct native
   PySTAC types. Plain JSON/GeoJSON remains distinguishable; schema lookup failure
   permits structural recognition. Misleading schema evidence fails clearly.
3. PySTAC is optional at import/runtime. Without it, ordinary readers still work;
   an explicit STAC request reports a missing dependency. Requested return types
   are respected, including the agreed Catalog/Collection subtype policy.
4. STAC opening reads only the selected document through PySTAC I/O and no Asset
   payload, preview, parent, child, next page, or directory inventory. Document
   URLs, absolute self links, and embedded Item bases resolve relative Assets
   correctly. Default-I/O redirect-base limitations are documented; metadata
   byte/time/request limits are deferred to optional section 9.1.
5. Both client variants retain job calls and polling/error behavior. Multi-output
   selection is explicit. Unsupported target types and explicitly supplied
   job-only arguments with Assets fail before I/O.
6. Independently created Assets open through the same configured readers without
   job lookup, rediscovery, transformation, or sibling selection. Relative Assets
   without a resolvable owner/base fail clearly; Windows paths/file URIs work.
7. A process-scoped composed opener reuses base acceptance/parsing and an ordered
   callable chain. Application registration is isolated and unrelated STAC
   outputs use the ordinary built-in. Acceptance never runs transformations.
8. Configured folder products become owned native Assets with stable distinct
   keys, absolute locations, individual formats/roles/hints, and non-secret
   derivation metadata. Folder bases without trailing slashes and absolute
   configured entries work without scans or implicit credential inheritance.
9. Transformation preserves raw JSON, cached sources, and previously returned
   objects, including loaded owner/link relationships. Copying must not follow
   remote links. Recoverable entry failures preserve source/sibling Assets and
   warn; invalid transformed results fail rather than silently bypass rules.
10. Reopening with changed configuration recomputes transformation without
    duplicate Assets. Opening a selected derived Asset does not rerun it.
    Subsequent native navigation has the explicitly documented hook/I/O behavior.
11. Reader-option tests cover validated standardized/legacy hints, scoped client
    overrides, caller precedence, mapping merges, clearing, storage aliases,
    candidate isolation, and atomic credential replacement.
12. Authenticated S3 Zarr opening uses effective reader settings and scoped runtime
    credentials; parsing/transforming acquires no Asset credentials. Tokens,
    keys, and credential-bearing exception text do not enter returned metadata,
    warnings, logs, or reader summaries.
13. Synchronous PySTAC metadata reads run off the async event loop; cancellation
    of the await propagates, with the worker-read limitation documented. Native
    synchronous navigation is documented. Cuiman does not change global PySTAC
    I/O to configure a client.
14. Executable testing-service examples and a notebook demonstrate inline and
    linked outputs, Item selection, Asset opening, transformation, and cleanup.
    The new branch must add its own representative test processes/fixtures if
    they are absent from main rather than depend on the previous feature branch.

## 11. Implementation sequence and review

Implement on a new branch from main using this document alone. Inspect the
baseline and relevant Cuiman coverage before edits, preserve unrelated working-
tree changes, and stop after each step for review and comments.

1. Add one or two representative testing processes/fixtures for inline Item and
   linked ItemCollection outputs with real small products and relative locations.
2. Add optional PySTAC packaging and `StacJobResultOpener`, standard PySTAC I/O/base
   handling, and sync/async job-output tests. Confirm conservative recognition
   and no payload/crawl behavior.
3. Add the Asset overload, minimal shared-context adaptation, reader metadata/
   option/access handling, and tests of exact-target and argument semantics.
4. Add composed STAC transformation and declared-folder examples with isolation,
   ownership, failure, repeated-opening, and no-I/O transformation tests.
5. Update the opener guide, API/customization docs, maintained examples, a testing-
   service notebook, and `CHANGES.md` to describe the implemented scope. Keep
   uniform presentation and diagnostics clearly labeled as future work.

Follow AGENTS.md and Pixi tooling; use relative implementation imports, deferred
optional imports and `TYPE_CHECKING` where appropriate, Black-style formatting,
and private helpers at the end of Python files where feasible. Public classes,
functions, constants, aliases, and dataclass attributes need docstrings explaining
their purpose as well as their individual behavior. Keep touched-code coverage
close to 100%; use appropriate package tests/checks and a strict docs build.
Resolve routine implementation details autonomously and flag substantive gaps.

## 12. Substantive boundaries to verify during implementation

- **Document bases:** inspect whether the main transport exposes the effective
  result-document URI. If not, a minimal transport/context adjustment is needed
  for redirected inline results with relative references; do not invent a base.
- **Extension support:** choose and test a supported PySTAC version range and
  explicit reader-adapter extension versions. PySTAC's ability to preserve or
  expose a field does not guarantee Cuiman can use it to open data.
- **Transformation beyond the initial document:** initial embedded objects are
  covered; automatic hooks during later native navigation require an explicit
  per-object I/O policy. Do not claim that behavior until it is implemented and
  tested, or expand every linked document eagerly to obtain it.
- **Generic inspection:** uniform availability/diagnostic presentation is
  intentionally deferred in section 9. Its eventual surface and CLI/App execution
  strategy require a separate design decision, while transformation is required
  by this initial specification.
