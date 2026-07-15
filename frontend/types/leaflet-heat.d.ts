import "leaflet";

declare module "leaflet" {
  interface HeatLayerOptions {
    minOpacity?: number;
    maxZoom?: number;
    max?: number;
    radius?: number;
    blur?: number;
    gradient?: Record<number, string>;
  }

  type HeatLatLngTuple = [number, number, number?];

  function heatLayer(latlngs: HeatLatLngTuple[], options?: HeatLayerOptions): Layer;
}

declare module "leaflet.heat";
