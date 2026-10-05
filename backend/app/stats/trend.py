import math
from dataclasses import dataclass

MIN_YEARS_FOR_TREND = 10
ALPHA = 0.05


@dataclass(frozen=True)
class TrendResult:
    n: int
    s: int
    z: float | None
    p_value: float | None
    conclusion: str
    statement: str


def mann_kendall(values: list[float]) -> TrendResult:
    n = len(values)
    if n < MIN_YEARS_FOR_TREND:
        return TrendResult(
            n,
            0,
            None,
            None,
            "insufficient",
            f"Con {n} años de datos no es posible evaluar una tendencia (se requieren al menos {MIN_YEARS_FOR_TREND}).",
        )
    s = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            s += (values[j] > values[i]) - (values[j] < values[i])
    counts: dict[float, int] = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    ties = sum(t * (t - 1) * (2 * t + 5) for t in counts.values() if t > 1)
    variance = (n * (n - 1) * (2 * n + 5) - ties) / 18
    if variance <= 0:
        return TrendResult(n, s, None, None, "no_trend", "Los valores no varían; no hay tendencia que evaluar.")
    if s > 0:
        z = (s - 1) / math.sqrt(variance)
    elif s < 0:
        z = (s + 1) / math.sqrt(variance)
    else:
        z = 0.0
    p = math.erfc(abs(z) / math.sqrt(2))
    if p < ALPHA:
        direction = "creciente" if z > 0 else "decreciente"
        return TrendResult(
            n, s, z, p, direction, f"Tendencia {direction} estadísticamente significativa (Mann-Kendall, p = {p:.3f}, n = {n} años)."
        )
    return TrendResult(n, s, z, p, "no_trend", f"No se detecta una tendencia estadísticamente significativa (Mann-Kendall, p = {p:.3f}, n = {n} años).")
