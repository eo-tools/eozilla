# PySTAC job-result openers: implementation plan

Status: Steps 1–4 approved. Step 5 implemented and verified;
awaiting user review. Step 6 remains optional and unstarted.

This plan implements [PySTAC Job Results and Asset Opening](pystac-job-result-openers.md).
That document remains the behavioral specification, subject to the user-approved
branch and scope adjustments recorded here. This plan divides the work into
independently reviewable steps, with runnable testing processes developed
alongside the STAC opener. Steps 1-5 are mandatory; Step 6 is an optional extension.

## Iteration and review

- Implement exactly one step at a time.
- After each step, report the changes, relevant validation, remaining limitations,
  and any substantive decisions needed.
- Stop and wait for user review. Do not start the next step until authorized.
- Apply requested adjustments to the current step and pause again for review.
- Resolve routine implementation details within the agreed scope autonomously.
- Update essential API/configuration documentation, limitations, and CHANGES.md
  alongside each mandatory step. Run relevant tests and inspect touched-code
  coverage in that step; documentation and verification do not wait for Step 6.

Design approval and implementation are separate checkpoints. Writing this plan
does not begin implementation.

## Preparation before Step 1

The checkout inspected on 2026-10-08 is `forman/217-cuiman_stac_openers` at
`0544abc25a0fb48482058a86e6bdf250317783f9`. Local `main` is
`7c06deaee8d95225bb9b90e9c7f55853a883a4ed`; the current branch adds the initial
specification commit. Recheck these facts before implementation.

At the start of Step 1, the current task branch was verified at
`b786d2660c42160f15e90d2bbf136dc9cc9b5ded`. Implementation remains on that branch.

Use the existing task branch `forman/217-cuiman_stac_openers` for all implementation
steps. Do not create or switch branches. This user instruction overrides the
specification's instruction to create a new branch from `main`. Retain the
specification and this plan, and preserve unrelated working-tree content,
including the nested `eozilla-app/` checkout. Inspect the actual current-branch
baseline; do not assume implementation or a Procodile schema-reference fix from
another feature branch is present.

Inspect applicable repository guidance and the relevant existing tests. Before
changing Cuiman, measure the relevant baseline coverage using Pixi tooling.
Preparation belongs to the first implementation iteration; it is not a separate
feature step.

## Step 1: one selected-target context and explicit output selection

Adapt the existing opener context rather than introduce multiple public target or
runtime models. It must hold one authoritative selected value, effective location
and format, receiving client configuration, requested return type, reader options,
and optional job/output/process/schema facts. An independent Asset must eventually
fit this context without fabricated job information.

Select the original job output before dispatch. Automatically select only a sole
output; multiple outputs require `output_name`. Distinguish an absent output from
an explicitly selected null. Remove the implicit `return_value` preference.
Preserve the original mapping and values without mutation.

Adapt existing readers to the shared contract while retaining ordered dispatch,
configuration-class isolation, later registration precedence, and idempotent
unregistration. Keep unrelated custom-opener contract changes out of scope.

**Validation:** context/selection cases, raw-output preservation, existing reader
and registry tests, and both clients' polling, timeout, failure/dismissal, and API
error behavior. Run the relevant Cuiman tests and inspect touched-code coverage.

Use small in-memory fixtures to validate this step; the runnable testing-service
processes are added in Step 2.

**Documentation:** update the context/custom-opener contract and explicit output
selection rules, including the removal of the `return_value` preference.

**Pause:** review the shared context and selection behavior.

### Step 1 implementation record

- Kept the public name `JobResultOpenContext`. Added authoritative `value` and
  effective `location`, with optional producing-job facts. Existing
  `output_value`, Link/qualified-value helpers, and media-type overrides remain
  available for readers.
- Job outputs are selected and copied during context construction. Missing,
  empty, and ambiguous results fail clearly; explicit null and empty-string output
  names are valid selections. Process descriptions use the selected output's name.
