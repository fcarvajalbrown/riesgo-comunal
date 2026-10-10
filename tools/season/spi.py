from math import exp, lgamma, log, sqrt
from statistics import NormalDist

EPSILON = 1e-10
LIMIT = 1e-6


def lower_regularized_gamma(a: float, x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x < a + 1.0:
        term = total = 1.0 / a
        n = a
        for _ in range(500):
            n += 1.0
            term *= x / n
            total += term
            if abs(term) < abs(total) * EPSILON:
                break
        return total * exp(-x + a * log(x) - lgamma(a))
    b = x + 1.0 - a
    c = 1.0 / 1e-300
    d = 1.0 / b
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < EPSILON:
            break
    return 1.0 - exp(-x + a * log(x) - lgamma(a)) * h


def fit(totals: list[float]) -> dict[str, float]:
    wet = [t for t in totals if t > 0.0]
    zero = 1.0 - len(wet) / len(totals)
    if len(wet) < 2:
        return {"alpha": 0.0, "beta": 0.0, "zero": zero}
    mean = sum(wet) / len(wet)
    a = log(mean) - sum(log(t) for t in wet) / len(wet)
    if a <= 0.0:
        return {"alpha": 0.0, "beta": 0.0, "zero": zero}
    alpha = (1.0 + sqrt(1.0 + 4.0 * a / 3.0)) / (4.0 * a)
    return {"alpha": alpha, "beta": mean / alpha, "zero": zero}


def index(total: float, params: dict[str, float]) -> float | None:
    if params["alpha"] <= 0.0:
        return None
    probability = params["zero"] + (1.0 - params["zero"]) * lower_regularized_gamma(params["alpha"], total / params["beta"])
    return NormalDist().inv_cdf(min(max(probability, LIMIT), 1.0 - LIMIT))
