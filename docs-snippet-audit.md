# Documentation snippet audit

Audited 2026-09-17. Scope: every `docs/**/*.md` file and root `*.md` file
present before this report: 43 files, including pages absent from MkDocs navigation.
Package READMEs and Markdown inside the separate `eozilla-app` checkout are outside
this scope. That checkout's source and tooling were inspected to assess its docs.

There are 203 fenced blocks, including shell commands, generated help, diagrams,
output, and explanatory fragments. This inventory records possibilities, not an
extraction backlog. Extracting all blocks is neither necessary nor recommended.

Extract an example when it demonstrates meaningful behavior that can silently
break, or when the same code appears in several places. Prefer complete example
modules with named sections and behavior tests. Keep small, clear examples inline
unless extraction offers a concrete maintenance benefit.

## Verification performed

- 32 blocks already use real snippet includes: 14 Python, 17 Bash, and one JSON
  block in the Cuiman guides. Some also contain handwritten calls. The illustrative
  escaped markers in `docs/contributing.md` are not real includes.
- Extracted the remaining 44 Python blocks into temporary files and ran Python
  compilation, Ruff lint, and Ruff formatting checks with the root configuration.
  41 compile, 16 are lint-clean, 13 would be reformatted, and two cannot be parsed
  by the formatter. Ruff can format the standalone `return` example even though
  Python cannot compile it as a module. Missing-name and unused-import findings
  often indicate cross-block dependencies rather than errors in the full tutorial.
- Parsed all 13 embedded JSON/YAML/TOML blocks. All parse, but one YAML-labeled
  block is actually Graphviz DOT and parses as a string. Parsing alone does not
  establish schema validity or example correctness.
- Parsed all 20 TypeScript/TSX blocks with the installed TypeScript parser and
  checked them with the app's Prettier configuration: all parse, four would be
  reformatted. This is not TypeScript semantic checking or React execution.
- Expanded snippets in all 43 Markdown files with `pymdownx.snippets`,
  `check_paths=True`, and dedenting enabled: passed. This is not a full site build.
- Existing `examples/guides` Ruff lint and formatting checks pass (five Python
  files). All 40 tests in `cuiman/tests/test_guide_examples.py` pass, including
  execution of rendered Python walkthroughs in sequence.
- Reproduced three runtime failures offline: the two alternative Procodile
  dependency declarations described below and `Client(...)` in the app overview.
- No deployment, installation recipe, login, browser launch, server, or Docker
  build from the docs was executed. No production snippets were edited.

The initial `pixi run` failure was traced to sandbox access to the existing
`%LOCALAPPDATA%/rattler/cache/uv-cache` directory: `Path.mkdir(exist_ok=True)`
fails with WinError 183 inside the sandbox and succeeds outside it. This does not
indicate cache corruption. Separately, `pixi run --locked --offline` reports an
out-of-date lockfile. `pixi run --as-is python --version` succeeds. The focused
tests used the existing `.pixi/envs/default/python.exe`, added workspace `*/src`
directories to the process import path, and used a fresh pytest temporary
directory because the default pytest temp root was inaccessible. Two dependency
deprecation warnings were reported. The full package suites were not run.

## Repairs to make before extraction

