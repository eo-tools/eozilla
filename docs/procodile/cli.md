# Procodile-Example CLI

This is the CLI of the Eozilla Procodile example.

You can use shorter command name aliases, e.g., use command name `ep`
for `execute-process`, or `lp` for `list-processes`.

**Usage**:

```console
$ procodile-example [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--version`: Show version and exit.
* `--help`: Show this message and exit.

**Commands**:

* `execute-process`: Execute a process.
* `list-processes`: List all processes.
* `get-process`: Get details of a process.

## `procodile-example execute-process`

Execute a process.

The process request to be submitted may be read from a file given
by `--request`, or from `stdin`, or from the `process_id` argument
with zero, one, or more `--input` (or `-i`) options.

The `process_id` argument and any given `--input` options will override
settings with the same name found in the given request file or `stdin`,
if any.

**Usage**:

```console
$ procodile-example execute-process [OPTIONS] [PROCESS_ID]
```

**Arguments**:

* `[PROCESS_ID]`: Process identifier.

**Options**:

* `-d, --dotpath`: Input names use dot-path notion to encode nested values, e.g., `-i scene.colors.bg=red`.
* `-i, --input [NAME=VALUE]...`: Process input value.
* `-s, --subscriber [NAME=URL]...`: Process subscriber URL.
* `-r, --request PATH`: Execution request file. Use `-` to read from &lt;stdin&gt;.
* `--help`: Show this message and exit.

## `procodile-example list-processes`

List all processes.

**Usage**:

```console
$ procodile-example list-processes [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

## `procodile-example get-process`

Get details of a process.

**Usage**:

```console
$ procodile-example get-process [OPTIONS] PROCESS_ID
```

**Arguments**:

* `PROCESS_ID`: Process identifier.  [required]

**Options**:

* `--help`: Show this message and exit.
