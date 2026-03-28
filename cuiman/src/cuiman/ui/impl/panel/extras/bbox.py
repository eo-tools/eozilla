#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

import panel as pn
import param
from ipyleaflet import DrawControl, GeoJSON, Map

pn.extension()

BBox = list[float]


class BBoxEditor(pn.widgets.WidgetBase, pn.custom.PyComponent):
    value = param.List(default=[0, 40, 20, 60], allow_None=False)

    def __init__(
        self,
        center: tuple[float, float] = (0, 0),
        zoom: int = 2,
        **params,
    ):
        super().__init__(**params)

        # --- draw control
        enabled_tool: dict[str, Any] = {"shapeOptions": {"color": "#0000FF"}}
        disabled_tool: dict[str, Any] = {}
        draw_control = DrawControl()
        draw_control.rectangle = enabled_tool
        draw_control.circle = enabled_tool
        draw_control.polygon = enabled_tool
        draw_control.polyline = disabled_tool
        draw_control.circlemarker = disabled_tool
        draw_control.on_draw(self._handle_draw)

        # --- map
        self._map = Map(center=center, zoom=zoom, scroll_wheel_zoom=True)
        self._map.add(draw_control)

        map_widget = pn.pane.IPyWidget(self._map, width=400)

        # --- value display
        # TODO: replace by text box to let user enter the 4 coordinates
        self._value_display = pn.widgets.StaticText()

        def on_value_change(e):
            self._update_display(e.new)

        # react to value changes
        self.param.watch(on_value_change, "value")

        # initial display
        self._update_display(self.value)

        # layout
        self._panel = pn.Column(map_widget, self._value_display)

    # --- Panel rendering
    def __panel__(self):
        return self._panel

    # --- value → UI

    def _update_display(self, value):
        self._value_display.value = f"Selected bbox: {value}"

    # --- map → value
    def _handle_draw(self, target: DrawControl, action: str, geo_json: dict):
        if action != "created":
            return

        if geo_json["geometry"]["type"] != "Polygon":
            return

        target.clear()

        coords = geo_json["geometry"]["coordinates"][0]
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]

        bbox: BBox = [min(lons), min(lats), max(lons), max(lats)]
        self.value = bbox

        # replace user layer
        for layer in list(self._map.layers):
            if getattr(layer, "name", None) == "user":
                self._map.remove(layer)

        self._map.add(GeoJSON(name="user", data=geo_json))