- Both clients validate selection before optional schema lookup and dispatch.
  Path readers use the context's effective location. Polling/status/API errors and
  registration behavior remain covered by the existing and extended tests.
- Updated public docstrings, the opener/customization guides, and CHANGES.md.
- Baseline: 68 relevant tests passed, with 100% opener-module coverage.
- Final verification: 727 Cuiman tests passed; Cuiman and maintained guide examples
  have 100% statement coverage. Ruff lint/format checks, Mypy over 48 Cuiman source
  files, and the strict MkDocs build passed.
- Environment workaround: normal Pixi initialization could not use its cache;
  final tests/type/docs commands used `pixi run --as-is` with the explicit existing
  Pixi Python interpreter. Test temporary files, coverage output, and generated
  docs were isolated under `.pixi/step1/`.

## Step 2: testing processes, native STAC opening, and PySTAC metadata I/O

### Testing processes

#### Deliverables

Add two processes to `wraptile.services.local.testing`, with proposed IDs
`create_inline_stac` and `create_linked_stac`:

1. **Inline STAC outputs:** return STAC JSON directly in named job outputs.
   Start with an Item and an ItemCollection containing multiple Items. Provide
   explicit output descriptions/schema hints and keep the actual values in the
   original `JobResults` mapping.
2. **Linked STAC outputs:** write corresponding STAC metadata documents and
   return ordinary `gavicore.models.Link` outputs pointing to those documents,
   with appropriate media types. Include relative Asset locations and embedded
   Items to exercise containing-document base resolution.

Use shared private builders so both processes describe equivalent small,
deterministic products. Give Items stable IDs, geometry/bounds, temporal metadata,
and native Asset metadata such as titles, roles, and individual media types.
Include a small readable dataset and a simple report. Repeated Asset keys across
Items should demonstrate that selection is scoped to an owner.

Keep producer-side metadata generation independent of the future Cuiman opener.
Avoid introducing a mandatory PySTAC dependency for the testing service. Reuse
existing optional data-generation dependencies where suitable. Provide bounded
inputs/defaults and explicit output-location and cleanup behavior.

#### Browser usability

Linked documents must be reachable over HTTP for `eozilla-app` testing;
`file:///` and in-process `memory://` links alone do not satisfy this goal.
The inspected local service has no existing artifact-serving route. Establish a
minimal development/test serving arrangement for generated metadata and products,
with a known public base URL and suitable browser access. Keep any serving change
limited to the testing setup and its declared artifact directory. Document how
to run it and clean up its output.

This step supplies raw API outputs and reachable documents for manual app testing.
It does not require new browser STAC presentation or Python-backed app actions.

#### Process validation

- Test process registration, descriptions, execution, and original output shapes.
- Confirm inline outputs survive JSON serialization and linked outputs are Links.
- Fetch linked documents through the testing HTTP setup and resolve their relative
  Assets to the intended products.
- Verify deterministic product contents and Windows path handling where relevant.
- Verify repeat runs and cleanup; update the existing process-list expectations.
- Run `pixi run test-wraptile` and relevant Procodile tests if its behavior changes.
- Supply example execution requests and representative results for manual review.

### Native opening and transport

Add the optional `cuiman[stac]` extra and built-in `StacJobResultOpener`, following
the existing optional-wrapper/concrete-implementation pattern. Ordinary Cuiman
imports must not import PySTAC. Verify a supported PySTAC version range against
its actual parsing, ownership, copying, and I/O behavior.

Return native Item, ItemCollection, Collection, or Catalog objects. Parse
ItemCollection explicitly and retain additional fields, unknown extensions,
concrete Collection Assets, navigation links, and advertised next-page information.
Keep `item_assets` definitions distinct from concrete Assets.

Recognition uses available schema hints, structural evidence, and supported media
types without treating all JSON/GeoJSON as STAC. Acceptance respects `data_type`
and performs no I/O, credential acquisition, or transformation. Opening handles
definitive parsing. Use assignable requested-type matching, including accepting a
Collection for a Catalog request. Strong STAC evidence, explicit STAC requests,
and malformed metadata must not silently yield unrelated representations; retain
parser failures in grouped errors where fallback is permitted.

