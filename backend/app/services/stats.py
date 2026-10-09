"""Estatísticas descritivas e área por classe de interpretação de cada índice."""

import numpy as np

from app.domain.indices import SpectralIndex
from app.domain.models import IndexClassArea, IndexStats

HISTOGRAM_BINS = 40
PERCENTILES = (2, 25, 50, 75, 98)


def index_stats(index: SpectralIndex, data: np.ndarray, pixel_area_m2: float) -> IndexStats:
    values = data[np.isfinite(data)]
    n = int(values.size)
    edges = np.linspace(index.vmin, index.vmax, HISTOGRAM_BINS + 1)
    if n == 0:
        return IndexStats(
            valid_pixels=0,
            mean=None,
            std=None,
            percentiles={},
            histogram=[0] * HISTOGRAM_BINS,
            histogram_edges=edges.round(4).tolist(),
            classes=[],
        )

    hist, _ = np.histogram(np.clip(values, index.vmin, index.vmax), bins=edges)
    pct = np.percentile(values, PERCENTILES)
    classes = []
    for k, cls in enumerate(index.classes):
        last = k == len(index.classes) - 1
        upper = values <= cls.max if last else values < cls.max
        count = int(np.count_nonzero((values >= cls.min) & upper))
        classes.append(
            IndexClassArea(
                label=cls.label,
                min=cls.min,
                max=cls.max,
                area_km2=round(count * pixel_area_m2 / 1e6, 6),
                fraction=round(count / n, 4),
            )
        )
    return IndexStats(
        valid_pixels=n,
        mean=round(float(values.mean()), 4),
        std=round(float(values.std()), 4),
        percentiles={f"p{p}": round(float(v), 4) for p, v in zip(PERCENTILES, pct, strict=True)},
        histogram=hist.astype(int).tolist(),
        histogram_edges=edges.round(4).tolist(),
        classes=classes,
    )