| Location | Finding | Required preparation |
| --- | --- | --- |
| `docs/procodile/usage.md:103` | `Annotated`/`Field` brackets are malformed; types, specifications, defaults, and return type are placeholders; `registry` is indented into the model class but used at module scope. | Replace the conceptual skeleton with a small concrete model, registered function, and execution assertion. |
| `docs/procodile/workflow-dev.md:191` | The alternative `FromMain` example supplies only `Field(title=...)`, not dependency metadata. With the preceding registry/main/step setup and `Field` imported, registration raises `ValueError: Invalid dependency metadata for input 'id'`. | Supply an actual dependency and test the alternative separately. |
| `docs/procodile/workflow-dev.md:227` | `inputs={FromStep(...)}` is a set; registration raises `AttributeError: 'set' object has no attribute 'items'`. | Use an input-name-to-dependency mapping and assert workflow results. |
| `docs/procodile/workflow-dev.md:138` onward | Blocks reuse `registry`, `main_step`, `Annotated`, and `Field`; alternative examples repeat step IDs. | Build separate complete workflows for alternatives instead of executing every fence consecutively. |
| `docs/procodile/workflow-dev.md:325` | Five top-level `return` statements are illustrative output cases, not a compilable module. | Turn these into separate functions and parameterized output-normalization tests. |
| `docs/procodile/workflow-dev.md:388` | Graphviz DOT is labeled YAML; YAML parsing misleadingly succeeds with a string. | Label as DOT and validate/render with Graphviz if extracted. |
| `docs/cuiman/configuration.md:191` | `!cuiman ...` is IPython syntax, not standalone Python. | Keep explicitly notebook-only or show a shell recipe and test the CLI with `CliRunner`. |
| `docs/eozilla-app/index.md:28` | `Client(...)` passes a positional Ellipsis to a keyword-only constructor and raises `TypeError`. | Supply explicit example configuration and test launch/cleanup with mocks. |
| `README.md:42` | Installation says `pip add eozilla`. | Use `pip install eozilla`; keep it synchronized with `docs/index.md:36`. |
| `docs/procodile/usage.md:8` | Installation says `pypi install procodile`. | Use `pip install procodile`. |
| `docs/eozilla-app/dynamic-expressions.md:210` | The displayed interface names `SupportedExpressionNode`; the current implementation uses `SupportedExpression`. | Decide whether the block documents a design or the current API; source current API excerpts from checked declarations. |

## Extraction and test ownership

The following table describes possible destinations and checks if an example
warrants extraction. It does not prescribe implementing every row.

| Area | Extract into | Useful independent checks/tests |
| --- | --- | --- |
| Cuiman configuration (15 Python blocks, three data blocks) | `examples/guides/cuiman/configuration.py` plus JSON/YAML fixtures | Import complete helpers, validate `ClientConfig` variants and equivalent file formats, assert merge/replacement behavior; isolate environment, config paths, and credentials. Supply fixture tokens and custom config types. Mock interactive configuration and authentication. |
| Cuiman getting started and authentication (three Python blocks) | Small synchronous/asynchronous helpers in `examples/guides/cuiman/` | Mock transport/authentication; assert request results and cleanup on both success and failure. No real login or service required. |
| Cuiman customization (two Python blocks) | A small importable example package | Supply the missing `.opener` and `anolis_client` modules/version; test config defaults, opener registration, client factories, and CLI help. |
| Cuiman existing guides | Continue existing named sections | Existing tests cover complete modules and ordered rendered walkthroughs. The notebook launch at `guides/app.md:61` remains embedded; it already runs in the rendered-guide test. Shell recipes and JSON do not gain shell/data formatting checks from Ruff. |
| Appligator Dockerfile generation (four Python blocks) | `examples/guides/appligator/` helpers | Temporary workspace, lockfile, local packages, input files, and output directory; assert generated Dockerfile/context. Follow `appligator/tests/airflow/test_gen_dockerfile.py`. Avoid running Docker. |
| Appligator usage | Concrete process module, YAML fixture, shell recipes | Replace the ellipsis body with deterministic behavior; validate configuration and CLI option mapping with temporary paths and mocked generation/build steps. |
| Procodile usage/workflow development (15 Python blocks) | `examples/guides/procodile/` modules plus request/expected-description fixtures | Registry lookup and process execution, input-model validation, dependency resolution, result mapping, and CLI help. Test each declaration alternative independently. Use `procodile/tests`; compare expected JSON against actual model output. |
| Wraptile customization | Importable example CLI module | Supply the example package version and assert CLI name/version/help without starting a server. Use `wraptile/tests`. |
| Eozilla App Python launch | Reuse a maintained Cuiman app helper | Test configured client, launch, and cleanup without a real browser. |
| App schemas (JSON/YAML) | App fixture files | Parse and feed schemas through the existing generator/dynamic-expression tests; assert widget selection and conditional behavior. The `x-ui` YAML fragment needs its enclosing schema. |
| App TS/TSX | App-owned examples, declarations, and component fixtures | Prettier, ESLint, TypeScript semantic checks, Vitest, and component tests. Signatures need declaration context/imports; JSX needs props and components; the bbox factory needs `isBBoxField` and `BBoxEditor`. Several architecture fragments are descriptive, not runnable examples. |
| Installation/development/CLI recipes | Named shell sections where reuse helps | Check shell syntax and formatting with suitable shell tooling; test application arguments with `CliRunner`. Package installation, Airflow, Docker, and server startup need dedicated integration environments. Do not run every command fence as a script. |
| Generated CLI reference pages | Keep generated by `tools/gen_cli_docs.py` | Validate regeneration/help output. `[OPTIONS]`, placeholders, and `$` prompts are usage notation, not literal executable shell. |
| Mermaid, text, output, snippet-syntax demonstrations | Usually retain in Markdown | Render/diagram syntax checks or compare actual output when worthwhile; these are not Python unit-test extraction targets. |

