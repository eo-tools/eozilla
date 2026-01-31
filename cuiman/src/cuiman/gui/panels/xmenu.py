from collections.abc import Iterable

import panel as pn
import param


class XMenu(pn.viewable.Viewer):
    open = param.Boolean(default=False)

    def __init__(
        self,
        label: str,
        items: Iterable[pn.viewable.Viewable],
        description: str | None = None,
        **params,
    ):
        super().__init__(**params)

        self.label = label
        self.button = pn.widgets.Button(name=label + " v", description=description)
        self.button.on_click(lambda _: self._toggle())

        self.menu = pn.Column(
            *items,
            visible=False,
            styles={"position": "relative", "z-index": "1000"},
        )

    def _toggle(self):
        self.open = not self.open
        self.menu.visible = self.open
        self.button.name = self.label + (" ^" if bool(self.open) else " v")

    def __panel__(self):
        return pn.Column(
            self.button,
            self.menu,
            sizing_mode="fixed",
        )
