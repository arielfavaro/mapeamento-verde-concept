import numpy as np
import pytest

from app.domain.indices import INDEX_BY_ID, available_indices, compute_index, normalized_difference
from app.domain.sensors import SENSOR_BY_ID


def test_normalized_difference_known_values():
    nir = np.array([0.5, 0.3, 0.0], dtype=np.float32)
    red = np.array([0.1, 0.3, 0.0], dtype=np.float32)
    out = normalized_difference(nir, red)
    assert out[0] == pytest.approx(0.4 / 0.6)
    assert out[1] == 0
    assert np.isnan(out[2])  # denominador zero vira NaN, não infinito


def test_nan_propagates():
    out = normalized_difference(np.array([np.nan], dtype=np.float32), np.array([0.2], dtype=np.float32))
    assert np.isnan(out[0])


def test_ndvi_of_dense_vegetation_is_high():
    bands = {"nir": np.array([0.45]), "red": np.array([0.03])}
    assert compute_index(INDEX_BY_ID["NDVI"], bands)[0] > 0.8


def test_ndwi_of_water_is_positive():
    bands = {"green": np.array([0.08]), "nir": np.array([0.02])}
    assert compute_index(INDEX_BY_ID["NDWI"], bands)[0] > 0


def test_evi_matches_formula():
    b = {"nir": np.array([0.4]), "red": np.array([0.05]), "blue": np.array([0.03])}
    expected = 2.5 * (0.4 - 0.05) / (0.4 + 6 * 0.05 - 7.5 * 0.03 + 1)
    assert compute_index(INDEX_BY_ID["EVI"], b)[0] == pytest.approx(expected, rel=1e-5)


def test_radar_db_ignores_non_positive():
    out = compute_index(INDEX_BY_ID["VV_DB"], {"vv": np.array([0.1, 0.0])})
    assert out[0] == pytest.approx(-10.0)
    assert np.isnan(out[1])


def test_missing_band_raises():
    with pytest.raises(ValueError, match="rededge"):
        compute_index(INDEX_BY_ID["NDRE"], {"nir": np.array([0.4])})


@pytest.mark.parametrize(
    ("sensor", "present", "absent"),
    [
        ("sentinel-2", {"NDVI", "NDRE", "NBR", "MNDWI"}, {"RVI"}),
        ("landsat", {"NDVI", "NBR"}, {"NDRE", "RVI"}),
        ("hls", {"NDVI", "NDMI"}, {"NDRE"}),
        ("sentinel-1", {"RVI", "VV_DB", "CR"}, {"NDVI"}),
    ],
)
def test_available_indices_follow_sensor_bands(sensor, present, absent):
    ids = {i.id for i in available_indices(SENSOR_BY_ID[sensor].band_names)}
    assert present <= ids
    assert not (absent & ids)


def test_index_classes_are_ordered_and_contiguous():
    for index in INDEX_BY_ID.values():
        for a, b in zip(index.classes, index.classes[1:], strict=False):
            assert a.max == b.min, index.id
