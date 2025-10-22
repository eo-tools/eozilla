#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import logging


class LogMessageFilter(logging.Filter):
    def __init__(self, *excludes: str):
        super().__init__(f"Log message filter: {excludes}")
        self.excludes = excludes

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name == "uvicorn.access":
            for exclude in self.excludes:
                if exclude in record.getMessage():
                    return False
        return True
