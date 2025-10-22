#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import panel as pn
import param
from ipyleaflet import DrawControl, GeoJSON, Map


class BboxSelector(pn.viewable.Viewer):
    value = param.List(
        bounds=(4, 4),
        default=None,
        doc="Bounding box as [min_lon, min_lat, max_lon, max_lat]",
    )

    def __init__(self, center=(0, 0), zoom=2, **params):
        # noinspection PyArgumentList
        super().__init__(**params)

        # Set up the draw control
        draw_control = DrawControl(rectangle={"shapeOptions": {"color": "#0000FF"}})
        draw_control.rectangle = {"shapeOptions": {"color": "#0000FF"}}
        draw_control.circle = {}
        draw_control.polyline = {}
        draw_control.polygon = {}
        draw_control.point = {}
        draw_control.on_draw(self._handle_draw)

        # Create the map
        self.map = Map(center=center, zoom=zoom, scroll_wheel_zoom=True)
        self.map.add(draw_control)

        # Leaflet map as ipy-widget
        map_widget = pn.pane.IPyWidget(self.map, width=512)

        # Displayed value as text for feedback
        value_display = pn.widgets.StaticText(
            name="Selected bbox", value=str(self.value)
        )

        self._panel = pn.Column(map_widget, value_display)
        self._value_display = value_display

    def __panel__(self):
        return self._panel

    def _handle_draw(self, target: DrawControl, action: str, geo_json: dict):
        if action == "created" and geo_json["geometry"]["type"] == "Polygon":
            target.clear()

            coords = geo_json["geometry"]["coordinates"][0]
            lons = [c[0] for c in coords]
            lats = [c[1] for c in coords]
            min_lon, max_lon = min(lons), max(lons)
            min_lat, max_lat = min(lats), max(lats)
            self.value = [min_lon, min_lat, max_lon, max_lat]
            self._value_display.value = str(self.value)

            for layer in self.map.layers:
                if layer.name == "user":
                    self.map.remove(layer)
                    break
            user_layer = GeoJSON(name="user", data=geo_json)
            self.map.add(user_layer)
