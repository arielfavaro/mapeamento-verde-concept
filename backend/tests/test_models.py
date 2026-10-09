import pytest
from pydantic import ValidationError

from app.domain.aoi import PRESETS, bbox_area_km2, slugify
from app.domain.models import BBox, JobRequest

PF = dict(zip(("west", "south", "east", "north"), PRESETS[0].bbox, strict=True))


def test_bbox_must_be_ordered():
    with pytest.raises(ValidationError):
        BBox(west=-47.3, south=-21.9, east=-47.5, north=-21.7)


def test_job_rejects_index_without_bands():
    with pytest.raises(ValidationError, match="NDRE"):
        JobRequest(sensor="landsat", aoi=PF, start="2024-01-01", end="2024-01-31", indices=["NDRE"])


def test_job_rejects_reversed_period():
    with pytest.raises(ValidationError):
        JobRequest(sensor="sentinel-2", aoi=PF, start="2024-02-01", end="2024-01-01")


def test_job_rejects_unknown_sensor():
    with pytest.raises(ValidationError):
        JobRequest(sensor="modis", aoi=PF, start="2024-01-01", end="2024-01-31")


def test_porto_ferreira_bbox_area():
    # retângulo de ~22,9 × 20,1 km
    assert bbox_area_km2(*PRESETS[0].bbox) == pytest.approx(460, rel=0.03)


def test_slugify():
    assert slugify("Porto Ferreira - SP") == "porto-ferreira-sp"
    assert slugify("???") == "aoi"
