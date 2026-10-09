"""Pipeline de um processamento: janela → cenas → máscara → composição → índices → arquivos."""

import csv
import json
import logging
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import dask
import numpy as np
import xarray as xr
from odc.geo.geobox import GeoBox

from app import __version__
from app.config import Settings
from app.domain.aoi import bbox_area_km2, slugify
from app.domain.errors import ProcessingError
from app.domain.indices import INDEX_BY_ID, available_indices, compute_index
from app.domain.models import (
    AcquisitionUsed,
    CompositeMethod,
    JobRequest,
    JobResult,
    Layer,
    LayerKind,
    OutputFile,
    WindowAttemptOut,
)
from app.domain.sensors import Sensor, get_sensor
from app.domain.windows import Window, WindowAttempt, choose_window
from app.services.catalog import FoundItem, SceneCatalog
from app.services.loader import (
    SourceStack,
    build_geobox,
    by_source,
    estimate_coverage,
    load_band,
    load_stack,
    monitor_read_failures,
)
from app.services.raster_io import write_cog
from app.services.stats import index_stats

log = logging.getLogger(__name__)

Reporter = Callable[[float, str], None]

WINDOW_STEP_DAYS = 30


@dataclass(frozen=True)
class _DatePlane:
    stack: int
    index: int
    stack_ref: SourceStack

    @property
    def group(self) -> list[FoundItem]:
        return self.stack_ref.groups[self.index]

    @property
    def valid_fraction(self) -> float:
        return self.stack_ref.valid_fraction[self.index]


