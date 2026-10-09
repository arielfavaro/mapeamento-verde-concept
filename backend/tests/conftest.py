import time
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import pystac
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.domain.models import JobRequest, JobResult, Layer, LayerKind, OutputFile
from app.domain.sensors import SENTINEL_2, Sensor
from app.main import create_app
from app.services.catalog import FoundItem
from app.services.loader import build_geobox
from app.services.raster_io import write_cog

PF_BBOX = (-47.5546664, -21.935324, -47.3343908, -21.7547284)
JOB_SENSOR = SENTINEL_2
PF_AOI = dict(zip(("west", "south", "east", "north"), PF_BBOX, strict=True))


def make_item(item_id: str, when: datetime, cloud: float = 5.0, tile: str = "23KKS") -> pystac.Item:
    w, s, e, n = PF_BBOX
    geom = {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}
    item = pystac.Item(
        item_id, geom, list(PF_BBOX), when, {"eo:cloud_cover": cloud, "platform": "Sentinel-2B", "s2:mgrs_tile": tile}
    )
    item.add_asset("rendered_preview", pystac.Asset("https://example.com/preview.png"))
    return item


class FakeCatalog:
    def __init__(self) -> None:
        self.calls: list[tuple[str, date, date, float | None]] = []

    def search(self, sensor: Sensor, bbox, start, end, max_scene_cloud):
        self.calls.append((sensor.id, start, end, max_scene_cloud))
        source = sensor.sources[0]
        return [
            FoundItem(source, make_item("A", datetime(2024, 3, 5, 13, 22, tzinfo=UTC), 3, "23KKS")),
            FoundItem(source, make_item("B", datetime(2024, 3, 5, 13, 22, tzinfo=UTC), 7, "22KHA")),
            FoundItem(source, make_item("C", datetime(2024, 3, 15, 13, 22, tzinfo=UTC), 40, "23KKS")),
        ]

    def sign(self, href: str) -> str:
        return href


def fake_process(request: JobRequest, out_dir: Path, report) -> JobResult:
    """Simula o pipeline gravando um COG pequeno de verdade (permite testar os tiles)."""
    report(0.5, "processando")
    geobox = build_geobox(request.aoi.as_tuple(), "EPSG:31983", 500)
    ndvi = np.linspace(-0.1, 0.9, geobox.shape[0] * geobox.shape[1], dtype=np.float32).reshape(geobox.shape)
    path = write_cog(out_dir / "teste_NDVI.tif", [ndvi], geobox, ["NDVI"])
    return JobResult(
        window_start=request.start,
        window_end=request.end,
        window_attempts=[],
        acquisitions=[],
        coverage=1.0,
        crs="EPSG:31983",
        resolution_m=500,
        width=geobox.shape[1],
        height=geobox.shape[0],
        bounds_wgs84=PF_BBOX,
        stats={},
        files=[OutputFile(name=path.name, description="NDVI", size_bytes=path.stat().st_size)],
        layers=[
            Layer(id="NDVI", name="NDVI", kind=LayerKind.INDEX, file=path.name, colormap="rdylgn", vmin=-0.1, vmax=0.85)
        ],
    )


@pytest.fixture
def catalog() -> FakeCatalog:
    return FakeCatalog()


@pytest.fixture
def client(tmp_path, catalog):
    settings = Settings(storage_dir=tmp_path)
    app = create_app(settings, catalog=catalog, process=fake_process)
    with TestClient(app) as c:
        yield c


def wait_for(client: TestClient, job_id: str, timeout: float = 10.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["state"] in ("succeeded", "failed"):
            return job
        time.sleep(0.05)
    raise TimeoutError(job_id)
