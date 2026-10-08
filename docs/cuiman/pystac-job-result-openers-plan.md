# PySTAC job-result openers: implementation plan

Status: Step 1 implemented and verified; awaiting user review before Step 2.

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

## Step 2: testing processes, native STAC opening, and bounded metadata transport

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
Include a small readable dataset and a simple report, plus a products-folder
Asset for the later configured-expansion example. Repeated Asset keys across
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

Provide configurable scoped metadata I/O, adapting per-object PySTAC StacIO where
appropriate. Default bounds are 2 MiB per document, 10 seconds per fetch, and
16 metadata requests per opening operation. Enforce bounds while reading and share
reads within an operation. Read only the selected metadata document.

Retain effective redirect locations and establish correct containing-document
bases for inline and embedded objects without changing source JSON. Make the
minimal transport/context adjustment needed to retain a result-document base;
report unavailable or ambiguous bases instead of guessing. Keep process and
metadata credentials separate and authorize redirect scopes explicitly.

Initial async metadata I/O must not block the event loop, and cancellation must
propagate. Retain per-object/client navigation policy without changing global
PySTAC I/O. Later native navigation remains an explicit synchronous user action.

**Validation:** all four native types, inline/qualified/linked and raw-dictionary
forms, misleading/missing schema hints, missing PySTAC, requested types, bounded
reads, redirect and embedded bases, cancellation, policy isolation, and proof of
no Asset/preview reads or parent/child/member/next-page traversal.

**Documentation:** describe optional installation, supported native types and
PySTAC versions, metadata limits and access configuration, document-base failures,
and synchronous native navigation from both clients. Include runnable testing
process requests, the HTTP setup, and cleanup instructions.

**Pause:** review both processes, product layout, browser accessibility, native
opening, dependency behavior, and transport policy together.

## Step 3: exact-Asset overload for both clients

Add equivalent `str` and `pystac.Asset` overloads to Client and AsyncClient,
preserving the public parameter name `job_id` and keyword job calls. Strings
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

## Step 5: composed transformation and declared folder products

Provide a small composition helper for registerable STAC opener classes with an
optional source predicate and an ordered chain of async transformation callables.
Reuse base acceptance/parsing once; require neither parser copying nor inheritance.
Keep external product configuration owned by the composing application.

Transform independent native objects, including initially embedded Items. Preserve
raw results, source JSON, cached parsed sources, previous returns, and loaded
ownership/link relationships without resolving remote links while copying. Give
each stage isolated input so a failed stage cannot leak partial mutations.

Use the Step 2 folder Asset to demonstrate declared product expansion. Resolve
the folder first, then join configured paths with location-aware behavior even
without a trailing separator. Add correctly owned Assets with stable declared
keys, individual titles/roles/formats/hints, and namespaced non-secret derivation
metadata. Preserve the source folder Asset. Handle absolute entries without
inheriting folder credentials or signed query parameters. Report key conflicts
and ambiguous bases instead of overwriting or guessing.

Recoverable entry failures retain unaffected Assets and successful siblings with
sanitized ClientWarning messages. Invalid transformed types, broken ownership,
unusable structure, and whole-stage failures are opening errors that cannot
silently bypass required transformation. Recompute on each job-output opening;
opening a selected Asset never reruns transformations.

Initial hooks cover the opened document and embedded objects. Automatic hooks
during later native remote navigation remain outside this implementation unless
an application supplies an explicit composed I/O policy.

**Validation:** composition/registration isolation, order and predicates, one parse,
copy boundaries and ownership, no scans/probes/payload reads/credential acquisition,
folder joining, conflicts, partial and stage failures, changed configuration,
repeated use, and exact opening of derived Assets.

**Documentation:** document the composition API, a minimal runnable declared-products
example, transformation failure behavior, and the initial-document/navigation
boundary. Keep uniform listing/diagnostics, previews, generic discovery, automatic
pagination, and new browser action adapters explicitly deferred.

### Mandatory completion checks

Before the Step 5 review, exercise the integrated workflow against both Step 2
processes: execute a job, inspect raw outputs, open native STAC metadata, select and
read an Asset, apply configured transformation, read a derived Asset, and clean up.
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

**Pause:** review reusable composition, the declared-products example, integrated
verification, essential documentation, and remaining limitations. The mandatory
implementation ends here. Do not start optional Step 6 without user authorization.

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
| 4: bounded metadata opening and document bases | 2 |
| 5: client job behavior and argument validation | 1, 3 |
| 6: independent Assets and location handling | 3 |
| 7: composed opener and predicate isolation | 5 |
| 8: declared owned folder products | 2, 5 |
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
