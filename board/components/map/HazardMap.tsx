"use client";

import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState } from "react";

const BASE = process.env.NEXT_PUBLIC_SANKET_API ?? "";

const OSM_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

const TERRAIN_SOURCE = "terrarium";

export interface MapLayerState {
  flood: boolean;
  cells: boolean;
  lakes: boolean;
  settlements: boolean;
  watched: boolean;
}

export const DEFAULT_LAYERS: MapLayerState = {
  flood: true,
  cells: true,
  lakes: true,
  settlements: true,
  watched: true,
};

interface LayerPayload {
  bbox: number[];
  settlements: GeoJSON.FeatureCollection;
  watched_features: GeoJSON.FeatureCollection;
  lakes: GeoJSON.FeatureCollection;
  flood_path: GeoJSON.FeatureCollection;
  corridor_cells: GeoJSON.FeatureCollection & { max_priority?: number };
  dem_vintage: string;
}

export function HazardMap({
  layers = DEFAULT_LAYERS,
  dimension = "2d",
  focus,
  height = 560,
  onSelect,
}: {
  layers?: MapLayerState;
  dimension?: "2d" | "3d";
  focus?: [number, number] | null;
  height?: number;
  onSelect?: (name: string, kind: string) => void;
}) {
  const container = useRef<HTMLDivElement | null>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [ready, setReady] = useState(false);
  const [data, setData] = useState<LayerPayload | null>(null);

  useEffect(() => {
    void fetch(`${BASE}/api/map/layers`, { cache: "no-store" })
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData(null));
  }, []);

  useEffect(() => {
    if (!container.current || map.current) return;
    const instance = new maplibregl.Map({
      container: container.current,
      style: OSM_STYLE,
      center: [85.28, 28.08],
      zoom: 9.2,
      attributionControl: { compact: true },
    });
    instance.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
    instance.addControl(new maplibregl.ScaleControl({ maxWidth: 120 }), "bottom-left");
    instance.on("load", () => setReady(true));
    map.current = instance;
    return () => {
      instance.remove();
      map.current = null;
    };
  }, []);

  useEffect(() => {
    const instance = map.current;
    if (!instance || !ready || !data) return;

    const put = (id: string, collection: GeoJSON.FeatureCollection) => {
      const existing = instance.getSource(id) as maplibregl.GeoJSONSource | undefined;
      if (existing) existing.setData(collection);
      else instance.addSource(id, { type: "geojson", data: collection });
    };

    put("flood", data.flood_path);
    put("cells", data.corridor_cells);
    put("lakes", data.lakes);
    put("settlements", data.settlements);
    put("watched", data.watched_features);

    if (!instance.getLayer("flood-fill")) {
      instance.addLayer({
        id: "flood-fill",
        type: "fill",
        source: "flood",
        paint: {
          "fill-color": [
            "interpolate",
            ["linear"],
            ["get", "depth_min_m"],
            0.05,
            "#56b4e9",
            1.0,
            "#2781d6",
            2.5,
            "#be1e60",
          ],
          "fill-opacity": 0.75,
        },
      });
    }
    if (!instance.getLayer("cell-circle")) {
      instance.addLayer({
        id: "cell-circle",
        type: "circle",
        source: "cells",
        filter: [">", ["get", "priority"], 0],
        paint: {
          "circle-radius": [
            "interpolate",
            ["linear"],
            ["zoom"],
            8,
            ["interpolate", ["linear"], ["get", "priority_normalised"], 0, 3, 1, 11],
            13,
            ["interpolate", ["linear"], ["get", "priority_normalised"], 0, 7, 1, 30],
          ],
          "circle-color": [
            "interpolate",
            ["linear"],
            ["get", "priority_normalised"],
            0,
            "#f6a740",
            0.35,
            "#ef6f3c",
            0.7,
            "#d93a4e",
            1,
            "#b3123c",
          ],
          "circle-opacity": 0.82,
          "circle-stroke-width": 1,
          "circle-stroke-color": "#ffffff",
          "circle-stroke-opacity": 0.9,
        },
      });
    }
    if (!instance.getLayer("lakes-fill")) {
      instance.addLayer({
        id: "lakes-fill",
        type: "fill",
        source: "lakes",
        paint: { "fill-color": "#0ea5e9", "fill-opacity": 0.55, "fill-outline-color": "#0369a1" },
      });
    }
    if (!instance.getLayer("settlement-dot")) {
      instance.addLayer({
        id: "settlement-dot",
        type: "circle",
        source: "settlements",
        paint: {
          "circle-radius": 7,
          "circle-color": "#ffffff",
          "circle-stroke-width": 3,
          "circle-stroke-color": "#b31b28",
        },
      });
      instance.addLayer({
        id: "settlement-label",
        type: "symbol",
        source: "settlements",
        layout: {
          "text-field": ["get", "name"],
          "text-size": 12,
          "text-offset": [0, 1.4],
          "text-anchor": "top",
        },
        paint: { "text-halo-color": "#ffffff", "text-halo-width": 2, "text-color": "#0d1620" },
      });
    }
    if (!instance.getLayer("watched-dot")) {
      instance.addLayer({
        id: "watched-dot",
        type: "circle",
        source: "watched",
        paint: {
          "circle-radius": 9,
          "circle-color": "#f59e0b",
          "circle-stroke-width": 3,
          "circle-stroke-color": "#7c2d12",
        },
      });
    }

    for (const [layerId, visible] of [
      ["flood-fill", layers.flood],
      ["cell-circle", layers.cells],
      ["lakes-fill", layers.lakes],
      ["settlement-dot", layers.settlements],
      ["settlement-label", layers.settlements],
      ["watched-dot", layers.watched],
    ] as const) {
      if (instance.getLayer(layerId)) {
        instance.setLayoutProperty(layerId, "visibility", visible ? "visible" : "none");
      }
    }
  }, [ready, data, layers]);

  useEffect(() => {
    const instance = map.current;
    if (!instance || !ready) return;
    if (dimension === "3d") {
      if (!instance.getSource(TERRAIN_SOURCE)) {
        instance.addSource(TERRAIN_SOURCE, {
          type: "raster-dem",
          tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],
          tileSize: 256,
          encoding: "terrarium",
          maxzoom: 13,
        });
      }
      instance.setTerrain({ source: TERRAIN_SOURCE, exaggeration: 1.6 });
      instance.easeTo({ pitch: 62, bearing: -18, duration: 800 });
    } else {
      instance.setTerrain(null);
      instance.easeTo({ pitch: 0, bearing: 0, duration: 600 });
    }
  }, [dimension, ready]);

  useEffect(() => {
    const instance = map.current;
    if (!instance || !ready || !focus) return;
    instance.easeTo({ center: focus, zoom: 12.5, duration: 900 });
  }, [focus, ready]);

  useEffect(() => {
    const instance = map.current;
    if (!instance || !ready || !onSelect) return;
    const handler = (event: maplibregl.MapMouseEvent) => {
      const hits = instance.queryRenderedFeatures(event.point, {
        layers: ["settlement-dot", "watched-dot", "cell-circle"].filter((id) =>
          instance.getLayer(id),
        ),
      });
      const first = hits[0];
      if (!first?.properties) return;
      if (first.layer.id === "cell-circle") {
        const props = first.properties;
        const row = (label: string, value: string) =>
          `<div style="display:flex;justify-content:space-between;gap:14px"><span style="color:#71808f">${label}</span><b>${value}</b></div>`;
        const health = props.nearest_health_km;
        const helipad = props.nearest_helipad_km;
        new maplibregl.Popup({ closeButton: true, maxWidth: "268px" })
          .setLngLat(event.lngLat)
          .setHTML(
            `<div style="font:12px/1.6 system-ui;padding:2px 1px">
              <div style="font-weight:600;margin-bottom:5px">Corridor cell, 900 m</div>
              ${row("modelled peak rise", `${Number(props.peak_rise_m).toFixed(2)} m`)}
              ${row("residents", String(Math.round(Number(props.population))))}
              ${row("buildings destroyed or major", String(props.damaged_buildings))}
              ${row("bridges out within 5 km", `${props.bridges_out_5km} of ${Number(props.bridges_out_5km) + Number(props.bridges_standing_5km)}`)}
              ${helipad == null ? "" : row("nearest standing helipad", `${Number(helipad).toFixed(1)} km`)}
              ${health == null ? "" : row("nearest health facility", `${Number(health).toFixed(0)} km`)}
              ${Number(props.schools) ? row("schools", `${props.schools}, ${props.schools_destroyed} destroyed`) : ""}
              ${Number(props.hydropower_mw) ? row("hydropower exposed", `${props.hydropower_mw} MW`) : ""}
              <div style="margin-top:5px;padding-top:4px;border-top:1px solid #e6eaee;color:#71808f">triage priority ${Number(props.priority).toFixed(0)}</div>
            </div>`,
          )
          .addTo(instance);
        return;
      }
      onSelect(String(first.properties.name), String(first.properties.kind ?? "settlement"));
    };
    instance.on("click", handler);
    return () => {
      instance.off("click", handler);
    };
  }, [ready, onSelect]);

  return (
    <div className="relative overflow-hidden rounded-lg border" style={{ height }}>
      <div ref={container} className="h-full w-full" />
      {layers.cells ? (
        <div className="pointer-events-none absolute left-2 top-2 rounded-md border bg-white/92 px-3 py-2 shadow-card">
          <div className="text-[9.5px] font-semibold uppercase tracking-[0.07em] text-ink-faint">
            Priority score
          </div>
          <div className="mt-1.5 flex items-center gap-2">
            <span className="h-2 w-2 rounded-full" style={{ background: "#f6a740" }} />
            <span className="h-3 w-3 rounded-full" style={{ background: "#ef6f3c" }} />
            <span className="h-4 w-4 rounded-full" style={{ background: "#d93a4e" }} />
            <span className="h-5 w-5 rounded-full" style={{ background: "#b3123c" }} />
            <span className="ml-1 text-[10px] text-ink-muted">lower to higher</span>
          </div>
          <div className="mt-1 text-[9.5px] text-ink-faint">
            people at depth, observed damage, access loss
          </div>
        </div>
      ) : null}
      <div className="pointer-events-none absolute bottom-2 right-2 rounded border bg-white/90 px-2.5 py-1.5 text-[10px] text-ink-muted shadow-card">
        {dimension === "3d" ? "Terrain ×1.6 · AWS Terrarium" : "2D"} · DEM{" "}
        {data?.dem_vintage ?? " "}
      </div>
    </div>
  );
}