Use standard PySTAC StacIO for metadata reads and native navigation, with an
optional native-I/O factory on the receiving client configuration. Read only the
selected metadata document. Cuiman byte/time/request bounds are deferred to the
optional future extension in specification section 9.1, outside Steps 1–6.

Establish document-URL/self-link bases for inline, linked, and embedded objects
without changing source JSON. Document that default PySTAC I/O does not expose
effective redirected metadata URLs; absolute self links or application I/O are
needed when relative references depend on a changed redirect base. Make the
minimal transport/context adjustment needed to retain a result-document base;
report unavailable or ambiguous bases instead of guessing. Keep process and
metadata credentials separate; an application's native I/O owns custom access.

Initial async metadata I/O must not block the event loop, and cancellation must
propagate to the await; an already running synchronous worker read may continue.
Retain per-object/client navigation policy without changing global
PySTAC I/O. Later native navigation remains an explicit synchronous user action.

**Validation:** all four native types, inline/qualified/linked and raw-dictionary
forms, misleading/missing schema hints, missing PySTAC, requested types, standard
file/HTTP reads, self-link and embedded bases, cancellation, policy isolation, and proof of
no Asset/preview reads or parent/child/member/next-page traversal.

**Documentation:** describe optional installation, supported native types and
PySTAC versions, standard metadata I/O and customization, document-base failures,
and synchronous native navigation from both clients. Include runnable testing
process requests, the HTTP setup, and cleanup instructions.

**Pause:** review both processes, product layout, browser accessibility, native
opening, dependency behavior, and transport policy together.

### Step 2 implementation record

The original bounded-transport implementation below was superseded during Step 3
review by the standard PySTAC I/O simplification recorded there. Its verification
results describe that earlier implementation, not current metadata-limit behavior.

- Added `create_inline_stac` and `create_linked_stac` to the existing testing
  registry. Both produce equivalent Item/ItemCollection metadata, real 2×2 Zarr
  grids and CSV reports, and ordinary Link,
  integer, and null outputs. Counts are bounded to 1–4 before generation; each run
  has a separate directory with stable Item IDs and Asset keys.
- The testing service mounts its configured artifact directory at `/testing-stac`.
  Default output is `.pixi/testing-stac`, advertised at
  `http://localhost:8008/testing-stac`. Environment overrides, browser access,
  execution requests, representative outputs, and explicit cleanup are documented
  in the Wraptile usage guide. Restart an existing testing server to expose the
  new registered processes and HTTP mount.
- Added optional `cuiman[stac]` with verified PySTAC `>=1.15.2,<1.16`, plus the Pixi
  development dependency and lock update. The built-in optional wrapper preserves
  deferred imports and registration precedence. Native Item, ItemCollection,
  Collection, and Catalog parsing preserves unknown fields and concrete Asset
  ownership without following remote links. Collection satisfies a Catalog
  request; incompatible native requests and required STAC failures are terminal.
- Added bounded `StacMetadataIO`, configurable limits and a runtime application
  factory. HTTP streams and off-thread local files use independent operation
  budgets/caches; cancellation propagates. Explicit origin headers remain separate
  from process authentication, and redirects do not inherit credentials or cookies.
  Each returned object's read-only PySTAC I/O retains the application policy for
  explicit synchronous navigation without changing PySTAC's global default.
- Retained effective job-result response URIs per exact result object using weak
  references, with an optional custom-transport hook. Inline metadata prefers its
  absolute self URI; embedded Items use their containing ItemCollection. Normalized
  native references leave original results untouched and reject missing bases.
- Baseline: 136 targeted Cuiman tests and 11 testing-service tests passed. Final:
  788 Cuiman tests, 129 Wraptile tests (4 existing skips), and 154 Procodile tests
  passed. Cuiman, maintained guide examples, and Wraptile have 100% statement
  coverage. Package Ruff lint/format checks, Mypy over 72 source files, the strict
  documentation build, and `git diff --check` passed.
