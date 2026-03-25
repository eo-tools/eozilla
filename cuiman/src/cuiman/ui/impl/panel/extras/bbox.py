#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import panel as pn
import param
from ipyleaflet import DrawControl, GeoJSON, Map

# TODO: This is AI-generated. Verify & test!

pn.extension()

BBox = tuple[float, float, float, float]


class BBoxEditor(pn.widgets.Widget):
    value = param.Tuple(default=None, allow_None=True, length=4)

    def __init__(self, center=(0, 0), zoom: int = 2, **params):
        super().__init__(**params)

        # --- draw control
        draw_control = DrawControl(rectangle={"shapeOptions": {"color": "#0000FF"}})
        draw_control.rectangle = {"shapeOptions": {"color": "#0000FF"}}
        draw_control.circle = {}
        draw_control.polyline = {}
        draw_control.polygon = {}
        draw_control.point = {}
        draw_control.on_draw(self._handle_draw)

        # --- map
        self._map = Map(center=center, zoom=zoom, scroll_wheel_zoom=True)
        self._map.add(draw_control)

        map_widget = pn.pane.IPyWidget(self._map, width=400)

        # --- value display
        self._value_display = pn.widgets.StaticText()

        # react to value changes
        self.param.watch(self._update_display, "value")

        # initial display
        self._update_display(
            param.parameterized.Event(new=self.value, old=None, name="value", obj=self)
        )

        # layout
        self._panel = pn.Column(map_widget, self._value_display)

    # --- Panel rendering
    def __panel__(self):
        return self._panel

    # --- value → UI
    def _update_display(self, event):
        self._value_display.value = f"Selected bbox: {event.new}"

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

        bbox: BBox = (min(lons), min(lats), max(lons), max(lats))
        self.value = bbox

        # replace user layer
        for layer in list(self._map.layers):
            if getattr(layer, "name", None) == "user":
                self._map.remove(layer)

        self._map.add(GeoJSON(name="user", data=geo_json))
