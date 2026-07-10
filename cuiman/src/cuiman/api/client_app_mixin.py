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

    from cuiman.app import AppState


class ClientAppMixin(ABC):
    """
    Extra methods for the Client App.
    """

    @property
    @abstractmethod
    def config(self) -> ClientConfig:
        """Will be overridden by the actual client class."""

    @cached_property
    def app_state(self) -> "AppState":
        """
        Shared, reactive state used by the Cuiman app.

        Use the returned object to inspect or update the internal app state
        rendered by [show_app()][cuiman.api.client_app_mixin.ClientAppMixin.show_app].

        Currently, the app state only manages the process requests being
        edited and executed by a user. The requests are a mapping from process IDs
        to process requests.

        You can get and set process requests using the methods

        - ``client.app_state.get_process_request(process_id)``
        - ``client.app_state.set_process_request(process_id, process_request)``

        where ``process_id`` is the process ID and ``process_request`` is a dict
        or a ``ProcessRequest`` object that comprises basically two attributes:

        - ``inputs``: a mapping from input name to an input's value.
        - ``outputs``: the outputs to be generated. Just used to detect
          whether an output is included or now.

        Another convenient way to work with the nested app state is the
        ``process_requests`` property:

        - ``client.app_state.process_requests.my_process.inputs.threshold = 0.75``
        - ``client.app_state.process_requests.my_process = {"inputs": {...}}``
        """
        from cuiman.app import AppState

        return AppState()

    def show_app(
        self,
        *,
        compact: bool | None = None,
        debug: bool = False,
        scheme: Literal["dark", "light", "auto"] = "auto",
        width: int | str = "100%",
        height: int | str = 600,
        display: Literal["browser", "notebook", "auto"] = "auto",
    ) -> "rs.ServeResult":
        """
        Show the Cuiman app for this client.

        The app connects to this client's API configuration and uses
        [app_state][cuiman.api.client_app_mixin.ClientAppMixin.app_state] as
        its shared state. You can keep using ``client.app_state`` while the app
        is open, including its ``at`` accessor, to interact with the data the
        app reads and writes.

        Args:
            compact: Compact mode. Defaults to True, if ``display`` is "notebook".
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
        compact_ = compact if isinstance(compact, bool) else display_ == "notebook"

        # noinspection PyTypeChecker
        return serve(
            self.config,
            self.app_state.store,
            compact=compact_,
            debug=debug,
            scheme=scheme,
            width=width,
            height=height,
            display=display_,
        )