Inline API expressions and the indented conceptual text/flow descriptions were
also considered. They do not constitute additional self-contained programs; keep
them with their surrounding explanation or include them as sections of the larger
examples above.

## Recommended minimal scope

1. Keep the existing Cuiman extraction setup and tests; they already work.
2. Fix broken examples directly in Markdown where practical. A typo or incomplete
   example does not by itself justify new infrastructure.
3. Extract a few complete Procodile examples, using named sections in the docs and
   tests that verify results. These have the clearest benefit because the audit
   found actual syntax and runtime failures, and tests can run entirely offline.
4. Leave short commands, configuration fragments, signatures, diagrams, generated
   help, output, and illustrative code inline. Reconsider individual examples only
   when repeated code or maintenance failures justify extraction.

Do not add a generic snippet framework, a test per fence, or new shell/TypeScript
tooling solely for this audit. Broader Cuiman, Appligator, Wraptile, and app
extraction remains optional rather than a planned follow-up.

If app extraction later becomes worthwhile, account for its separate checkout:
unconditional includes into `eozilla-app/src` would make the main docs build depend
on that checkout. Root README includes also need special care because GitHub does
not expand `pymdownx.snippets`.

The root tooling already formats and lints `examples/guides/**/*.py` and includes
that tree in mypy's scan. Tests for new example modules must still be added to the
owning package's suite. Only Cuiman's coverage task currently includes its guide
source explicitly; extend another package's coverage task only when adding tested
examples there. The current Python tasks do not cover data/shell/app checks; that
gap alone does not justify adding more tooling.

## Complete file inventory

Counts and fence-opening line numbers below refer to the audited source, before
any extraction. An include count denotes blocks containing actual includes, not
the number of included sections. Zero-block pages contain prose, links, or API
reference directives rather than fenced examples.

