#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""Generic discovery for otherwise unhandled job output values and links."""

from typing import Any
from urllib.parse import quote

from ...resources import JobResultResource, JobResultResourceListing, make_resource_id
from ..context import ResolutionContext
from ..resolver import (
    JobResultResolver,
    json_value,
    output_link,
    output_media_type,
    output_provenance,
    result_listing,
)


class ValueResolver(JobResultResolver):
    """Preserve an otherwise unhandled value or ordinary link as one resource."""

    async def accept(self, ctx: ResolutionContext) -> bool:
        """Accept every output, including scalars, arrays, objects, and null."""
        return True

    async def resolve(self, ctx: ResolutionContext) -> JobResultResourceListing:
        """Normalize references without dereferencing them or splitting values."""
        link = output_link(ctx.value)
        description = ctx.output_description
        fields: dict[str, Any] = {
            "id": make_resource_id(ctx.output_name),
            "output_name": ctx.output_name,
            "path": quote(ctx.output_name, safe=""),
            "kind": "link" if link else "value",
            "media_type": output_media_type(ctx.value),
            "title": (link.title if link else None)
            or (description.title if description else None),
            "description": description.description if description else None,
            "provenance": output_provenance(ctx),
            "discovery_state": "complete",
        }
        if link is not None:
            fields["link"] = link
        else:
            fields["value"] = json_value(ctx.value)
        return result_listing(ctx, [JobResultResource(**fields)])