- An independent temporary localhost server exercised both real processes with
  both clients: native Item/ItemCollection opening, original outputs including
  null, reachable relative products, and ordinary CSV opening passed. Only the
  temporary test server was stopped; the existing user server was preserved.
- Environment: the Pixi dependency update encountered a locked running
  `wraptile.exe`. The manifest/lock update used `pixi add --no-install`; interrupted
  editable-package registrations were restored without stopping that server.
  Checks used `pixi run --as-is` with the explicit Pixi interpreter. QA outputs
  remain isolated under `.pixi/step2/`; Procodile temporary files were confined
  there after Windows denied writes in its default external temporary directory.
- Updated essential opener/configuration/testing-service documentation and
  CHANGES.md. Asset overloads, Asset reader/access hints, transformations, and
  the optional notebook remain in their later approved steps.

## Step 3: exact-Asset overload for both clients

Add equivalent `str` and `pystac.Asset` overloads to Client and AsyncClient,
using the public parameter name `job_id_or_asset` for job and Asset calls. Strings
always identify jobs. Reject unsupported target types.

Use omitted-argument handling to reject explicitly supplied `output_name`,
`poll_interval`, and `timeout` with an Asset, including explicit defaults or None,
before I/O or dispatch. Asset calls perform no job lookup, polling, process lookup,
metadata rediscovery, sibling selection, or transformation.

Resolve exactly the supplied Asset using its own href, media type, metadata, and
owner/base. Use the receiving client's readers and policies for independently
created and foreign-client Assets. Preserve media-type parameters and signed URL
queries; call-level media-type overrides must not mutate the Asset. Handle native
Windows paths, file URIs, spaces, and query-independent suffix detection.

**Validation:** argument semantics and no-I/O rejection, independent and derived
Assets, owner/base resolution and clear failures, authoritative Asset formats,
both client variants, and the Step 2 metadata-to-Asset workflow.

**Documentation:** document both overloads, rejected Asset arguments, location
resolution, and a minimal runnable metadata-to-Asset example.

**Pause:** review the public two-stage workflow and exact-target semantics.

### Step 3 implementation record

- Added equivalent job-ID and native Asset overloads to Client and AsyncClient,
  keeping `job_id` keyword calls and existing job polling/selection behavior.
  Omission sentinels reject explicit job-only arguments, including None and exact
  defaults, before href resolution or reader dispatch. Unsupported targets fail
  with TypeError, and ordinary Cuiman imports still do not load PySTAC.
- Asset opening retains the exact native object, uses the receiving client's
  registry/configuration, and dispatches without job/process/result API calls,
  metadata rediscovery, or sibling selection. Closed-client and async event-loop
  ownership checks apply to Asset calls too.
- Shared location handling resolves relative hrefs from the owner's absolute
  document base, including Collection Assets and storage URIs. Missing bases and
  non-absolute URI forms fail clearly. Windows paths, PySTAC's normalized
  `file:C:/...` forms, escaped spaces, and signed queries are covered. Built-in
  path readers use Asset MIME essence for matching while retaining parameters in
  the context, honor explicit format overrides without mutation, and ignore query
  strings/fragments during suffix detection.
- Baseline: 182 targeted tests passed with 100% opener-module coverage. Final:
  865 Cuiman tests and 19 subtests passed with 100% statement coverage across
  Cuiman and maintained guide examples. Ruff lint/format checks, Mypy over 53
  Cuiman source files, the strict docs build, and `git diff --check` passed.
- Both real testing processes were exercised through a separate temporary HTTP
  server with both clients: native metadata opening, exact CSV Asset reading,
  and preservation of raw outputs passed. Unit workflows also read real generated
  Zarr products after selecting an Asset from either process's native metadata.
  HTTP Zarr requires the reader's optional `fsspec[http]`/aiohttp dependencies,
  absent from the current Pixi environment. The runnable guide uses CSV and
  documents that requirement; the environment was not changed in this step.
