# Cuiman reader revision handover

Continue [issue #243](https://github.com/eo-tools/eozilla/issues/243) from step 3.
Steps 1 and 2 are complete. The next change is accepting an already retrieved
`gavicore.models.core.JobResults` in both clients' `read_job_result()` methods.

Recorded on 2026-11-05. Source baseline: commit `abee0861` on
`forman/243-cuiman_opener_api_revision`. This handover and the 0.5.0 entry in
`CHANGES.md` were added afterward.

## Decisions that supersede the original issue

- Use `Client.read_job_result()` and `AsyncClient.read_job_result()` publicly.
  The user explicitly replaced the issue's original instruction to keep
  `open_job_result()`.
- Backward compatibility is unnecessary. Opener modules, imports, configuration
  aliases, and subclass hooks were removed.
- Defer representation conversions, including Zarr to pandas. The placeholder
  is in `cuiman/src/cuiman/api/reader/impl/_xr.py`, in `accept_data_type()`.
  Unsupported representations must raise rather than return a different type.

## Completed behavior

The framework lives in `cuiman.api.reader`, with `JobResultReader`,
`JobResultReadContext`, `JobResultReaderRegistry`, and `JobResultReadError`.
Readers implement `accept_job_result()` and `read_job_result()`; path readers
implement `read_path_like()`. Reader IDs are explicit and unique within a
registry, and an inherited `option_policy` is independent of identity.

Both clients have generic overloads associating `data_type: type[T]` with `T`;
untyped calls return `Any`. Dispatch validates custom and built-in results with
`isinstance`, closes incompatible results when possible, and can try the next
reader. Valid lazy datasets remain open for the caller to manage.

Media types take precedence over suffixes for job outputs and Assets. Explicit
engines override inferred defaults. Zarr inference is shared by xarray reading
and STAC option preparation. Pillow and native STAC reject unsupported engine
overrides. Tests, maintained examples, guides, and notebooks use reader names.

## Step 3 implementation and completion criteria

1. Extend both client methods and their overloads to accept `JobResults`, alongside
   job IDs and PySTAC Assets, retaining typed returns and current call forms.
   Reading supplied results must bypass job polling, process lookup, and
   refetching the result document. Fetching a selected linked payload is allowed.
2. Reuse `JobResultReadContext(job_results=...)` for output selection and copying.
   A sole output is selected automatically; multiple outputs require
   `output_name`. Empty results, unknown names, and ambiguous selection must
   raise clear errors. Explicit null output values remain valid selections.
   Preserve `data_type`, `media_type`, `reader_id`, and reader options, and leave
   the supplied results unchanged.
3. Retain available result-document URL context for relative links. The current
   transport stores effective response URLs against exact result-object identity
   using weak references; `get_response_href(results)` exposes that information.
   Determine how much context is available when results come from another client
   or are manually constructed; preserve available context without guessing a
   document URL from `api_url`.
4. Complete sync/async tests for selection, non-mutation, linked data, relative
   links, and absence of result-document refetches. Extend the static typing
   assertions to `JobResults`, update the reader guide and changelog, and rerun
   the Cuiman suite, coverage, typing, lint, and strict documentation build.

This step is independent of waiting behavior in issue #241. Completion means
both clients satisfy every criterion above; conversions remain deferred.

## Entry points

- `cuiman/src/cuiman/api/client_mixin.py` and `async_client_mixin.py`: public
  overloads and target dispatch. Currently, every non-string target goes through
  the Asset-only context helper.
- `cuiman/src/cuiman/api/client_mixin_base.py`: `_new_job_result_context()` already
  attaches `get_response_href(job_results)` to `ctx.document_href`.
- `cuiman/src/cuiman/api/reader/context.py`: existing selection, copying, and
  location normalization; `job_id` and process metadata are optional.
- `cuiman/src/cuiman/api/transport/httpx2.py`: response URL retention.
- `cuiman/tests/api/test_client_reader.py`, `test_client_asset.py`,
  `test_reader_contract.py`, and `test_reader_identity.py`: client behavior.
- `cuiman/tests/typing/read_job_result.py`: static assertions, executed by
  `cuiman/tests/api/test_reader_typing.py` in the regular suite.
- `docs/cuiman/guides/readers.md`: maintained guide.

## Validation and environment

The last complete step-2 run passed **1,315 tests and 19 subtests**, with **100%
statement coverage of `cuiman.api.reader`**. Source and example lint, example
formatting, type checking, and the strict docs build also passed.

Use the repository's Pixi tasks. In this Windows session, `pixi run --as-is`
used the existing environment after normal Pixi execution hit a cache-directory
error. Tests and docs required the workspace packages' `src` directories on
`PYTHONPATH`; dependency-file access also required sandbox escalation.

The coverage command was:

```powershell
pixi run --as-is test-cuiman -p no:cacheprovider --cov=cuiman.api.reader --cov-report=term-missing -q
```

Type checking used `pixi run --as-is typecheck --exclude '(^|[/\\])site[/\\]'`.
Generated `site/` contains a copy of the docs hook, which otherwise produces a
duplicate-module error. `pixi run --as-is build-docs` passed in strict mode.

At handover creation, the source working tree was clean apart from the unrelated
untracked nested checkout `eozilla-app/`. Preserve that checkout and any new user
changes when continuing.