| File | Blocks | Languages and fence lines | Includes |
| --- | ---: | --- | ---: |
| `AGENTS.md` | 0 | None | 0 |
| `CHANGES.md` | 0 | None | 0 |
| `CODE_OF_CONDUCT.md` | 0 | None | 0 |
| `CONTRIBUTING.md` | 0 | None | 0 |
| `docs/appligator/cli.md` | 1 | console: 19 | 0 |
| `docs/appligator/gen_dockerfile.md` | 6 | python: 32, 58, 86, 100; bash: 44; unlabelled: 155 | 0 |
| `docs/appligator/index.md` | 0 | None | 0 |
| `docs/appligator/usage.md` | 15 | bash: 8, 12, 16; python: 43; commandline: 58, 74, 95, 107, 118, 129, 139, 150, 200, 207; yaml: 165 | 0 |
| `docs/contributing.md` | 20 | commandline: 36, 43, 52, 58, 68, 75, 85, 106, 114, 123, 132, 139, 154; text: 99; bash: 171, 210, 236; python: 188; markdown: 196; unlabelled: 241 | 0 |
| `docs/cuiman/api.md` | 0 | None | 0 |
| `docs/cuiman/authentication.md` | 2 | python: 23; console: 44 | 0 |
| `docs/cuiman/cli.md` | 15 | console: 33, 71, 96, 114, 133, 153, 169, 194, 222, 251, 275, 291, 311, 331, 351 | 0 |
| `docs/cuiman/configuration.md` | 23 | python: 42, 77, 124, 180, 191, 261, 281, 370, 379, 400, 416, 433, 452, 502, 555; json: 134; yaml: 145, 485; text: 157, 525; bash: 225; console: 298, 536 | 0 |
| `docs/cuiman/customization.md` | 2 | python: 29, 118 | 0 |
| `docs/cuiman/getting-started.md` | 2 | python: 31, 64 | 0 |
| `docs/cuiman/gui-generation.md` | 1 | yaml: 63 | 0 |
| `docs/cuiman/guides/api.md` | 8 | bash: 12, 103; python: 24, 40, 53, 66, 79, 96 | 8 |
| `docs/cuiman/guides/app.md` | 6 | bash: 10, 52; python: 39, 61, 78, 92 | 5 |
| `docs/cuiman/guides/cli.md` | 12 | bash: 14, 21, 31, 43, 54, 63, 72, 79, 86, 100, 113, 119 | 12 |
| `docs/cuiman/guides/openers.md` | 7 | json: 19; python: 32, 48, 71, 82, 100; bash: 107 | 7 |
| `docs/cuiman/index.md` | 0 | None | 0 |
| `docs/eozilla-app/dynamic-expressions.md` | 20 | yaml: 16, 261; text: 57; ts: 83, 93, 102, 121, 137, 210, 282, 307, 327, 366, 405, 433, 478; mermaid: 200; tsx: 354, 393, 447 | 0 |
| `docs/eozilla-app/index.md` | 3 | console: 22; python: 28; text: 51 | 0 |
| `docs/eozilla-app/schema-form.md` | 10 | text: 46, 74; tsx: 83, 604; mermaid: 96, 109, 504; json: 181, 191; bash: 529 | 0 |
| `docs/eozilla-app/service-provider.md` | 5 | ts: 30, 181; mermaid: 215, 245, 265 | 0 |
| `docs/gavicore/index.md` | 0 | None | 0 |
| `docs/gavicore/models/api.md` | 0 | None | 0 |
| `docs/gavicore/models/description.md` | 0 | None | 0 |
| `docs/gavicore/service/api.md` | 0 | None | 0 |
| `docs/gavicore/service/description.md` | 1 | mermaid: 18 | 0 |
| `docs/gavicore/util/api.md` | 0 | None | 0 |
| `docs/gavicore/util/description.md` | 0 | None | 0 |
| `docs/index.md` | 5 | commandline: 36; bash: 52, 71, 82; mermaid: 89 | 0 |
| `docs/procodile/api.md` | 0 | None | 0 |
| `docs/procodile/cli.md` | 4 | console: 10, 39, 61, 75 | 0 |
| `docs/procodile/index.md` | 0 | None | 0 |
| `docs/procodile/usage.md` | 8 | bash: 8, 12, 16; python: 103, 133; toml: 153; json: 182, 234 | 0 |
| `docs/procodile/workflow-dev.md` | 14 | python: 121, 138, 161, 178, 191, 215, 227, 248, 261, 282, 304, 325, 382; yaml: 388 | 0 |
| `docs/wraptile/cli.md` | 3 | console: 16, 38, 58 | 0 |
| `docs/wraptile/customization.md` | 1 | python: 17 | 0 |
| `docs/wraptile/index.md` | 0 | None | 0 |
| `docs/wraptile/usage.md` | 3 | commandline: 7, 21, 30 | 0 |
| `README.md` | 6 | commandline: 42; bash: 58, 77, 88, 105; text: 100 | 0 |

## Embedded Python check results

Each block was checked as a separate temporary `.py` file. These results
describe extraction readiness; a lint-clean block may still need external
modules, files, configuration, or a service. `F821` means missing names,
`F401` unused imports, `F706` return outside a function, and `B018` a
standalone expression with no effect.

