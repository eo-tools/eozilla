#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import gavicore.util.cli.parameters as cli_params


def test_exported_cli_parameters():
    arguments_and_options = set(
        k for k in dir(cli_params) if k.endswith("_ARGUMENT") or k.endswith("_OPTION")
    )
    assert arguments_and_options == {
        "DOT_PATH_OPTION",
        "PROCESS_ID_ARGUMENT",
        "REQUEST_FILE_OPTION",
        "REQUEST_INPUT_OPTION",
        "REQUEST_SUBSCRIBER_OPTION",
    }
