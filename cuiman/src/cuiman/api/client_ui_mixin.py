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


class ClientUiMixin(ABC):
    """
    Extra methods for the Client UI.
    """

    @property
    @abstractmethod
    def config(self) -> ClientConfig:
        """Will be overridden by the actual client class."""

    @cached_property
    def ui_data(self) -> "rs.Store":
        from cuiman.app import create_app_remote_store

        return create_app_remote_store()

    def show_ui(
        self,
        *,
        debug: bool = False,
        scheme: Literal["dark", "light", "auto"] = "auto",
        width: int | str = "100%",
        height: int | str = 600,
        display: Literal["browser", "notebook", "auto", "none"] = "auto",
    ) -> None:
        from cuiman.app import serve

        display_ = (
            ("notebook" if has_ishell else "browser") if display == "auto" else display
        )

        serve(
            self.config,
            self.ui_data,
            compact=display_ == "notebook",
            debug=debug,
            scheme=scheme,
            width=width,
            height=height,
            display=display_,
        )
