from abc import ABC, abstractmethod
from typing import Optional

from .dru_models import OGCApplicationPackage
from .models import ProcessSummary
from .service import Service


class DRUService(Service, ABC):
    """The DRUService interface extends the Service interface by providing
    four endpoints defined per
    [OGC API - Processes — Part 2 (DRU)](https://docs.ogc.org/DRAFTS/20-044.html)."""

    @abstractmethod
    async def deploy_process(
        self, w: str | None = None, *args, **kwargs
    ) -> Optional[ProcessSummary]:
        """Deploy a new process to a server supporting
        OGC API - Processes — Part 2 (DRU) by providing a process
        description in a supported format.

        Depending on the service implementation,
        the server may not return a response body.

        For more information, see
        [OGC API - Processes — Part 2 (DRU)](https://docs.ogc.org/DRAFTS/20-044.html#deploy).

        Args:
            w: Optionally point to the workflow identifier for deploying a
                CWL containing multiple workflow definitions.
        """

    @abstractmethod
    async def replace_process(
        self,
        process_id: str,
        w: str | None = None,
        *args,
        **kwargs,
    ) -> Optional[ProcessSummary]:
        """Replace an exisitng and mutable process by providing a new
        process description in a supported format.

        Depending on the service implementation,
        the server may not return a response body.

        For more information, see
        [OGC API - Processes — Part 2 (DRU)](https://docs.ogc.org/DRAFTS/20-044.html#replace).

        Args:
            process_id: Unique identifier of registered process
                that is to be replaced.
            w: Optionally point to the workflow identifier for deploying a
                CWL containing multiple workflow definitions.
        """

    @abstractmethod
    async def undeploy_process(self, process_id: str, *args, **kwargs) -> None:
        """Remove an exisitng and mutable process by providing
        its process id.

        For more information, see
        [OGC API - Processes — Part 2 (DRU)](https://docs.ogc.org/DRAFTS/20-044.html#undeploy).

        Args:
            process_id: Unique identifier of registered process
                that is to be replaced.
        """

    @abstractmethod
    async def get_formal_description(
        self, process_id: str, *args, **kwargs
    ) -> OGCApplicationPackage:
        """Retrieve a formal description of a previously deployed process
        via the deploy operation.
        The returned description relates to the most recent deployment.

        For more information, see
        [OGC API - Processes — Part 2 (DRU)](https://docs.ogc.org/DRAFTS/20-044.html#application-package-retrieval-operation).

        Args:
            process_id: Unique identifier of registered process
                that is to be replaced.
        """
