from math import erf, log, sqrt
from statistics import median

EULER = 0.5772156649
SIGNIFICANCE = 0.05


def mann_kendall(values: list[float]) -> dict[str, float]:
    n = len(values)
    s = sum((values[j] > values[i]) - (values[j] < values[i]) for i in range(n - 1) for j in range(i + 1, n))
    ties: dict[float, int] = {}
    for v in values:
        ties[v] = ties.get(v, 0) + 1
    variance = (n * (n - 1) * (2 * n + 5) - sum(t * (t - 1) * (2 * t + 5) for t in ties.values())) / 18.0
    z = 0.0 if s == 0 or variance <= 0 else (s - 1 if s > 0 else s + 1) / sqrt(variance)
    p = 2.0 * (1.0 - 0.5 * (1.0 + erf(abs(z) / sqrt(2.0))))
    return {"s": s, "z": z, "p": p}


def sen_slope(years: list[int], values: list[float]) -> float:
    return median((values[j] - values[i]) / (years[j] - years[i]) for i in range(len(values) - 1) for j in range(i + 1, len(values)) if years[j] != years[i])


def l_moments(values: list[float]) -> tuple[float, float]:
    x = sorted(values)
    n = len(x)
    b0 = sum(x) / n
    b1 = sum(i * x[i] for i in range(n)) / (n * (n - 1))
    return b0, 2.0 * b1 - b0


def gumbel(values: list[float]) -> tuple[float, float]:
    l1, l2 = l_moments(values)
    scale = l2 / log(2.0)
    return l1 - EULER * scale, scale


def return_level(location: float, scale: float, years: float) -> float:
    return location - scale * log(-log(1.0 - 1.0 / years))


def thresholds(maxima: dict[int, float], present_year: int, periods: tuple[int, ...]) -> dict:
    years = sorted(maxima)
    values = [maxima[y] for y in years]
    trend = mann_kendall(values)
    slope = sen_slope(years, values) if trend["p"] < SIGNIFICANCE else 0.0
    adjusted = [v + slope * (present_year - y) for y, v in zip(years, values)]
    location, scale = gumbel(adjusted)
    return {
        "years": f"{years[0]}-{years[-1]}",
        "n": len(years),
        "mann_kendall_p": round(trend["p"], 4),
        "trend_m3s_per_year": round(slope, 3),
        "nonstationary": slope != 0.0,
        "present_year": present_year,
        "gumbel_location": round(location, 2),
        "gumbel_scale": round(scale, 2),
        "levels": {str(t): round(max(return_level(location, scale, t), 0.0), 2) for t in periods},
    }

