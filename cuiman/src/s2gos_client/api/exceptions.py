#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from s2gos_common.models import ApiError


class ClientError(Exception):
    """Raised if a web API call failed.

     The failure can have several reasons such as

    - the request failed with a status code that is not 2xx, or
    - the received JSON response is not parsable.

    Args:
        message: The error message
        api_error: The details describing the error that occurred on the server
            or the details that describe a non-expected response from the server.
    """

    def __init__(self, message: str, api_error: ApiError):
        super().__init__(message)
        self.api_error = api_error