| Location | Compiles | Ruff lint codes | Ruff format |
| --- | --- | --- | --- |
| `docs/appligator/gen_dockerfile.md:32` | Yes | Pass | Pass |
| `docs/appligator/gen_dockerfile.md:58` | Yes | F821 | Would reformat |
| `docs/appligator/gen_dockerfile.md:86` | Yes | F821 | Pass |
| `docs/appligator/gen_dockerfile.md:100` | Yes | F821 | Would reformat |
| `docs/appligator/usage.md:43` | Yes | Pass | Would reformat |
| `docs/contributing.md:188` | Yes | Pass | Pass |
| `docs/cuiman/authentication.md:23` | Yes | Pass | Would reformat |
| `docs/cuiman/configuration.md:42` | Yes | F821 | Pass |
| `docs/cuiman/configuration.md:77` | Yes | F821 | Pass |
| `docs/cuiman/configuration.md:124` | Yes | Pass | Pass |
| `docs/cuiman/configuration.md:180` | Yes | Pass | Pass |
| `docs/cuiman/configuration.md:191` | invalid syntax (snippet line 1) | invalid-syntax | Parse error |
| `docs/cuiman/configuration.md:261` | Yes | Pass | Pass |
| `docs/cuiman/configuration.md:281` | Yes | Pass | Pass |
| `docs/cuiman/configuration.md:370` | Yes | F821 | Pass |
| `docs/cuiman/configuration.md:379` | Yes | F821 | Pass |
| `docs/cuiman/configuration.md:400` | Yes | F821 | Pass |
| `docs/cuiman/configuration.md:416` | Yes | F821 | Pass |
| `docs/cuiman/configuration.md:433` | Yes | F821 | Pass |
| `docs/cuiman/configuration.md:452` | Yes | F821 | Pass |
| `docs/cuiman/configuration.md:502` | Yes | F821 | Pass |
| `docs/cuiman/configuration.md:555` | Yes | F821 | Pass |
| `docs/cuiman/customization.md:29` | Yes | Pass | Would reformat |
| `docs/cuiman/customization.md:118` | Yes | Pass | Pass |
| `docs/cuiman/getting-started.md:31` | Yes | Pass | Pass |
| `docs/cuiman/getting-started.md:64` | Yes | Pass | Pass |
| `docs/cuiman/guides/app.md:61` | Yes | F401 | Pass |
| `docs/eozilla-app/index.md:28` | Yes | Pass | Pass |
| `docs/procodile/usage.md:103` | closing parenthesis ']' does not match opening parenthesis '(' (snippet line 9) | invalid-syntax | Parse error |
| `docs/procodile/usage.md:133` | Yes | Pass | Pass |
| `docs/procodile/workflow-dev.md:121` | Yes | Pass | Pass |
| `docs/procodile/workflow-dev.md:138` | Yes | F821 | Pass |
| `docs/procodile/workflow-dev.md:161` | Yes | F821 | Pass |
| `docs/procodile/workflow-dev.md:178` | Yes | F821 | Would reformat |
| `docs/procodile/workflow-dev.md:191` | Yes | F401, F821 | Would reformat |
| `docs/procodile/workflow-dev.md:215` | Yes | F821 | Would reformat |
| `docs/procodile/workflow-dev.md:227` | Yes | F821 | Would reformat |
| `docs/procodile/workflow-dev.md:248` | Yes | F821 | Would reformat |
| `docs/procodile/workflow-dev.md:261` | Yes | F821 | Would reformat |
| `docs/procodile/workflow-dev.md:282` | Yes | F821 | Would reformat |
| `docs/procodile/workflow-dev.md:304` | Yes | B018, F821 | Pass |
| `docs/procodile/workflow-dev.md:325` | 'return' outside function (snippet line 2) | F706 | Pass |
| `docs/procodile/workflow-dev.md:382` | Yes | F821 | Pass |
| `docs/wraptile/customization.md:17` | Yes | Pass | Would reformat |

The four TS/TSX blocks needing Prettier formatting are
`docs/eozilla-app/dynamic-expressions.md:354` and `:393`,
`docs/eozilla-app/schema-form.md:83`, and
`docs/eozilla-app/service-provider.md:181`.
