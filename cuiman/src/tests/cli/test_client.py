#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

import click
import pytest
import typer

from s2gos_client import ClientError
from s2gos_client.api.client import Client
from s2gos_client.api.transport import TransportError
from s2gos_client.cli.cli import cli
from s2gos_client.cli.client import use_client
from s2gos_common.models import ApiError


class UseClientTest(TestCase):
    def test_success(self):
        with use_client(new_cli_context(), None) as client:
            self.assertIsInstance(client, Client)

    # noinspection PyMethodMayBeStatic
    def test_fail_with_client_error(self):
        with pytest.raises(click.exceptions.Exit):
            with use_client(new_cli_context(), None):
                raise ClientError(
                    "Not found",
                    api_error=ApiError(
                        type="error",
                        title="Not found",
                        status=404,
                        detail="Something was not found",
                        traceback=["a", "b", "c"],
                    ),
                )

    # noinspection PyMethodMayBeStatic
    def test_fail_with_client_error_and_traceback(self):
        with pytest.raises(ClientError, match="Not found"):
            with use_client(new_cli_context(traceback=True), None):
                raise ClientError(
                    "Not found",
                    api_error=ApiError(
                        type="error",
                        title="Not found",
                        status=404,
                        detail="Something was not found",
                        traceback=["a", "b", "c"],
                    ),
                )

    # noinspection PyMethodMayBeStatic
    def test_fail_with_transport_error(self):
        with pytest.raises(click.exceptions.Exit):
            with use_client(new_cli_context(), None):
                raise TransportError("connection could not be established")

    # noinspection PyMethodMayBeStatic
    def test_fail_with_transport_error_and_traceback(self):
        with pytest.raises(TransportError, match="connection could not be established"):
            with use_client(new_cli_context(traceback=True), None):
                raise TransportError("connection could not be established")

    # noinspection PyMethodMayBeStatic
    def test_fail_with_other_error(self):
        with pytest.raises(ValueError, match=r"path must be given"):
            with use_client(new_cli_context(), None):
                raise ValueError("path must be given")


def new_cli_context(traceback: bool = False):
    return typer.Context(
        cli,
        obj={
            "get_client": lambda config_path: Client(config_path=config_path),
            "traceback": traceback,
        },
        # the following have no special meaning for the tests,
        # but typer/click wants them to be given.
        allow_extra_args=False,
        allow_interspersed_args=False,
        ignore_unknown_options=False,
    )
