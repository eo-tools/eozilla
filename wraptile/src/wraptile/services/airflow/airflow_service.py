#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import datetime
import logging
import os
from typing import Any, Optional

import fastapi
from airflow_client.client import (
    ApiClient,
    ApiException,
    Configuration,
    DAGRunPatchBody,
    DAGRunPatchStates,
    DAGRunResponse,
    DagRunState,
    TriggerDAGRunPostBody,
)
from airflow_client.client.api import DAGApi
from airflow_client.client.api import DagRunApi as DAGRunApi
from airflow_client.client.api import XComApi

from gavicore.models import (
    InputDescription,
    JobInfo,
    JobList,
    JobResults,
    JobStatus,
    OutputDescription,
    ProcessDescription,
    ProcessList,
    ProcessRequest,
    ProcessSummary,
)
from procodile.workflow import FINAL_STEP_ID
from wraptile.exceptions import ServiceException
from wraptile.services.airflow.tokens import TokenProvider, create_token_provider
from wraptile.services.base import ServiceBase

_log = logging.getLogger(__name__)

DEFAULT_AIRFLOW_BASE_URL = "http://localhost:8080"


class AirflowService(ServiceBase):
    def __init__(
        self,
        title: str,
        description: Optional[str] = None,
    ):
        super().__init__(title=title, description=description)
        self._exec_count: int = 0
        self._airflow_base_url: Optional[str] = None
        self._airflow_username: Optional[str] = None
        self._airflow_password: Optional[str] = None
        self._token_provider_instance: Optional[TokenProvider] = None
        self._api_client: Optional[ApiClient] = None

    def configure(
        self,
        airflow_base_url: Optional[str] = None,
        airflow_username: Optional[str] = None,
        airflow_password: Optional[str] = None,
    ):
        """
        Configure the Airflow service.

        Args:
            airflow_base_url: The base URL of the Airflow web API, defaults to
                `http://localhost:8080`.
            airflow_username: The Airflow username, defaults to `admin`.
            airflow_password: The Airflow password.
                For an Airflow installation with the simple Auth manager,
                use the one from
                `.airflow/simple_auth_manager_passwords.json.generated`.
        """
        self._airflow_base_url = airflow_base_url
        self._airflow_username = airflow_username
        self._airflow_password = airflow_password

    async def get_processes(
        self, request: fastapi.Request, *args, **kwargs
    ) -> ProcessList:
        processes: list[ProcessSummary] = []
        try:
            dag_collection = self.airflow_dag_api.get_dags(
                exclude_stale=True,
                limit=None,
                owners=None,  # TODO important, get for current user only
            )
        except ApiException as e:
            raise ServiceException(e.status, detail=e.reason, exception=e) from e
        if dag_collection and dag_collection.dags:
            for dag in dag_collection.dags:
                # https://github.com/apache/airflow-client-python/blob/main/airflow_client/client/models/dag_response.py
                processes.append(
                    ProcessSummary(
                        id=dag.dag_id,
                        version="0.0.0",  # TODO: get version
                        title=dag.dag_display_name,
                        description=dag.description,
                    )
                )
        return ProcessList(
            processes=processes,
            links=[self.get_self_link(request, "get_processes")],
        )

    async def get_process(self, process_id: str, *args, **kwargs) -> ProcessDescription:
        try:
            dag_details = self.airflow_dag_api.get_dag_details(dag_id=process_id)
        except ApiException as e:
            raise ServiceException(e.status, detail=e.reason, exception=e) from e

        inputs: dict[str, InputDescription] = {}
        if dag_details.params:
            for param_key, param_value in dag_details.params.items():
                _log.debug("DAG param %r: %r", param_key, param_value)
                input_desc = self._param_to_input_description(param_key, param_value)
                if input_desc is not None:
                    inputs[param_key] = input_desc

        # TODO: where to get outputs from?
        outputs: dict[str, OutputDescription] = {}

        return ProcessDescription(
            id=dag_details.dag_id,
            version="0.0.0",  # TODO: get version
            title=dag_details.dag_display_name,
            description=dag_details.doc_md or dag_details.description,
            inputs=inputs,
            outputs=outputs,
        )

    @staticmethod
    def _param_to_input_description(
        param_key: str, param_value: Any
    ) -> InputDescription | None:
        if not isinstance(param_value, dict):
            return None
        schema_dict: dict = param_value.get("schema", {})
        default = param_value.get("value")
        title = schema_dict.get("title")
        description = param_value.get("description") or schema_dict.get("description")
        nullable = bool(schema_dict.get("nullable", False))
        schema_override: dict[str, Any] = {
            "default": default,
            "description": description,
        }
        if title is not None:
            schema_override["title"] = title
        return InputDescription.model_validate(
            {
                "schema": {**schema_dict, **schema_override},
                "title": title,
                "description": description,
                "minOccurs": 0 if nullable else 1,
            }
        )

    async def execute_process(
        self, process_id: str, process_request: ProcessRequest, *args, **kwargs
    ) -> JobInfo:
        logical_date = datetime.datetime.now(datetime.timezone.utc)
        dag_run_id = self.new_dag_run_id(process_id, logical_date)
        dag_run_body = TriggerDAGRunPostBody(
            dag_run_id=dag_run_id,
            conf=process_request.inputs,
            logical_date=logical_date,
        )
        try:
            dag_run = self.airflow_dag_run_api.trigger_dag_run(process_id, dag_run_body)
        except ApiException as e:
            raise ServiceException(e.status, e.reason, exception=e) from e
        return self.dag_run_to_job_info(dag_run)

    async def get_jobs(self, request: fastapi.Request, *args, **kwargs) -> JobList:
        try:
            dag_collection = self.airflow_dag_api.get_dags(
                exclude_stale=True,
                limit=None,
                owners=None,  # TODO important, get for current user only
            )
        except ApiException as e:
            raise ServiceException(e.status, detail=e.reason, exception=e) from e

        jobs: list[JobInfo] = []
        for dag in dag_collection.dags:
            try:
                dag_run_collection = self.airflow_dag_run_api.get_dag_runs(dag.dag_id)
            except ApiException as e:
                raise ServiceException(e.status, e.reason, exception=e) from e
            jobs.extend(
                self.dag_run_to_job_info(dag_run)
                for dag_run in dag_run_collection.dag_runs
            )
        return JobList(jobs=jobs, links=[self.get_self_link(request, name="get_jobs")])

    async def get_job(self, job_id: str, *args, **kwargs) -> JobInfo:
        dag_id = self.get_dag_id_from_job_id(job_id)
        try:
            dag_run = self.airflow_dag_run_api.get_dag_run(dag_id, job_id)
        except ApiException as e:
            raise ServiceException(e.status, e.reason, exception=e) from e
        return self.dag_run_to_job_info(dag_run)

    async def dismiss_job(self, job_id: str, *args, **kwargs) -> JobInfo:
        dag_id = self.get_dag_id_from_job_id(job_id)
        dag_run_patch = DAGRunPatchBody(
            note="Cancelled", state=DAGRunPatchStates.FAILED
        )
        try:
            # TODO: check if this really works
            dag_run = self.airflow_dag_run_api.patch_dag_run(
                dag_id, job_id, dag_run_patch
            )
        except ApiException as e:
            raise ServiceException(e.status, e.reason, exception=e) from e
        return self.dag_run_to_job_info(dag_run)

    async def get_job_results(self, job_id: str, *args, **kwargs) -> JobResults:
        dag_id = self.get_dag_id_from_job_id(job_id)
        return_value: Optional[Any] = None
        try:
            xcom_entry = self.airflow_xcom_api.get_xcom_entry(
                dag_id=dag_id,
                dag_run_id=job_id,
                task_id=FINAL_STEP_ID,
                xcom_key="return_value",
            )
            if xcom_entry is not None and xcom_entry.actual_instance is not None:
                return_value = xcom_entry.actual_instance.value
        except ApiException as e:
            raise ServiceException(e.status, e.reason, exception=e) from e
        # TODO: use keys from output definitions, if provided.
        #   Otherwise, "return_value" is correct.
        return JobResults({"return_value": return_value})  # type: ignore[dict-item]

    def new_dag_run_id(self, dag_id: str, logical_time: datetime.datetime):
        self._exec_count += 1
        return f"{dag_id}__{logical_time.strftime('%Y%m%d%H%M%S')}_{self._exec_count}"

    @classmethod
    def get_dag_id_from_job_id(cls, job_id):
        return job_id.split("__", maxsplit=1)[0]

    @classmethod
    def dag_run_to_job_info(cls, dag_run: DAGRunResponse) -> JobInfo:
        return JobInfo(
            jobID=dag_run.dag_run_id,
            processID=dag_run.dag_id,
            status=cls.dag_run_state_to_job_status(dag_run.state),
            progress=None,  # check, it seems we have no good option here
            message=dag_run.note,  # check
            created=dag_run.queued_at,
            started=dag_run.start_date,
            updated=dag_run.last_scheduling_decision,
            finished=dag_run.end_date,
        )

    @classmethod
    def dag_run_state_to_job_status(cls, dag_run_state: DagRunState) -> JobStatus:
        mapping = {
            DagRunState.RUNNING: JobStatus.running,
            DagRunState.FAILED: JobStatus.failed,
            DagRunState.QUEUED: JobStatus.accepted,
            DagRunState.SUCCESS: JobStatus.successful,
        }
        return mapping[dag_run_state]

    # NOTE: these are plain properties (not cached_property) so every call
    # re-reads airflow_client, which refreshes the bearer token on expiry. A
    # cached_property would pin the first token for the life of the service.
    @property
    def airflow_dag_api(self) -> DAGApi:
        return DAGApi(self.airflow_client)

    @property
    def airflow_dag_run_api(self) -> DAGRunApi:
        return DAGRunApi(self.airflow_client)

    @property
    def airflow_xcom_api(self) -> XComApi:
        return XComApi(self.airflow_client)

    @property
    def airflow_client(self) -> ApiClient:
        airflow_base_url: str = (
            self._airflow_base_url
            or os.getenv("AIRFLOW_API_BASE_URL")
            or DEFAULT_AIRFLOW_BASE_URL
        )
        access_token = self._token_provider(airflow_base_url).get_token()
        if self._api_client is None:
            self._api_client = ApiClient(
                Configuration(host=airflow_base_url, access_token=access_token)
            )
        else:
            # The generated Airflow client resolves the bearer header from
            # configuration.access_token at call time, so mutating it in place
            # refreshes auth without discarding the connection pool.
            self._api_client.configuration.access_token = access_token
        return self._api_client

    def _token_provider(self, base_url: str) -> TokenProvider:
        if self._token_provider_instance is None:
            self._token_provider_instance = create_token_provider(
                base_url,
                username=self._airflow_username,
                password=self._airflow_password,
            )
        return self._token_provider_instance
