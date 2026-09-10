#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from contextlib import contextmanager
from types import TracebackType
from typing import Callable, Iterator, Literal, Optional, TypeAlias

import httpx2
import typer
from authlib.common.errors import AuthlibBaseError
from joserfc.errors import JoseError

from cuiman.api.auth import LoginRequiredError
from cuiman.api.auth.secret_store import SecretStoreError
from cuiman.api.client import Client
from cuiman.api.exceptions import ClientError
from cuiman.api.transport import TransportError

GetClient: TypeAlias = Callable[[str | None], Client]


@contextmanager
def handle_auth_errors() -> Iterator[None]:
    """Report actionable CLI failures without echoing provider token responses."""
    try:
        yield
    except (AuthlibBaseError, JoseError, httpx2.HTTPError) as exc:
        typer.echo(
            "Authentication failed. Check provider settings and credentials; "
            "use 'cuiman login --force' to sign in again.",
            err=True,
        )
        raise typer.Exit(code=1) from exc
    except (SecretStoreError, RuntimeError, TimeoutError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


def use_client(ctx: typer.Context, config_file: str | None) -> "UseClient":
    """
    Context manager
    """
    return UseClient(ctx, config_file)


class UseClient:
    def __init__(self, ctx: typer.Context, config_file: str | None):
        self.ctx = ctx
        self.config_file = config_file
        self.client: Client | None = None

    def __enter__(self):
        _get_client: GetClient = self.ctx.obj["get_client"]
        self.client = _get_client(self.config_file)
        return self.client

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Literal[False]:
        if self.client is not None:
            self.client.close()
            self.client = None
        show_traceback = self.ctx.obj.get("traceback", False)
        if isinstance(exc_value, ClientError):
            # Note for the following it may be a good idea to
            # to use rich.traceback for comprehensive output
            client_error: ClientError = exc_value
            api_error = client_error.api_error
            message_lines = [
                f"Error: {client_error}",
                "Server-side error details:",
                f"  title:  {api_error.title}",
                f"  status: {api_error.status}",
                f"  type:   {api_error.type}",
                f"  detail: {api_error.detail}",
            ]
            if api_error.traceback and show_traceback:
                message_lines.append("  traceback:")
                message_lines.extend(api_error.traceback)
            typer.echo("\n".join(message_lines))
            if not show_traceback:
                raise typer.Exit(code=2)
        elif isinstance(exc_value, TransportError):
            typer.echo(f"Transport error: {exc_value}")
            if not show_traceback:
                raise typer.Exit(code=3)
        elif (
            isinstance(exc_value, (AuthlibBaseError, JoseError, LoginRequiredError))
            and not show_traceback
        ):
            with handle_auth_errors():
                raise exc_value

        return False  # propagate exception