- Updated essential API docstrings, the two-stage guide/example, guide tests, and
  CHANGES.md. Checks used the existing Pixi interpreter via `pixi run --as-is`,
  with QA outputs isolated under `.pixi/step3/`. Step 4 reader hints and scoped
  Asset access, Step 5 transformations, and the optional notebook remain pending.
- Review adjustment: grouped the Asset/context helpers, href resolution, metadata
  transport, recognition, and native parser under `opener.impl._stac`. The optional
  `StacJobResultOpener` wrapper stays in `impl/openers.py` alongside the other
  optional wrappers, as requested during review. Like those wrappers, it only
  declares its required module and creates its concrete implementation. Shared
  optional-opener handling delegates missing-PySTAC diagnostics to STAC support.
  Public imports remain unchanged. Asset recognition stays in STAC helpers;
  the shared context does not import STAC implementations. STAC's public error remains alongside
  shared opener errors because it participates in common dispatch.
  Reorganization verification: 259 targeted tests passed with 100% statement
  coverage across the opener package; all 865 Cuiman tests and 19 subtests passed.
  Ruff lint/format checks, Mypy over 55 source files, the strict docs build, and
  `git diff --check` also passed.
  Subsequent wrapper review: 259 targeted tests passed with 100% opener coverage;
  lint, formatting, Mypy over 54 source files, and diff checks passed. This test
  run supplied workspace source paths through a command-local PYTHONPATH because
  the existing environment's editable imports were unavailable; it did not modify
  the environment.
- Context review: removed STAC metadata I/O and native Asset recognition from
  `JobResultOpenContext`. Asset entry points normalize effective location/media
  type into shared facts, preserving the exact selected value and format override
  behavior. Metadata I/O belongs to the STAC opener instance. The original fresh
  request budgets and caches were subsequently removed in the simplification
  recorded below. Returned native objects retain their own navigation policy. No context
  subclass or generic extension-state API was needed. Tests configure transport
  through the existing client factory instead of adding private context fields.
  Verification: 299 targeted opener/client/guide tests passed with 100% opener
  statement coverage, including fresh metadata on repeated openings. Lint,
  formatting, Mypy over 54 source files, strict documentation, and diff checks
  passed. Documentation required permission to read existing Pixi registration
  files; the environment was not modified.

- Metadata I/O review: replaced Cuiman's bounded transport and PySTAC adapter with
  standard native `StacIO`. Removed the custom transport export and limit settings;
  applications can use a runtime-only `ClientConfig.stac_io_factory`. Every opening
  obtains an I/O instance, which returned native objects retain for navigation.
  Initial synchronous metadata reads run in a worker thread; cancellation ends the
  await but may leave an already running read active. Default PySTAC I/O does not
  expose a redirected response URL, so bases use the supplied URI or absolute self
  link. These limitations are documented in the spec and guide.
  Specification section 9.1 now defers a 2 MiB response limit, a 10-second per-fetch
  timeout, and at most 16 metadata requests to an optional future extension outside
  Steps 1–6. This review supersedes earlier bounded-transport behavior records.
  Verification: 376 focused opener/client/configuration/guide tests and one subtest
  passed, with 100% opener statement coverage. The package regression passed 848
  tests and 19 subtests; its two failures passed subsequent checks after updating
  the guide and granting read access to installed package metadata for the CLI
  version check. Ruff lint/format checks, Mypy over 53 source files, strict docs,
  and live HTTP workflows for both testing processes and both clients passed.

- Path-helper review: moved generic file-URI/native-path conversion to
  `opener.impl._paths`, shared by ordinary path readers and the STAC opener.
  The helper raises generic `JobResultOpenError` and has no STAC dependency;
  STAC-specific href/base resolution remains in `_stac.locations`.
  Verification: 208 opener/Asset tests passed with 100% coverage of the changed
  implementation modules. Ruff lint and formatting checks passed.

