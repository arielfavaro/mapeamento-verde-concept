from rasterio.io import MemoryFile

from app.services.tiles import empty_tile
from tests.conftest import PF_AOI, wait_for

JOB = {"sensor": "sentinel-2", "aoi": PF_AOI, "aoi_name": "Porto Ferreira", "start": "2024-03-01", "end": "2024-03-31"}


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_sensors_have_explanations_and_indices(client):
    sensors = {s["id"]: s for s in client.get("/api/sensors").json()}
    assert set(sensors) == {"sentinel-2", "landsat", "hls", "sentinel-1"}
    assert "NDRE" in sensors["sentinel-2"]["indices"]
    assert "NDRE" not in sensors["landsat"]["indices"]
    assert sensors["sentinel-1"]["cloud_filterable"] is False
    for s in sensors.values():
        assert s["info"]["summary"] and s["info"]["strengths"] and s["info"]["limitations"]


def test_indices_include_legend_colors(client):
    ndvi = next(i for i in client.get("/api/indices").json() if i["id"] == "NDVI")
    assert len(ndvi["colors"]) == 11
    assert ndvi["colors"][0].startswith("#")


def test_presets(client):
    presets = client.get("/api/aoi-presets").json()
    assert presets[0]["id"] == "porto-ferreira"


def test_unknown_colormap_is_404(client):
    assert client.get("/api/colormaps/nao-existe").status_code == 404


def test_scene_search_groups_tiles_by_date(client, catalog):
    body = {**{k: JOB[k] for k in ("sensor", "aoi", "start", "end")}, "max_scene_cloud": 50}
    res = client.post("/api/scenes/search", json=body)
    assert res.status_code == 200
    data = res.json()
    assert data["total_scenes"] == 3
    assert [d["date"] for d in data["dates"]] == ["2024-03-05", "2024-03-15"]
    assert len(data["dates"][0]["scenes"]) == 2
    assert data["dates"][0]["scene_cloud_max"] == 7
    assert catalog.calls[0][3] == 50


def test_validation_error_is_422(client):
    bad = {**JOB, "start": "2024-04-01"}
    assert client.post("/api/jobs", json=bad).status_code == 422


def test_rejects_huge_aoi(client):
    huge = {**JOB, "aoi": {"west": -50, "south": -24, "east": -45, "north": -20}}
    assert client.post("/api/jobs", json=huge).status_code == 422


def test_job_lifecycle_download_and_tiles(client):
    res = client.post("/api/jobs", json=JOB)
    assert res.status_code == 202
    job = wait_for(client, res.json()["id"])
    assert job["state"] == "succeeded", job
    assert job["log"]

    name = job["result"]["files"][0]["name"]
    file_res = client.get(f"/api/jobs/{job['id']}/files/{name}")
    assert file_res.status_code == 200
    assert file_res.content[:4] in (b"II*\x00", b"MM\x00*")

    archive = client.get(f"/api/jobs/{job['id']}/archive.zip")
    assert archive.status_code == 200
    assert archive.content[:2] == b"PK"

    # tile z12 sobre Porto Ferreira
    tile = client.get(f"/api/jobs/{job['id']}/tiles/NDVI/12/1507/2299.png")
    assert tile.status_code == 200
    assert tile.content[:8] == b"\x89PNG\r\n\x1a\n"
    # tile longe da AOI: PNG transparente, sem erro
    assert client.get(f"/api/jobs/{job['id']}/tiles/NDVI/12/0/0.png").status_code == 200

    assert client.get(f"/api/jobs/{job['id']}/tiles/XYZ/12/0/0.png").status_code == 404
    assert len(client.get("/api/jobs").json()) == 1
    assert client.delete(f"/api/jobs/{job['id']}").status_code == 204
    assert client.get(f"/api/jobs/{job['id']}").status_code == 404


def test_files_outside_result_are_not_served(client):
    job = wait_for(client, client.post("/api/jobs", json=JOB).json()["id"])
    assert client.get(f"/api/jobs/{job['id']}/files/job.json").status_code == 404
    assert client.get(f"/api/jobs/{job['id']}/files/..%2F..%2Fsecret").status_code == 404


def test_invalid_job_id_is_404(client):
    assert client.get("/api/jobs/..%2Fetc").status_code == 404
    assert client.get("/api/jobs/" + "0" * 32).status_code == 404


def test_config_exposes_limits(client):
    cfg = client.get("/api/config").json()
    assert cfg["max_aoi_km2"] > 0
    assert cfg["target_crs"] == "EPSG:31983"


def test_openapi_is_served_under_api_prefix(client):
    assert client.get("/api/openapi.json").status_code == 200
    assert client.get("/api/docs").status_code == 200


def test_tile_outside_data_is_fully_transparent():
    empty_tile.cache_clear()
    with MemoryFile(empty_tile()) as mem, mem.open() as png:
        alpha = png.read(png.count)
    assert alpha.max() == 0
