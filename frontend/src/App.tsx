import type { Map as LeafletMap } from "leaflet";
import { type ReactNode, useMemo, useRef, useState } from "react";

import {
  useColormap,
  useConfig,
  useCreateJob,
  useDeleteJob,
  useIndices,
  useJob,
  useJobs,
  usePresets,
  useSceneSearch,
  useSensors,
} from "./api/queries";
import type { BBox, JobRequest } from "./api/types";
import { AreaPeriodForm } from "./components/AreaPeriodForm";
import { Guide } from "./components/Guide";
import { JobDetail } from "./components/JobDetail";
import { JobList } from "./components/JobList";
import { Legend } from "./components/Legend";
import { MapView } from "./components/MapView";
import { ProcessForm, type ProcessOptions } from "./components/ProcessForm";
import { SceneSearch } from "./components/SceneSearch";
import { SensorPicker } from "./components/SensorPicker";
import { monthRange } from "./lib/format";
import { bboxFromCorners, bboxFromTuple } from "./lib/geo";

type Tab = "processar" | "resultados" | "guia";

// Usado até os presets chegarem da API (mesmo retângulo do backend).
const FALLBACK_AOI: BBox = { west: -47.5546664, south: -21.935324, east: -47.3343908, north: -21.7547284 };

function defaultPeriod() {
  const now = new Date();
  const year = now.getMonth() === 0 ? now.getFullYear() - 1 : now.getFullYear();
  const month = now.getMonth() === 0 ? 12 : now.getMonth();
  return monthRange(year, month);
}

