#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Literal

from cuiman.api.ishell import has_ishell

from .config import ClientConfig

if TYPE_CHECKING:
    from cuiman.app import App


class ClientAppMixin(ABC):
    """
    Extra methods for the Client App.
    """

    @property
    @abstractmethod
    def config(self) -> ClientConfig:
        """Will be overridden by the actual client class."""

    def show_app(
        self,
        *,
        compact: bool | None = None,
        debug: bool = False,
        scheme: Literal["dark", "light", "auto"] = "auto",
        width: int | str = "100%",
        height: int | str = 600,
        display: Literal["browser", "notebook", "auto"] = "auto",
    ) -> "App":
        """
        Show the Cuiman app for this client.

        The app connects to this client's API configuration, renders the app GUI,
        and returns an object that provides the serve result and a shared
        [app state][cuiman.app.AppState], which you can interact with.

        The app state currently only manages the process requests being
        edited and executed by a user. The requests are a mapping from process IDs
        to process requests.

        Display the app and get the app instance:

        ```
        app = client.show_app()
        ```

        You can get and set process requests using the methods

        - ``app.get_process_request(process_id)``
        - ``app.set_process_request(process_id, process_request)``

        where ``process_id`` is the process ID and ``process_request`` is a dict
        or a ``ProcessRequest`` object that comprises basically two attributes:

        - ``inputs``: a mapping from input name to an input's value.
        - ``outputs``: the outputs to be generated. Just used to detect
          whether an output is included or now.

        Another convenient way to work with the nested app state is the
        ``process_requests`` property:

        - ``app.process_requests.my_process.inputs.threshold = 0.75``
        - ``app.process_requests.my_process = {"inputs": {...}}``

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
            An ``App`` instance.
        """
        from cuiman.app import App, serve

        display_ = (
            ("notebook" if has_ishell else "browser") if display == "auto" else display
        )
        compact_ = compact if isinstance(compact, bool) else display_ == "notebook"

        remote_store = App.create_remote_store()

        # noinspection PyTypeChecker
        serve_result = serve(
            self.config,
            remote_store,
            compact=compact_,
            debug=debug,
            scheme=scheme,
            width=width,
            height=height,
            display=display_,
        )

        return App(remote_store, serve_result)
