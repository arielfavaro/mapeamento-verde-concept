"""Escolha da janela temporal.

Em vez de uma janela fixa de 30 dias, a janela começa no período pedido e é expandida
simetricamente até atingir a cobertura mínima de pixels válidos (ou o limite máximo).
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class Window:
    start: date
    end: date

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def expanded(self, days_each_side: int) -> "Window":
        delta = timedelta(days=days_each_side)
        return Window(self.start - delta, self.end + delta)


@dataclass(frozen=True)
class WindowAttempt:
    window: Window
    coverage: float
    scenes: int


def candidate_windows(base: Window, max_days: int, step_days: int) -> Iterator[Window]:
    """Gera a janela pedida e expansões sucessivas de ``step_days`` (metade para cada lado)."""
    if step_days <= 0:
        raise ValueError("step_days deve ser positivo")
    yield base
    grow = step_days // 2 or 1
    k = grow
    while base.expanded(k).days <= max_days:
        yield base.expanded(k)
        k += grow


def choose_window(
    base: Window,
    coverage_of: Callable[[Window], tuple[float, int]],
    target_coverage: float,
    max_days: int,
    step_days: int = 30,
) -> tuple[Window, list[WindowAttempt]]:
    """Retorna a primeira janela que atinge ``target_coverage``; senão, a de maior cobertura.

    ``coverage_of`` devolve (fração da AOI com ao menos uma observação válida, nº de cenas).
    """
    attempts: list[WindowAttempt] = []
    for window in candidate_windows(base, max(max_days, base.days), step_days):
        coverage, scenes = coverage_of(window)
        attempts.append(WindowAttempt(window, coverage, scenes))
        if coverage >= target_coverage:
            return window, attempts
    best = max(attempts, key=lambda a: (a.coverage, -a.window.days))
    return best.window, attempts