- Parameter-name review: renamed the implementing methods' first parameter to
  `job_id_or_asset` in both mixins, aligned the overloads and documentation, and
  updated keyword-call tests. The job branch narrows this value to a local `job_id`.
  This supersedes the earlier `job_id` keyword-call record. Verification: 117
  client/Asset/STAC tests passed; Ruff lint and formatting checks passed.

- Asset-helper review: moved native Asset recognition to `opener.impl.base` as
  `as_stac_asset()`, with a docstring explaining its optional-import behavior.
  Updated path-reader and STAC callers; the helper still checks only an already
  loaded PySTAC module. Verification: 208 opener/Asset tests passed, including
  optional-dependency import checks; Ruff lint and formatting passed.

- Shared-mixin review: extracted `_new_job_result_context()` and async
  `_open_result_context()` into `ClientMixinBase`. Both clients share context
  construction, result-document URL retention, registry selection, and dispatch
  for job outputs and exact Assets. The synchronous client uses `run_sync` and the
  asynchronous client awaits dispatch. Polling, API calls, sleeps, and event-loop
  binding remain in their respective mixins. Verification: 125 client/Asset/STAC/
  metadata tests passed, covering all extracted helper statements; Ruff lint and
  formatting checks passed.

## Step 4: validated reader options and scoped Asset access

Define the supported reader adapters and extension versions explicitly. Translate
only understood, validated hints, including applicable Storage metadata and
compatibility inputs for deprecated xarray-assets and legacy `x-options`.
Preserve unsupported metadata for inspection and warn without passing unrestricted
remote keyword arguments to readers.

Resolve non-secret options in order: reader defaults, accepted producer hints,
scoped receiving-client overrides, then caller options. Standardized/versioned
hints beat equivalent legacy hints. Merge only declared mappings by key;
scalars/lists replace and None clears. Normalize storage aliases in each layer,
including `backend_kwargs.storage_options`, before applying precedence. Expose
effective non-secret settings and sources through the shared context and isolate
each candidate's mutable options.

Acquire Asset access only after reader acceptance and immediately before reading.
Keep process, metadata-host, and Asset-store credentials separately scoped. Caller
credential sets replace provider credentials atomically, including session tokens.
Keep resolved credentials/providers outside PySTAC fields and serialization.
Sanitize warnings, grouped errors, logs, and reader summaries.

**Validation:** option precedence, version validation, mapping merges, clearing,
alias normalization, candidate isolation, scoped overrides, atomic credential
replacement, and authenticated S3 Zarr reader-boundary tests. Confirm metadata
parsing/transformation never acquires Asset credentials.

**Documentation:** document supported hint versions, option precedence and clearing,
scoped access configuration, credential replacement, and relevant failure behavior.

**Pause:** review reader configuration, supported metadata, and access behavior.

### Step 4 implementation record

- Added validated producer hints for built-in xarray, pandas, geopandas, and
  image adapters, keeping the logic in `opener.impl._stac.reader`. Xarray-assets
  1.0.0 is a compatibility input requiring its exact extension declaration.
  Legacy `x-options` is filtered through reader schemas; pandas CSV hints apply
  only to CSV targets. AWS S3 Storage 1.0.0 and 2.0.0 translate region and
  requester-pays metadata. Version 2 requires one matching, supported scheme;
  custom endpoints, alternate targets, arbitrary engines/code, remote credentials,
  and unsupported/invalid hints are not translated. Native metadata is preserved,
  with sanitized warnings for ignored hints. Supported fields and limits are
  documented in the opener guide and linked from the specification.
- Options resolve as reader defaults, producer hints, receiving-client overrides,
  then caller options. Only declared mappings merge; scalar/list replacement and
  None clearing are supported. Normalize xarray storage/consolidated aliases and
  S3 credential aliases in each layer, including aliases within one call, before
  precedence. Reader attempts copy option containers independently while retaining
  opaque runtime sessions/callables by identity. Shared contexts expose generic
  non-secret `resolved_options` and dotted-path `option_sources`; caller inputs,
  source JSON, and native Asset ownership remain unchanged.
