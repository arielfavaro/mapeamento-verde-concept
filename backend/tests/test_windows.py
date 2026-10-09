from datetime import date

import pytest

from app.domain.windows import Window, candidate_windows, choose_window

BASE = Window(date(2024, 3, 1), date(2024, 3, 30))


def test_candidate_windows_expand_symmetrically_until_limit():
    windows = list(candidate_windows(BASE, max_days=90, step_days=30))
    assert [w.days for w in windows] == [30, 60, 90]
    assert windows[1].start == date(2024, 2, 15)
    assert windows[1].end == date(2024, 4, 14)


def test_stops_at_first_window_reaching_target():
    coverage = {30: 0.4, 60: 0.99, 90: 1.0}
    chosen, attempts = choose_window(BASE, lambda w: (coverage[w.days], 3), 0.98, 120)
    assert chosen.days == 60
    assert len(attempts) == 2


def test_falls_back_to_best_coverage_preferring_shorter():
    coverage = {30: 0.5, 60: 0.8, 90: 0.8, 120: 0.7}
    chosen, attempts = choose_window(BASE, lambda w: (coverage[w.days], 1), 0.98, 120)
    assert chosen.days == 60
    assert len(attempts) == 4


def test_invalid_step():
    with pytest.raises(ValueError):
        list(candidate_windows(BASE, 90, 0))