def process_job(
    request: JobRequest,
    out_dir: Path,
    catalog: SceneCatalog,
    settings: Settings,
    report: Reporter,
) -> JobResult:
    sensor = get_sensor(request.sensor)
    bbox = request.aoi.as_tuple()
    area = bbox_area_km2(*bbox)
    if area > settings.max_aoi_km2:
        raise ProcessingError(f"AOI com {area:.0f} km² excede o limite de {settings.max_aoi_km2:.0f} km²")

    resolution = float(request.resolution_m or sensor.resolution_m)
    geobox = build_geobox(bbox, settings.target_crs, resolution)
    notes: list[str] = []

    report(0.02, "Buscando cenas no catálogo")
    window, attempts, items = _select_items(request, sensor, bbox, catalog, settings, resolution, report, notes)
    if not items:
        raise ProcessingError(
            "Nenhuma cena encontrada para o período. Amplie o período, aumente o limite de nuvem "
            "por cena, ative a janela adaptativa ou use HLS/Sentinel-1."
        )
    if len(items) > settings.max_scenes_per_job:
        items = sorted(items, key=lambda f: f.cloud if f.cloud is not None else 0)[: settings.max_scenes_per_job]
        items.sort(key=lambda f: f.item.datetime)
        notes.append(f"Limitado às {settings.max_scenes_per_job} cenas com menos nuvem.")

    with monitor_read_failures(items) as read_monitor:
        report(0.15, f"Lendo máscaras de nuvem de {len(items)} cenas")
        stacks = [load_stack(group, geobox, catalog.sign, request.cloud_buffer_px) for group in by_source(items)]
        planes = [_DatePlane(s, i, stack) for s, stack in enumerate(stacks) for i in range(len(stack.times))]
        if request.method is CompositeMethod.BEST_DATE:
            best = max(planes, key=lambda p: p.valid_fraction)
            planes = [best]
            notes.append(
                f"Melhor data: {best.stack_ref.times[best.index].date()} ({best.valid_fraction:.0%} da AOI limpa)."
            )

        composite, n_obs = _composite(sensor, stacks, planes, geobox, catalog, settings, report)

    if read_monitor.failures:
        failed_files = sorted(set(read_monitor.failures))
        files = len(failed_files)
        notes.append(
            f"{len(read_monitor.failures)} leitura(s) remota(s) falharam mesmo após novas tentativas "
            f"({files} arquivo(s)). Os pixels afetados ficaram sem a observação daquela data (veja a camada "
            "n_obs). Reprocessar costuma resolver."
        )
        log.warning("%d leituras remotas abandonadas: %s", len(read_monitor.failures), failed_files)

    coverage = float((n_obs > 0).mean())
    if coverage < request.target_coverage:
        notes.append(
            f"{1 - coverage:.1%} da AOI ficou sem nenhuma observação válida (NaN nos arquivos). "
            "Considere ampliar a janela ou usar HLS/Sentinel-1."
        )

    report(0.75, "Gravando GeoTIFFs")
    prefix = f"{sensor.id}_{slugify(request.aoi_name)}_{window.start:%Y%m%d}_{window.end:%Y%m%d}"
    band_names = [b.common for b in sensor.bands]
    tags = {"sensor": sensor.id, "window_start": str(window.start), "window_end": str(window.end)}
    composite_file = write_cog(
        out_dir / f"{prefix}_composicao.tif",
        [composite[b] for b in band_names],
        geobox,
        band_names,
        tags=tags,
    )
    nobs_file = write_cog(
        out_dir / f"{prefix}_n_obs.tif",
        [n_obs.astype(np.uint16)],
        geobox,
        ["n_obs"],
        dtype="uint16",
        nodata=None,
    )

    layers = _composite_layers(sensor, composite_file.name, band_names)
    layers.append(
        Layer(
            id="n_obs",
            name="Nº de observações válidas",
            kind=LayerKind.COUNT,
            file=nobs_file.name,
            colormap="viridis",
            vmin=0,
            vmax=float(max(1, int(n_obs.max()))),
        )
    )

    requested = request.indices or [i.id for i in available_indices(sensor.band_names)]
    stats = {}
    pixel_area = resolution * resolution
    for k, index_id in enumerate(requested):
        index = INDEX_BY_ID[index_id]
        report(0.78 + 0.17 * k / max(1, len(requested)), f"Calculando {index.name}")
        data = compute_index(index, composite)
        path = write_cog(out_dir / f"{prefix}_{index.id}.tif", [data], geobox, [index.id], tags=tags)
        stats[index.id] = index_stats(index, data, pixel_area)
        layers.append(
            Layer(
                id=index.id,
                name=index.name,
                kind=LayerKind.INDEX,
                file=path.name,
                colormap=index.colormap,
                vmin=index.vmin,
                vmax=index.vmax,
                unit=index.unit,
            )
        )

    report(0.96, "Gravando metadados")
    acquisitions = [
        AcquisitionUsed(
            date=p.stack_ref.times[p.index].date(),
            scene_ids=[f.item.id for f in p.group],
            platforms=sorted({f.platform for f in p.group}),
            valid_fraction=round(p.valid_fraction, 4),
        )
        for p in sorted(planes, key=lambda p: p.stack_ref.times[p.index])
    ]
    _write_scenes_csv(out_dir / f"{prefix}_cenas.csv", planes)

    west, south, east, north = geobox.extent.to_crs("EPSG:4326").boundingbox
    height, width = geobox.shape
    result = JobResult(
        window_start=window.start,
        window_end=window.end,
        window_attempts=[
            WindowAttemptOut(start=a.window.start, end=a.window.end, coverage=round(a.coverage, 4), scenes=a.scenes)
            for a in attempts
        ],
        acquisitions=acquisitions,
        coverage=round(coverage, 4),
        crs=settings.target_crs,
        resolution_m=resolution,
        width=width,
        height=height,
        bounds_wgs84=(west, south, east, north),
        files=[],
        layers=layers,
        stats=stats,
        warnings=notes,
    )
    _write_metadata(out_dir / f"{prefix}_metadados.json", request, result, settings)
    result.files = _list_files(out_dir, sensor, prefix)
    report(1.0, "Concluído")
    return result


def _select_items(
    request: JobRequest,
    sensor: Sensor,
    bbox: tuple[float, float, float, float],
    catalog: SceneCatalog,
    settings: Settings,
    resolution: float,
    report: Reporter,
    notes: list[str],
) -> tuple[Window, list[WindowAttempt], list[FoundItem]]:
    base = Window(request.start, request.end)

    if request.scene_ids:
        wanted = set(request.scene_ids)
        items = [f for f in catalog.search(sensor, bbox, base.start, base.end, None) if f.item.id in wanted]
        missing = wanted - {f.item.id for f in items}
        if missing:
            notes.append(f"{len(missing)} cena(s) selecionada(s) não encontrada(s) no período.")
        return base, [], items

    if not request.adaptive_window:
        return base, [], catalog.search(sensor, bbox, base.start, base.end, request.max_scene_cloud)

    coarse = build_geobox(bbox, settings.target_crs, max(settings.coverage_resolution_m, resolution))
    cache: dict[Window, list[FoundItem]] = {}

    def coverage_of(window: Window) -> tuple[float, int]:
        report(0.05, f"Avaliando janela {window.start} → {window.end} ({window.days} dias)")
        found = catalog.search(sensor, bbox, window.start, window.end, request.max_scene_cloud)
        cache[window] = found
        if not found:
            return 0.0, 0
        return estimate_coverage(found, coarse, catalog.sign).coverage, len(found)

    window, attempts = choose_window(
        base,
        coverage_of,
        request.target_coverage,
        request.max_window_days,
        WINDOW_STEP_DAYS,
    )
    if window != base:
        notes.append(f"Janela ampliada de {base.days} para {window.days} dias para atingir a cobertura.")
    return window, attempts, cache[window]


