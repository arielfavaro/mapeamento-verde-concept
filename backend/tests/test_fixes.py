"""Regressões encontradas nos logs do container."""

import logging
import warnings
from datetime import UTC, datetime

import numpy as np
import pystac

from app.domain.models import Layer, LayerKind
from app.logging_config import HealthCheckFilter
from app.services.catalog import FoundItem
from app.services.loader import build_geobox, monitor_read_failures
from app.services.raster_io import write_cog
from app.services.tiles import render_tile
from tests.conftest import JOB_SENSOR, PF_BBOX, make_item, wait_for

PF_AOI_JOB = {
    "sensor": "sentinel-2",
    "aoi": dict(zip(("west", "south", "east", "north"), PF_BBOX, strict=True)),
    "start": "2024-03-01",
    "end": "2024-03-31",
}


def test_tile_with_nodata_renders_without_runtime_warning(tmp_path):
    geobox = build_geobox(PF_BBOX, "EPSG:31983", 500)
    data = np.full(geobox.shape, 0.5, dtype=np.float32)
    data[:10, :10] = np.nan  # NoData = NaN, como nos índices reais
    path = write_cog(tmp_path / "ndvi.tif", [data], geobox, ["NDVI"])
    layer = Layer(id="NDVI", name="NDVI", kind=LayerKind.INDEX, file=path.name, colormap="rdylgn", vmin=-0.1, vmax=0.85)
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        assert render_tile(path, layer, 12, 1507, 2302)[:4] == b"\x89PNG"


def _emit_read_failure(uri: str) -> None:
    logging.getLogger("odc.loader._rio").warning("Ignoring read failure while reading: %s:%d", uri, 1)


def test_read_failures_of_this_job_are_recorded():
    item = make_item("A", datetime(2024, 3, 5, tzinfo=UTC))
    item.add_asset("B04", pystac.Asset("https://blob.example/B04.tif"))
    found = [FoundItem(JOB_SENSOR.sources[0], item)]
    with monitor_read_failures(found) as monitor:
        _emit_read_failure("https://blob.example/B04.tif?sig=abc")  # URL assinada da mesma cena
        _emit_read_failure("https://blob.example/OUTRO.tif?sig=abc")  # cena de outro job
    _emit_read_failure("https://blob.example/B04.tif")  # depois do job: não conta
    assert monitor.failures == ["https://blob.example/B04.tif"]


def test_health_check_is_dropped_from_access_log():
    filt = HealthCheckFilter()

    def record(path: str) -> logging.LogRecord:
        return logging.LogRecord(
            "uvicorn.access",
            logging.INFO,
            "",
            0,
            '%s - "%s %s HTTP/%s" %d',
            ("127.0.0.1:1", "GET", path, "1.1", 200),
            None,
        )

    assert filt.filter(record("/api/health")) is False
    assert filt.filter(record("/api/jobs")) is True


def test_job_list_is_lightweight(client):
    job = wait_for(client, client.post("/api/jobs", json=PF_AOI_JOB).json()["id"])
    assert job["result"] is not None
    listed = client.get("/api/jobs").json()[0]
    assert "result" not in listed and "log" not in listed
    assert listed["state"] == "succeeded"
