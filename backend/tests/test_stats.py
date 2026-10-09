import numpy as np
import pytest

from app.domain.indices import INDEX_BY_ID
from app.services.stats import HISTOGRAM_BINS, index_stats


def test_class_areas_sum_to_valid_area():
    data = np.array([[-0.2, 0.1, 0.3], [0.6, 0.8, np.nan]], dtype=np.float32)
    stats = index_stats(INDEX_BY_ID["NDVI"], data, pixel_area_m2=100.0)
    assert stats.valid_pixels == 5
    assert sum(c.fraction for c in stats.classes) == pytest.approx(1.0)
    assert sum(c.area_km2 for c in stats.classes) == pytest.approx(5 * 100 / 1e6)
    assert len(stats.histogram) == HISTOGRAM_BINS


def test_empty_data():
    stats = index_stats(INDEX_BY_ID["NDVI"], np.full((2, 2), np.nan), 100.0)
    assert stats.valid_pixels == 0
    assert stats.mean is None
