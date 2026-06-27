#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod
from functools import cached_property
from typing import TYPE_CHECKING, Literal

from cuiman.api.ishell import has_ishell

from .config import ClientConfig

if TYPE_CHECKING:
    import remotestate as rs


class ClientAppMixin(ABC):
    """
    Extra methods for the Client App.
    """

    @property
    @abstractmethod
    def config(self) -> ClientConfig:
        """Will be overridden by the actual client class."""

    @cached_property
    def app_store(self) -> "rs.Store":
        """
        Shared state store used by the Cuiman app.

        Use this store to inspect or update the data shown by
        [show_app()][cuiman.api.client_app_mixin.ClientAppMixin.show_app].

        Currently, the app store comprises a single state variable
        ``processRequests`` which is a mapping from process ID to
        process requests. A process request comprises basically two
        attributes:

        - ``inputs``: a mapping from input name to an input's value.
        - ``outputs``: the outputs to be generated. Just used to detect
          whether an output is included or now.

        The most convenient way to work with nested app state is the
        ``at`` accessor. Examples:

        - ``client.app_store.at.processRequests.myProcess.inputs.threshold = 0.75``
        - ``client.app_store.at.processRequests.myProcess = {"inputs": {...}}``
        """
        from cuiman.app import create_app_remote_store

        return create_app_remote_store()

    def show_app(
        self,
        *,
        debug: bool = False,
        scheme: Literal["dark", "light", "auto"] = "auto",
        width: int | str = "100%",
        height: int | str = 600,
        display: Literal["browser", "notebook", "auto"] = "auto",
    ) -> "rs.ServeResult":
        """
        Show the Cuiman app for this client.

        The app connects to this client's API configuration and uses
        [app_store][cuiman.api.client_app_mixin.ClientAppMixin.app_store] as
        its shared state. You can keep using ``client.app_store`` while the app
        is open, including its ``at`` accessor, to interact with the data the
        app reads and writes.

        Args:
            debug: Enable app debug mode.
            scheme: Color scheme to use in the app. ``"auto"`` follows the
                surrounding notebook theme when the app is embedded.
            width: Width of the notebook iframe.
            height: Height of the notebook iframe.
            display: Where to show the app. ``"auto"`` embeds it in notebooks
                and opens it in a browser otherwise.
        Return:
            An instance of type ``remotestate.ServeResult``.
        """
        from cuiman.app import serve

        display_ = (
            ("notebook" if has_ishell else "browser") if display == "auto" else display
        )

        # noinspection PyTypeChecker
        return serve(
            self.config,
            self.app_store,
            compact=display_ == "notebook",
            debug=debug,
            scheme=scheme,
            width=width,
            height=height,
            display=display_,
        )