- Added runtime-only `ClientConfig.asset_reader_options` and
  `asset_access_provider` callbacks. Applications scope policy by the exact
  receiving context's effective location and reader name. S3 access is acquired
  only after acceptance, just before reading, with synchronous or async providers
  and ambient fallback. Explicit credentials/access settings or storage clearing
  skip the provider. Replacement credential sets discard previous keys and session
  tokens atomically while retaining unrelated backend options. Process credentials
  and native metadata I/O never supply Asset access; runtime secrets stay outside
  STAC fields, profiles, reader summaries, warnings, and grouped Asset errors.
- Verification: 422 focused opener/client/configuration/guide tests and one subtest
  passed. All 896 Cuiman tests and 19 subtests passed. The new reader resolver has
  99% statement coverage (one defensive validator fallback remains uncovered);
  other touched opener modules and configuration have 100% in the package run.
  Tests exercise both clients and synchronous/async access callbacks at the
  authenticated S3 Zarr reader boundary without external S3 access, as well as
  schema/version rejection, precedence, clearing, mapping and alias handling,
  atomic credentials, candidate isolation, runtime sessions, safe summaries/errors,
  cancellation, and no access acquisition during acceptance or metadata parsing.
  Ruff lint/format checks, Mypy over 55 source files, strict documentation, and
  diff checks passed. Checks use the existing Pixi interpreter and command-local
  workspace source paths; QA outputs are isolated under `.pixi/step4/`. Package
  checks and docs needed read access to existing Pixi registrations/metadata;
  dependencies and the environment were not modified.
- Updated the opener guide, configuration guide, specification support notes,
  and CHANGES.md. Existing payload readers remain synchronous; async credential
  providers may perform asynchronous acquisition. Supported producer adapters
  cover a documented subset of extension fields, not every cloud platform.
  Step 5 transformations and the optional notebook remain pending.

- Naming review: renamed the path-reader policy identifier from `reader_adapter`
  to `asset_reader_id` in the shared base and all four built-in readers, and
  clarified its docstring. Verification: 114 implementation tests passed;
  Ruff lint, formatting, and diff checks passed.

- Argument-name review: use `asset_reader_id` consistently in reader-policy
  function parameters, callback examples, configuration docstrings, and tests.
  Verification: 46 Asset-reader tests passed; Ruff lint and formatting passed.

## Step 5: composed STAC transformation

Provide a small composition helper for registerable STAC opener classes with an
optional source predicate and an ordered chain of async transformation callables.
Reuse base acceptance/parsing once; require neither parser copying nor inheritance.
Keep application configuration owned by the composing application.

Transform independent native objects, including initially embedded Items. Preserve
raw results, source JSON, cached parsed sources, previous returns, and loaded
ownership/link relationships without resolving remote links while copying. Give
each stage isolated input so a failed stage cannot leak partial mutations.

Invalid transformed types, broken ownership,
unusable structure, and whole-stage failures are opening errors that cannot
silently bypass required transformation. Recompute on each job-output opening;
opening a selected Asset never reruns transformations.

Initial hooks cover the opened document and embedded objects. Automatic hooks
during later native remote navigation remain outside this implementation unless
an application supplies an explicit composed I/O policy.

**Validation:** composition/registration isolation, order and predicates, one parse,
copy boundaries and ownership, no unintended metadata or payload reads,
stage failures, repeated use, and exact opening of selected Assets.

**Documentation:** document the composition API, a minimal native-object
transformation example, transformation failure behavior, and the initial-document/navigation
boundary. Keep uniform listing/diagnostics, previews, generic discovery, automatic
pagination, and new browser action adapters explicitly deferred.

### Mandatory completion checks

Before the Step 5 review, exercise the integrated workflow against both Step 2
processes: execute a job, inspect raw outputs, open native STAC metadata, select and
read an Asset, apply a configured transformation, and clean up.
Keep this workflow runnable and understandable without a demo notebook.