def _composite(
    sensor: Sensor,
    stacks: list[SourceStack],
    planes: list[_DatePlane],
    geobox: GeoBox,
    catalog: SceneCatalog,
    settings: Settings,
    report: Reporter,
) -> tuple[dict[str, np.ndarray], np.ndarray]:
    selected: dict[int, list[int]] = {}
    for p in planes:
        selected.setdefault(p.stack, []).append(p.index)

    composite: dict[str, np.ndarray] = {}
    n_obs: np.ndarray | None = None
    bands = [b.common for b in sensor.bands]
    for k, band in enumerate(bands):
        report(0.2 + 0.55 * k / len(bands), f"Compondo banda {band} ({len(planes)} datas)")
        parts = [
            load_band(stacks[s], band, geobox, catalog.sign, settings.chunk_size).isel(time=idx)
            for s, idx in sorted(selected.items())
        ]
        stack = xr.concat(parts, dim="time") if len(parts) > 1 else parts[0]
        median = stack.median("time", skipna=True)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            if n_obs is None:
                med, count = dask.compute(median, stack.count("time"))
                n_obs = np.asarray(count.values)
            else:
                (med,) = dask.compute(median)
        composite[band] = np.asarray(med.values, dtype=np.float32)
    assert n_obs is not None
    return composite, n_obs


def _composite_layers(sensor: Sensor, file: str, band_names: list[str]) -> list[Layer]:
    def pos(names: tuple[str, str, str]) -> list[int] | None:
        if all(n in band_names for n in names):
            return [band_names.index(n) + 1 for n in names]
        return None

    candidates = [
        ("rgb", "Cor natural", sensor.rgb, 0.0, 0.3),
        ("falsa_cor", "Falsa-cor vegetação (NIR/R/G)", sensor.false_color, 0.0, 0.45),
        ("swir", "Agricultura / queimada (SWIR2/NIR/R)", ("swir2", "nir", "red"), 0.0, 0.45),
    ]
    layers = []
    for layer_id, name, names, vmin, vmax in candidates:
        bands = pos(names) if names else None
        if bands:
            layers.append(
                Layer(id=layer_id, name=name, kind=LayerKind.COMPOSITE, file=file, vmin=vmin, vmax=vmax, bands=bands)
            )
    return layers


def _write_scenes_csv(path: Path, planes: list[_DatePlane]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["data", "cena", "colecao", "plataforma", "tile", "nuvem_cena_pct", "fracao_aoi_valida"])
        for p in sorted(planes, key=lambda p: p.stack_ref.times[p.index]):
            day = p.stack_ref.times[p.index].date()
            for f in p.group:
                writer.writerow(
                    [
                        day,
                        f.item.id,
                        f.source.collection,
                        f.platform,
                        f.tile,
                        "" if f.cloud is None else round(f.cloud, 2),
                        round(p.valid_fraction, 4),
                    ]
                )


def _write_metadata(path: Path, request: JobRequest, result: JobResult, settings: Settings) -> None:
    sensor = get_sensor(request.sensor)
    meta = {
        "gerado_em": datetime.now(UTC).isoformat(),
        "versao_software": __version__,
        "catalogo_stac": settings.stac_url,
        "satelite": sensor.name,
        "processamento": sensor.info.processing,
        "pedido": json.loads(request.model_dump_json()),
        "resultado": json.loads(result.model_dump_json(exclude={"files", "layers"})),
    }
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


_FILE_DESCRIPTIONS = {
    "composicao": "Composição multibanda (reflectância de superfície, float32, NaN = sem dado)",
    "n_obs": "Número de observações válidas por pixel",
    "cenas": "Lista das cenas usadas (CSV)",
    "metadados": "Metadados completos do processamento (JSON)",
}


def _list_files(out_dir: Path, sensor: Sensor, prefix: str) -> list[OutputFile]:
    files = []
    for path in sorted(out_dir.glob(f"{prefix}_*")):
        key = path.stem.removeprefix(prefix + "_")
        description = _FILE_DESCRIPTIONS.get(key)
        if description is None and key in INDEX_BY_ID:
            description = f"Índice {INDEX_BY_ID[key].name} ({INDEX_BY_ID[key].formula})"
        files.append(OutputFile(name=path.name, description=description or key, size_bytes=path.stat().st_size))
    return files
