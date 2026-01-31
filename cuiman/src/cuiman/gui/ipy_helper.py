#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import TYPE_CHECKING
from pydantic import BaseModel

from gavicore.models import JobResults
from gavicore.util.request import ExecutionRequest

if TYPE_CHECKING:
    from IPython import InteractiveShell


class IPyHelper:
    @classmethod
    def set_execution_request_in_user_ns(
        cls, request: ExecutionRequest, var_name: str = "_request"
    ):
        shell = cls.get_interactive_shell()
        shell.user_ns[var_name] = request
        return var_name

    @classmethod
    def set_job_results_in_user_ns(
        cls, results: JobResults | dict, var_name: str = "_results"
    ) -> str:
        value = results.root if isinstance(results, JobResults) else results
        if isinstance(value, dict):
            value = JsonDict(
                "Results",
                {
                    k: (v.model_dump() if isinstance(v, BaseModel) else v)
                    for k, v in value.items()
                },
            )

        shell = cls.get_interactive_shell()
        shell.user_ns[var_name] = value
        return var_name

    @classmethod
    def get_interactive_shell(cls) -> "InteractiveShell":
        # noinspection PyProtectedMember
        from IPython import get_ipython

        interactive_shell = get_ipython()
        if interactive_shell is None:
            raise RuntimeError("Not running inside an interactive IPython shell")
        return interactive_shell


class JsonDict(dict):
    """A JSON object value that renders nicely in Jupyter notebooks."""

    def __init__(self, name: str, *args, **kwargs):
        # noinspection PyArgumentList
        super().__init__(*args, **kwargs)
        self._name = name

    def _repr_json_(self):
        return self, {"root": f"{self._name}:"}
