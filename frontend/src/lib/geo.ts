import type { BBox } from "../api/types";

const EARTH_RADIUS_KM = 6371.0088;
const rad = (deg: number) => (deg * Math.PI) / 180;

/** Área de um retângulo geográfico (mesma fórmula do backend). */
export function bboxAreaKm2(b: BBox): number {
  return EARTH_RADIUS_KM ** 2 * rad(b.east - b.west) * Math.abs(Math.sin(rad(b.north)) - Math.sin(rad(b.south)));
}

export function bboxFromTuple([west, south, east, north]: readonly [number, number, number, number]): BBox {
  return { west, south, east, north };
}

/** Normaliza dois cantos quaisquer em um bbox ordenado, arredondado a ~1 m. */
export function bboxFromCorners(a: { lat: number; lng: number }, b: { lat: number; lng: number }): BBox {
  const r = (v: number) => Math.round(v * 1e5) / 1e5;
  return {
    west: r(Math.min(a.lng, b.lng)),
    south: r(Math.min(a.lat, b.lat)),
    east: r(Math.max(a.lng, b.lng)),
    north: r(Math.max(a.lat, b.lat)),
  };
}

export function isValidBBox(b: BBox): boolean {
  return (
    b.west < b.east &&
    b.south < b.north &&
    b.west >= -180 &&
    b.east <= 180 &&
    b.south >= -90 &&
    b.north <= 90
  );
}

/** Formato [[sul, oeste], [norte, leste]] usado pelo Leaflet. */
export function toLatLngBounds(b: BBox): [[number, number], [number, number]] {
  return [
    [b.south, b.west],
    [b.north, b.east],
  ];
}
