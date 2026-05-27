So my team has created [Eozilla](https://github.com/eo-tools/eozilla/) with 
an OGC API - Processes client Cuiman which can also provide a tiny but 
very useful GUI (in `cuiman.gui`). Users like it. 

Cuiman's GUI heavily relies on `gavicore.ui` that is used to generate GUIs
from OpenAPI schemas. GUI generation is currently targeting 
[Panel](https://panel.holoviz.org/).

Now after a while using Panel in Jupyter notebooks my frustration 
about GUI programming "the old way" grows, and I'm looking for alternatives.

Panel requires users to use a MVC UI architecture that quickly ends up in
an observer/emitter dependency hell for UIs with many widgets connected 
to each other. Code is no longer comprehensive even (or especially?) 
if split into view and view-model classes.
Debugging is extremely hard, especially for bugs that occur when UIs are run
in Jupyter notebooks only, as logging and stdout outputs are suppressed 
for whatever reason (this may also be a problem caused by Jupyter). 

Let's create a GUI project from scratch using my favorite stack: an SPA using 
TypeScript, React, Mantine, Zustand, and Vite. The new app should replace 
the main Panel GUI entirely. 
It should be usable as a standalone app oor from within
Jupyter lab (by iframe rendering). The primary API it connect to should be the 
[OGC API - Processes, Part 1](https://github.com/opengeospatial/ogcapi-processes) 
as provided, for example, by the Eozilla Wraptile server.

Using an optional parameter, the app can make use of the [Zwieback]() 
TypeScript client, that uses a Zwieback Python WebSocket server.
Zwieback is another project we develop.

The UI comprises the following main parts:

1. "Processes" - A panel that lists all available processes.
   A process item is selectable.
   The primary model is `ProcessList` fetched from async 
   operation `getProcesses() -> ProcessList`. It comprises `ProcessSummary` items.
2. "Process Details" - A panel that displays the details of a selected
   process in the "Processes" panel. Primary model is `ProcessDescription`
   fetched from async operation `getProcess(process_id: str) -> ProcessDescription`.
3. "Process Request" - A panel that displays the inputs and outputs for a selected
   process. The UI is generated from the inputs and output mappings of the 
   associated primary model `ProcessDescription`: 
   `InputDescription` and `OutputDescription`.
   The panel's primary responsibility is creating a process request 
   (model `ProcessRequest`) and executing it using the async operation
   `executeProcess(process_id: str, process_request: ProcessRequest) -> JobInfo`.
   In a second step it is planned to persist user-defined, named process requests.
4. "Jobs" - A panel that lists all jobs submitted by the user.
   The panel is updated periodically  to reflect changed job states. Primary model is `JobList`
   retrieved from async operation `getJobs() -> JobList`.
   The panel's primary responsibility is managing a user's jobs.
   Multiple jobs can be selected.
   Selected jobs can be canceled (operation `dismissJob(jobId)`) and deleted
   (operation `deleteJob(jobId)`).
5. "Job Details" - A panel that displays the details a job. Primary model is `JobInfo`
   retrieved from async operation `getJob(job_id: str) -> JobInfo`.
   
   The panel is updated periodically to reflect changed job state.