Verify acceptance criteria 1-13 and the mandatory portion of criterion 14: runnable
testing processes and minimal executable workflow examples. Expanded maintained
examples and the notebook portion of criterion 14 are deferred by user agreement
to optional Step 6; do not report the original criterion as fully satisfied before
those deliverables exist.

Run the appropriate package tests, `pixi run checks`, `pixi run tests`,
`pixi run coverage`, and `pixi run build-docs` (the existing strict docs build).
Keep touched-code coverage close to 100%. Report baseline failures separately from
new regressions. Review the essential documentation and CHANGES.md updates made
throughout Steps 1-5.

**Pause:** review reusable composition, the native-object example, integrated
verification, essential documentation, and remaining limitations. The mandatory
implementation ends here. Do not start optional Step 6 without user authorization.

### Step 5 implementation record (awaiting review)

- Added `compose_stac_opener()` for client-registered STAC opening with an optional
  source predicate and ordered async transforms. It delegates acceptance and a
  single parse to the base opener, copies each stage input, and treats invalid or
  failed transformations as terminal opening errors with sanitized messages.
- After review, removed the folder-product expansion helper, its dedicated
  integration test and example, and the testing process's unused folder Asset.
  The CSV and Zarr Assets remain directly addressable. Composition retains
  native-type and ownership validation, with a concise configuration example.
- Verification for the revised scope: 902 Cuiman tests and 129 Wraptile tests
  passed; the nine focused composition tests give the retained implementation
  99% statement coverage. `pixi run checks` and the strict docs build passed.
  An earlier Cuiman run had two intermittent Windows Zarr writes fail; both
  cases passed in isolation and the full suite passed on rerun with an isolated
  workspace temp directory. The earlier aggregate coverage task likewise stopped
  on unrelated Windows/Zarr filesystem failures.

## Step 6 (optional): expanded guides, examples, and demo notebook

This extension is useful but is not required to complete the current implementation.
It expands the essential documentation and executable examples delivered in
Steps 1-5.

Expand the opener guide, API/customization walkthroughs, and maintained examples.
Add a demo notebook using both Step 2 processes to show execution, raw outputs,
native STAC inspection, Item selection, Asset reading, transformation, and cleanup.
Add a broader walkthrough of the testing-service/HTTP setup and manual eozilla-app
testing. Preserve the documented scope and navigation/extension limitations.

**Validation:** execute maintained examples and notebook against the testing
service and run the strict docs build and checks relevant to the added artifacts.
Complete the deferred portion of acceptance criterion 14. Repeat implementation
checks only where changes or unresolved concerns justify it.

**Pause:** review the optional guides, expanded examples, notebook, and their
execution evidence.

## Acceptance-criterion coverage

| Specification criterion | Primary steps |
| --- | --- |
| 1: preserve original outputs | 1, 2, 5 |
| 2: native representations and conservative recognition | 2 |
| 3: optional dependency and requested return types | 2 |
| 4: selected metadata opening and document bases | 2 |
| 5: client job behavior and argument validation | 1, 3 |
| 6: independent Assets and location handling | 3 |
| 7: composed opener and predicate isolation | 5 |
| 8: transformed native ownership and links | 5 |
| 9: transformation copying, ownership, and failures | 5 |
| 10: repeated opening and navigation boundary | 2, 5 |
| 11: validated hints and option resolution | 4 |
| 12: scoped S3 access and secret handling | 2, 4, 5 |
| 13: async I/O, cancellation, and per-client policy | 2 |
| 14: testing processes and minimal executable examples (required) | 2, 3, 5 |
| 14: expanded examples and demo notebook (deferred) | 6 (optional) |

All steps follow AGENTS.md, existing Pixi tooling, Black-style formatting,
package-relative implementation imports, deferred optional imports, and public API
docstrings. Generated client changes must follow the repository's generation
workflow rather than edits that regeneration would discard.
