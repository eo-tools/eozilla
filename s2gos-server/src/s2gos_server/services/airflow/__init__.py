#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from .airflow_service import DEFAULT_AIRFLOW_BASE_URL, AirflowService

__all__ = [
    "DEFAULT_AIRFLOW_BASE_URL",
    "AirflowService",
]
