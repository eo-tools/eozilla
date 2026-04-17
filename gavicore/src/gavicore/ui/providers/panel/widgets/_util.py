#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import panel as pn


def get_header_items(title: str | None, divider: bool = False) -> tuple:
    if title:
        text = pn.widgets.StaticText(value=title)
        if divider:
            return text, pn.layout.Divider(margin=(-12, 0, 0, 8))
        return (text,)
    return ()