export default function App() {
  const config = useConfig();
  const sensors = useSensors();
  const indices = useIndices();
  const presets = usePresets();
  const jobs = useJobs();

  const [tab, setTab] = useState<Tab>("processar");
  const [sensorId, setSensorId] = useState("sentinel-2");
  const [aoiOverride, setAoiOverride] = useState<BBox | null>(null);
  const [aoiName, setAoiName] = useState("Porto Ferreira");
  const [period, setPeriod] = useState(defaultPeriod);
  const [drawing, setDrawing] = useState(false);
  const [fitKey, setFitKey] = useState("inicio");

  const [maxSceneCloud, setMaxSceneCloud] = useState(80);
  const [estimateAoiCloud, setEstimateAoiCloud] = useState(true);
  const search = useSceneSearch();
  const [selectedDates, setSelectedDates] = useState<Set<string>>(new Set());
  const [hoverDate, setHoverDate] = useState<string | null>(null);

  const [options, setOptions] = useState<Omit<ProcessOptions, "indices" | "resolutionM">>({
    method: "median",
    adaptiveWindow: true,
    targetCoverage: 0.98,
    maxWindowDays: 120,
    cloudBufferPx: 2,
    onlySelected: true,
  });
  const [indicesBySensor, setIndicesBySensor] = useState<Record<string, string[]>>({});
  const [resolutionBySensor, setResolutionBySensor] = useState<Record<string, number>>({});

  const createJob = useCreateJob();
  const deleteJob = useDeleteJob();
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const activeJob = useJob(activeJobId);
  const [layerByJob, setLayerByJob] = useState<Record<string, string>>({});
  const [opacity, setOpacity] = useState(0.9);

  const mapRef = useRef<LeafletMap | null>(null);

  const sensor = sensors.data?.find((s) => s.id === sensorId);
  const defaultAoi = presets.data?.[0] ? bboxFromTuple(presets.data[0].bbox) : FALLBACK_AOI;
  const aoi = aoiOverride ?? defaultAoi;
  const sensorIndices = indicesBySensor[sensorId] ?? sensor?.indices ?? [];
  const resolution = resolutionBySensor[sensorId] ?? sensor?.resolution_m ?? 10;

  const result = activeJob.data?.result ?? null;
  const activeLayerId = activeJobId
    ? (layerByJob[activeJobId] ?? result?.layers.find((l) => l.kind === "index")?.id ?? result?.layers[0]?.id ?? null)
    : null;
  const activeLayer = result?.layers.find((l) => l.id === activeLayerId);
  const activeIndex = indices.data?.find((i) => i.id === activeLayerId);
  const countColors = useColormap(activeLayer?.kind === "count" ? (activeLayer.colormap ?? null) : null);

  const footprints = useMemo(() => {
    const dates = search.data?.dates ?? [];
    const shown = hoverDate ? [hoverDate] : [...selectedDates];
    return dates.filter((d) => shown.includes(d.date)).flatMap((d) => d.scenes);
  }, [search.data, hoverDate, selectedDates]);

  const resetSearch = () => {
    search.reset();
    setSelectedDates(new Set());
  };

  const changeAoi = (next: BBox, name?: string) => {
    setAoiOverride(next);
    if (name) setAoiName(name);
    setFitKey(`aoi-${Date.now()}`);
    resetSearch();
  };

  const runSearch = () =>
    search.mutate({
      sensor: sensorId,
      aoi,
      start: period.start,
      end: period.end,
      max_scene_cloud: maxSceneCloud,
      estimate_aoi_cloud: estimateAoiCloud && (sensor?.cloud_filterable ?? false),
    });

  const selectJob = (id: string) => {
    setActiveJobId(id);
    setFitKey(`job-${id}`);
  };

  const submitJob = () => {
    const manual = options.onlySelected && selectedDates.size > 0;
    const sceneIds = manual
      ? (search.data?.dates ?? []).filter((d) => selectedDates.has(d.date)).flatMap((d) => d.scenes.map((s) => s.id))
      : null;
    const body: JobRequest = {
      sensor: sensorId,
      aoi,
      aoi_name: aoiName || "AOI",
      start: period.start,
      end: period.end,
      method: options.method,
      max_scene_cloud: maxSceneCloud,
      cloud_buffer_px: options.cloudBufferPx,
      adaptive_window: options.adaptiveWindow && !manual,
      target_coverage: options.targetCoverage,
      max_window_days: Math.max(options.maxWindowDays, 1),
      scene_ids: sceneIds,
      indices: sensorIndices,
      resolution_m: resolution,
    };
    createJob.mutate(body, {
      onSuccess: (job) => {
        selectJob(job.id);
        setTab("resultados");
      },
    });
  };

  const fitBounds = result && fitKey.startsWith("job-") ? bboxFromTuple(result.bounds_wgs84) : aoi;
  const loadingError = sensors.error ?? indices.error;

  return (
    <div className="app">
      <aside className="sidebar">
        <header className="brand">
          <img className="brand-mark" src="/favicon.svg" alt="" width={36} height={36} />
          <div>
            <h1>Mapeamento Verde</h1>
            <p className="brand-sub">Imagens de satélite sem nuvem e índices espectrais</p>
          </div>
        </header>
        <nav className="tabs" role="tablist">
          {(
            [
              ["processar", "Processar"],
              ["resultados", `Resultados${jobs.data?.length ? ` (${jobs.data.length})` : ""}`],
              ["guia", "Guia"],
            ] as const
          ).map(([id, label]) => (
            <button key={id} role="tab" aria-selected={tab === id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>
              {label}
            </button>
          ))}
        </nav>

        <div className="sidebar-body">
          {loadingError && <p className="error-box">Não foi possível falar com a API: {loadingError.message}</p>}

          {tab === "processar" && sensors.data && indices.data && sensor && (
            <>
              <Step n={1} title="Satélite">
                <SensorPicker
                  sensors={sensors.data}
                  selectedId={sensorId}
                  onSelect={(id) => {
                    setSensorId(id);
                    resetSearch();
                  }}
                />
              </Step>
              <Step n={2} title="Área e período">
                <AreaPeriodForm
                  presets={presets.data ?? []}
                  maxAreaKm2={config.data?.max_aoi_km2 ?? 2500}
                  aoi={aoi}
                  aoiName={aoiName}
                  start={period.start}
                  end={period.end}
                  drawing={drawing}
                  onAoiChange={changeAoi}
                  onAoiNameChange={setAoiName}
                  onPeriodChange={(start, end) => {
                    setPeriod({ start, end });
                    resetSearch();
                  }}
                  onToggleDrawing={() => setDrawing((d) => !d)}
                  onUseVisibleExtent={() => {
                    const b = mapRef.current?.getBounds();
                    if (b) changeAoi(bboxFromCorners(b.getSouthWest(), b.getNorthEast()));
                  }}
                />
              </Step>
              <Step n={3} title="Cenas disponíveis (opcional)">
                <SceneSearch
                  sensor={sensor}
                  maxSceneCloud={maxSceneCloud}
                  estimateAoiCloud={estimateAoiCloud}
                  result={search.data}
                  loading={search.isPending}
                  error={search.error?.message ?? null}
                  selected={selectedDates}
                  onMaxSceneCloudChange={setMaxSceneCloud}
                  onEstimateChange={setEstimateAoiCloud}
                  onSearch={runSearch}
                  onToggleDate={(d) =>
                    setSelectedDates((prev) => {
                      const next = new Set(prev);
                      if (next.has(d)) next.delete(d);
                      else next.add(d);
                      return next;
                    })
                  }
                  onSelectDates={(ds) => setSelectedDates(new Set(ds))}
                  onHoverDate={setHoverDate}
                />
              </Step>
              <Step n={4} title="Processamento">
                <ProcessForm
                  sensor={sensor}
                  indices={indices.data}
                  options={{ ...options, indices: sensorIndices, resolutionM: resolution }}
                  selectedDates={selectedDates.size}
                  submitting={createJob.isPending}
                  error={createJob.error?.message ?? null}
                  onChange={({ indices: idx, resolutionM, ...rest }) => {
                    if (idx) setIndicesBySensor((m) => ({ ...m, [sensorId]: idx }));
                    if (resolutionM) setResolutionBySensor((m) => ({ ...m, [sensorId]: resolutionM }));
                    setOptions((o) => ({ ...o, ...rest }));
                  }}
                  onSubmit={submitJob}
                />
              </Step>
            </>
          )}

          {tab === "resultados" && (
            <>
              <JobList jobs={jobs.data ?? []} sensors={sensors.data ?? []} activeId={activeJobId} onSelect={selectJob} />
              {activeJob.data && (
                <JobDetail
                  job={activeJob.data}
                  indices={indices.data ?? []}
                  activeLayerId={activeLayerId}
                  opacity={opacity}
                  deleting={deleteJob.isPending}
                  onLayerChange={(id) => activeJobId && setLayerByJob((m) => ({ ...m, [activeJobId]: id }))}
                  onOpacityChange={setOpacity}
                  onDelete={() =>
                    activeJobId &&
                    deleteJob.mutate(activeJobId, {
                      onSuccess: () => setActiveJobId(null),
                    })
                  }
                />
              )}
            </>
          )}

          {tab === "guia" && sensors.data && indices.data && <Guide sensors={sensors.data} indices={indices.data} />}
        </div>
      </aside>

      <main className="main">
        <MapView
          aoi={aoi}
          drawing={drawing}
          footprints={footprints}
          result={result && activeJobId && activeLayerId ? { jobId: activeJobId, layerId: activeLayerId, opacity } : null}
          fitKey={fitKey}
          fitBounds={fitBounds}
          onMapReady={(m) => {
            mapRef.current = m;
          }}
          onAoiDrawn={(b) => {
            setDrawing(false);
            changeAoi(b, aoiName);
          }}
          overlay={
            activeLayer && (
              <Legend layer={activeLayer} index={activeIndex} colors={activeIndex?.colors ?? countColors.data?.colors} />
            )
          }
        />
      </main>
    </div>
  );
}

function Step({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <section className="step">
      <h2>
        <span className="step-n">{n}</span>
        {title}
      </h2>
      {children}
    </section>
  );
}
