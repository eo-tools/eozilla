#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from dataclasses import dataclass, field
from cuiman.api.exceptions import ClientError
from gavicore.models import JobInfo


@dataclass
class JobsPanelState:
    jobs: list[JobInfo] = field(default_factory=list)
    selected_indices: list[int] = field(default_factory=list)
    error: ClientError | None = None

    def selected_jobs(self) -> list[JobInfo]:
        if not self.selected_indices:
            return []
        ids = {self.jobs[i].jobID for i in self.selected_indices}
        return [j for j in self.jobs if j.jobID in ids]
