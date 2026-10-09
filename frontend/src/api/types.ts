// Espelho dos schemas do backend (app/domain/models.py e app/api/schemas.py).

export type BBox = { west: number; south: number; east: number; north: number };

export type Band = { common: string; label: string; wavelength: string; resolution_m: number };

export type Sensor = {
  id: string;
  name: string;
  kind: "optical" | "radar";
  resolution_m: number;
  revisit: string;
  since: string;
  collections: string[];
  cloud_filterable: boolean;
  bands: Band[];
  indices: string[];
  info: {
    mission: string;
    summary: string;
    how_it_works: string;
    processing: string;
    strengths: string[];
    limitations: string[];
    best_for: string[];
  };
};

export type IndexClass = { min: number; max: number; label: string };

export type SpectralIndex = {
  id: string;
  name: string;
  category: string;
  formula: string;
  bands: string[];
  description: string;
  reference: string;
  colormap: string;
  colors: string[];
  vmin: number;
  vmax: number;
  unit: string;
  classes: IndexClass[];
};

export type AoiPreset = {
  id: string;
  name: string;
  bbox: [number, number, number, number];
  description: string;
  area_km2: number;
};

export type Scene = {
  id: string;
  collection: string;
  datetime: string;
  platform: string;
  tile: string;
  scene_cloud: number | null;
  geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon;
  preview_url: string | null;
};

export type AcquisitionDate = {
  date: string;
  scenes: Scene[];
  scene_cloud_max: number | null;
  aoi_valid_fraction: number | null;
};

export type SceneSearchRequest = {
  sensor: string;
  aoi: BBox;
  start: string;
  end: string;
  max_scene_cloud: number;
  estimate_aoi_cloud: boolean;
};

export type SceneSearchResponse = { sensor: string; total_scenes: number; dates: AcquisitionDate[] };

export type CompositeMethod = "median" | "best_date";

export type JobRequest = {
  sensor: string;
  aoi: BBox;
  aoi_name: string;
  start: string;
  end: string;
  method: CompositeMethod;
  max_scene_cloud: number;
  cloud_buffer_px: number;
  adaptive_window: boolean;
  target_coverage: number;
  max_window_days: number;
  scene_ids: string[] | null;
  indices: string[] | null;
  resolution_m: number | null;
};

export type JobState = "queued" | "running" | "succeeded" | "failed";

export type Layer = {
  id: string;
  name: string;
  kind: "composite" | "index" | "count";
  file: string;
  colormap: string | null;
  vmin: number;
  vmax: number;
  unit: string;
  bands: number[] | null;
};

export type ClassArea = { label: string; min: number; max: number; area_km2: number; fraction: number };

export type IndexStats = {
  valid_pixels: number;
  mean: number | null;
  std: number | null;
  percentiles: Record<string, number>;
  histogram: number[];
  histogram_edges: number[];
  classes: ClassArea[];
};

export type JobResult = {
  window_start: string;
  window_end: string;
  window_attempts: { start: string; end: string; coverage: number; scenes: number }[];
  acquisitions: { date: string; scene_ids: string[]; platforms: string[]; valid_fraction: number }[];
  coverage: number;
  crs: string;
  resolution_m: number;
  width: number;
  height: number;
  bounds_wgs84: [number, number, number, number];
  files: { name: string; description: string; size_bytes: number }[];
  layers: Layer[];
  stats: Record<string, IndexStats>;
  warnings: string[];
};

/** Item da listagem: sem resultado nem log (ver GET /api/jobs/{id} para o detalhe). */
export type JobSummary = {
  id: string;
  created_at: string;
  updated_at: string;
  state: JobState;
  progress: number;
  message: string;
  request: JobRequest;
  error: string | null;
};

export type Job = JobSummary & {
  result: JobResult | null;
  log: string[];
};

export type AppConfig = { version: string; max_aoi_km2: number; target_crs: string };

export type Colormap = { name: string; colors: string[] };
