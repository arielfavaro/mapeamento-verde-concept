import "leaflet/dist/leaflet.css";

import type { LatLng, LatLngBoundsExpression, Map as LeafletMap } from "leaflet";
import { type ReactNode, useEffect, useState } from "react";
import { GeoJSON, LayersControl, MapContainer, Rectangle, TileLayer, useMap, useMapEvents } from "react-leaflet";

import { urls } from "../api/client";
import type { BBox, Scene } from "../api/types";
import { bboxFromCorners, isValidBBox, toLatLngBounds } from "../lib/geo";

type Props = {
  aoi: BBox;
  drawing: boolean;
  footprints: Scene[];
  result: { jobId: string; layerId: string; opacity: number } | null;
  fitKey: string;
  fitBounds: BBox;
  overlay?: ReactNode;
  onMapReady: (map: LeafletMap) => void;
  onAoiDrawn: (aoi: BBox) => void;
};

const PORTO_FERREIRA: [number, number] = [-21.85, -47.44];

export function MapView(props: Props) {
  return (
    <div className="map-wrap">
      <MapContainer center={PORTO_FERREIRA} zoom={11} className="map" ref={(m) => {
          if (m) props.onMapReady(m);
        }}>
        <LayersControl position="topright">
          <LayersControl.BaseLayer checked name="Satélite (Esri)">
            <TileLayer
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
              attribution="Imagens &copy; Esri, Maxar, Earthstar Geographics"
              maxZoom={19}
            />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="OpenStreetMap">
            <TileLayer
              url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              maxZoom={19}
            />
          </LayersControl.BaseLayer>
        </LayersControl>

        {props.result && (
          <TileLayer
            key={`${props.result.jobId}-${props.result.layerId}`}
            url={urls.tile(props.result.jobId, props.result.layerId)}
            opacity={props.result.opacity}
            maxZoom={19}
            zIndex={10}
          />
        )}

        {props.footprints.map((s) => (
          <GeoJSON
            key={s.id}
            data={s.geometry}
            style={{ color: "#f5a623", weight: 1.5, fillOpacity: 0.05, dashArray: "4 4" }}
          />
        ))}

        {isValidBBox(props.aoi) && (
          <Rectangle bounds={toLatLngBounds(props.aoi)} pathOptions={{ color: "#ff3b30", weight: 2, fill: false }} />
        )}

        <DrawRectangle active={props.drawing} onDone={props.onAoiDrawn} />
        <FitBounds fitKey={props.fitKey} bounds={toLatLngBounds(props.fitBounds)} />
      </MapContainer>
      {props.overlay && <div className="map-overlay">{props.overlay}</div>}
      {props.drawing && <div className="map-hint">Clique e arraste para desenhar a área</div>}
    </div>
  );
}

/** Reenquadra o mapa sempre que `fitKey` muda (nova AOI escolhida ou resultado aberto). */
function FitBounds({ fitKey, bounds }: { fitKey: string; bounds: LatLngBoundsExpression }) {
  const map = useMap();
  useEffect(() => {
    const el = map.getContainer();
    const fit = () => {
      map.invalidateSize();
      map.fitBounds(bounds, { padding: [24, 24], maxZoom: 16 });
    };
    if (el.clientWidth > 0 && el.clientHeight > 0) {
      fit();
      return;
    }
    // Container ainda sem tamanho (aba em segundo plano, layout pendente): com tamanho zero o
    // Leaflet enquadraria no zoom máximo. Espera o container ganhar tamanho e então enquadra.
    const observer = new ResizeObserver(() => {
      if (el.clientWidth > 0 && el.clientHeight > 0) {
        observer.disconnect();
        fit();
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
    // reenquadra só quando a chave muda, não a cada novo array de bounds
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fitKey, map]);
  return null;
}

function DrawRectangle({ active, onDone }: { active: boolean; onDone: (b: BBox) => void }) {
  const [start, setStart] = useState<LatLng | null>(null);
  const [current, setCurrent] = useState<LatLng | null>(null);
  const map = useMapEvents({
    mousedown(e) {
      if (!active) return;
      map.dragging.disable();
      setStart(e.latlng);
      setCurrent(e.latlng);
    },
    mousemove(e) {
      if (start) setCurrent(e.latlng);
    },
    mouseup(e) {
      if (!start) return;
      map.dragging.enable();
      const bbox = bboxFromCorners(start, e.latlng);
      setStart(null);
      setCurrent(null);
      if (isValidBBox(bbox)) onDone(bbox);
    },
  });

  useEffect(() => {
    const container = map.getContainer();
    container.style.cursor = active ? "crosshair" : "";
  }, [active, map]);

  if (!start || !current) return null;
  return <Rectangle bounds={toLatLngBounds(bboxFromCorners(start, current))} pathOptions={{ color: "#ff3b30", dashArray: "6 4" }} />;
}
