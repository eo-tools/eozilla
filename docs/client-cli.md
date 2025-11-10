# Client CLI Reference

The `cuiman` tool is a shell client for any web services 
compliant with OGC API - Processes, Part 1: Core Standard.


`cuiman` can be used to get the available processes, get process 
details, execute processes, and manage the jobs originating from the latter. It 
herewith resembles the core functionality of the OGC API - Processes, Part 1.
For details see https://ogcapi.ogc.org/processes/.

You can use shorter command name aliases, e.g., use command name `vr`
for `validate-request`, or `lp` for `list-processes`.

The tool&#x27;s exit codes are as follows:

• `0` - normal exit
• `1` - user errors, argument errors
• `2` - remote API errors 
• `3` - local network transport errors

If the `--traceback` flag is set, the original Python exception traceback
will be shown and the exit code will always be `1`. 
Otherwise, only the error message is shown.

**Usage**:

```console
$ cuiman [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--version`: Show version and exit.
* `--traceback, --tb`: Show server exception traceback, if any.
* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.

**Commands**:

* `configure`: Configure the client tool.
* `list-processes`: List available processes.
* `get-process`: Get process details.
* `create-request`: Create an execution request (template) for...
* `validate-request`: Validate a process execution request.
* `execute-process`: Execute a process in asynchronous mode.
* `list-jobs`: List all jobs.
* `get-job`: Get job details.
* `dismiss-job`: Cancel a running or delete a finished job.
* `get-job-results`: Get job results.

## `cuiman configure`

Configure the client tool.

**Usage**:

```console
$ cuiman configure [OPTIONS]
```

**Options**:

* `-u, --user TEXT`: Your user name.
* `-t, --token TEXT`: Your personal access token.
* `-s, --server TEXT`: The URL of a service complying to the OGC API - Processes.
* `-c, --config PATH`: Client configuration file.
* `--help`: Show this message and exit.

## `cuiman list-processes`

List available processes.

**Usage**:

```console
$ cuiman list-processes [OPTIONS]
```

**Options**:

* `-c, --config PATH`: Client configuration file.
* `-f, --format [simple|json|yaml]`: Output format.  [default: yaml]
* `--help`: Show this message and exit.

## `cuiman get-process`

Get process details.

**Usage**:

```console
$ cuiman get-process [OPTIONS] PROCESS_ID
```

**Arguments**:

* `PROCESS_ID`: Process identifier.  [required]

**Options**:

* `-c, --config PATH`: Client configuration file.
* `-f, --format [simple|json|yaml]`: Output format.  [default: yaml]
* `--help`: Show this message and exit.

## `cuiman create-request`

Create an execution request (template) for a given process.

The generated template comprises generated default values for all inputs.
Note that they might not necessarily be valid.
The generated template request may serve as a starting point for the actual,
valid execution request.

**Usage**:

```console
$ cuiman create-request [OPTIONS] [PROCESS_ID]
```

**Arguments**:

* `[PROCESS_ID]`: Process identifier.

**Options**:

* `-d, --dotpath`: Input names use dot-path notion to encode nested values, e.g., `-i scene.colors.bg=red`.
* `-c, --config PATH`: Client configuration file.
* `-f, --format [simple|json|yaml]`: Output format.  [default: yaml]
* `--help`: Show this message and exit.

## `cuiman validate-request`

Validate a process execution request.

The execution request to be validated may be read from a file given
by `--request`, or from `stdin`, or from the `process_id` argument
with zero, one, or more `--input` (or `-i`) options.

The `process_id` argument and any given `--input` options will override
settings with the same name found in the given request file or `stdin`, if any.

**Usage**:

```console
$ cuiman validate-request [OPTIONS] [PROCESS_ID]
```

**Arguments**:

* `[PROCESS_ID]`: Process identifier.

**Options**:

* `-d, --dotpath`: Input names use dot-path notion to encode nested values, e.g., `-i scene.colors.bg=red`.
* `-i, --input [NAME=VALUE]...`: Process input value.
* `-r, --request PATH`: Execution request file. Use `-` to read from &lt;stdin&gt;.
* `-f, --format [simple|json|yaml]`: Output format.  [default: yaml]
* `--help`: Show this message and exit.

## `cuiman execute-process`

Execute a process in asynchronous mode.

The execution request to be submitted may be read from a file given
by `--request`, or from `stdin`, or from the `process_id` argument
with zero, one, or more `--input` (or `-i`) options.

The `process_id` argument and any given `--input` options will override
settings with same name found in the given request file or `stdin`, if any.

**Usage**:

```console
$ cuiman execute-process [OPTIONS] [PROCESS_ID]
```

**Arguments**:

* `[PROCESS_ID]`: Process identifier.

**Options**:

* `-d, --dotpath`: Input names use dot-path notion to encode nested values, e.g., `-i scene.colors.bg=red`.
* `-i, --input [NAME=VALUE]...`: Process input value.
* `-s, --subscriber [NAME=URL]...`: Process subscriber URL.
* `-r, --request PATH`: Execution request file. Use `-` to read from &lt;stdin&gt;.
* `-c, --config PATH`: Client configuration file.
* `-f, --format [simple|json|yaml]`: Output format.  [default: yaml]
* `--help`: Show this message and exit.

## `cuiman list-jobs`

List all jobs.

**Usage**:

```console
$ cuiman list-jobs [OPTIONS]
```

**Options**:

* `-c, --config PATH`: Client configuration file.
* `-f, --format [simple|json|yaml]`: Output format.  [default: yaml]
* `--help`: Show this message and exit.

## `cuiman get-job`

Get job details.

**Usage**:

```console
$ cuiman get-job [OPTIONS] JOB_ID
```

**Arguments**:

* `JOB_ID`: Job identifier.  [required]

**Options**:

* `-c, --config PATH`: Client configuration file.
* `-f, --format [simple|json|yaml]`: Output format.  [default: yaml]
* `--help`: Show this message and exit.

## `cuiman dismiss-job`

Cancel a running or delete a finished job.

**Usage**:

```console
$ cuiman dismiss-job [OPTIONS] JOB_ID
```

**Arguments**:

* `JOB_ID`: Job identifier.  [required]

**Options**:

* `-c, --config PATH`: Client configuration file.
* `-f, --format [simple|json|yaml]`: Output format.  [default: yaml]
* `--help`: Show this message and exit.

## `cuiman get-job-results`

Get job results.

**Usage**:

```console
$ cuiman get-job-results [OPTIONS] JOB_ID
```

**Arguments**:

* `JOB_ID`: Job identifier.  [required]

**Options**:

* `-c, --config PATH`: Client configuration file.
* `-f, --format [simple|json|yaml]`: Output format.  [default: yaml]
* `--help`: Show this message and exit.
