from dataclasses import dataclass
from math import exp, log, sqrt

DMC_DAY_LENGTH_SOUTH = (11.5, 10.5, 9.2, 7.9, 6.8, 6.2, 6.5, 7.4, 8.7, 10.0, 11.2, 11.8)
DC_DAY_FACTOR_SOUTH = (6.4, 5.0, 2.4, 0.4, -1.6, -1.6, -1.6, -1.6, -1.6, 0.9, 3.8, 5.8)


@dataclass
class Codes:
    ffmc: float = 85.0
    dmc: float = 6.0
    dc: float = 15.0


def fine_fuel(temp: float, rh: float, wind: float, rain: float, previous: float) -> float:
    mo = 147.2 * (101.0 - previous) / (59.5 + previous)
    if rain > 0.5:
        rf = rain - 0.5
        wetting = 42.5 * rf * exp(-100.0 / (251.0 - mo)) * (1.0 - exp(-6.93 / rf))
        mo = mo + wetting + (0.0015 * (mo - 150.0) ** 2 * sqrt(rf) if mo > 150.0 else 0.0)
        mo = min(mo, 250.0)
    ed = 0.942 * rh**0.679 + 11.0 * exp((rh - 100.0) / 10.0) + 0.18 * (21.1 - temp) * (1.0 - exp(-0.115 * rh))
    if mo > ed:
        ko = 0.424 * (1.0 - (rh / 100.0) ** 1.7) + 0.0694 * sqrt(wind) * (1.0 - (rh / 100.0) ** 8)
        m = ed + (mo - ed) * 10.0 ** (-ko * 0.581 * exp(0.0365 * temp))
    else:
        ew = 0.618 * rh**0.753 + 10.0 * exp((rh - 100.0) / 10.0) + 0.18 * (21.1 - temp) * (1.0 - exp(-0.115 * rh))
        if mo < ew:
            k1 = 0.424 * (1.0 - ((100.0 - rh) / 100.0) ** 1.7) + 0.0694 * sqrt(wind) * (1.0 - ((100.0 - rh) / 100.0) ** 8)
            m = ew - (ew - mo) * 10.0 ** (-k1 * 0.581 * exp(0.0365 * temp))
        else:
            m = mo
    return min(max(59.5 * (250.0 - m) / (147.2 + m), 0.0), 101.0)


def duff_moisture(temp: float, rh: float, rain: float, previous: float, month: int) -> float:
    temp = max(temp, -1.1)
    drying = 1.894 * (temp + 1.1) * (100.0 - rh) * DMC_DAY_LENGTH_SOUTH[month - 1] * 1e-4
    if rain > 1.5:
        re = 0.92 * rain - 1.27
        mo = 20.0 + exp(5.6348 - previous / 43.43)
        if previous <= 33.0:
            b = 100.0 / (0.5 + 0.3 * previous)
        elif previous <= 65.0:
            b = 14.0 - 1.3 * log(previous)
        else:
            b = 6.2 * log(previous) - 17.2
        mr = mo + 1000.0 * re / (48.77 + b * re)
        previous = max(244.72 - 43.43 * log(mr - 20.0), 0.0)
    return previous + drying


def drought(temp: float, rain: float, previous: float, month: int) -> float:
    temp = max(temp, -2.8)
    drying = max((0.36 * (temp + 2.8) + DC_DAY_FACTOR_SOUTH[month - 1]) / 2.0, 0.0)
    if rain > 2.8:
        rd = 0.83 * rain - 1.27
        qr = 800.0 * exp(-previous / 400.0) + 3.937 * rd
        previous = max(400.0 * log(800.0 / qr), 0.0)
    return previous + drying


def initial_spread(ffmc: float, wind: float) -> float:
    m = 147.2 * (101.0 - ffmc) / (59.5 + ffmc)
    return 0.208 * exp(0.05039 * wind) * 91.9 * exp(-0.1386 * m) * (1.0 + m**5.31 / 4.93e7)


def buildup(dmc: float, dc: float) -> float:
    if dmc == 0.0 and dc == 0.0:
        return 0.0
    if dmc <= 0.4 * dc:
        value = 0.8 * dmc * dc / (dmc + 0.4 * dc)
    else:
        value = dmc - (1.0 - 0.8 * dc / (dmc + 0.4 * dc)) * (0.92 + (0.0114 * dmc) ** 1.7)
    return max(value, 0.0)


def fire_weather(isi: float, bui: float) -> float:
    fd = 0.626 * bui**0.809 + 2.0 if bui <= 80.0 else 1000.0 / (25.0 + 108.64 * exp(-0.023 * bui))
    b = 0.1 * isi * fd
    return exp(2.72 * (0.434 * log(b)) ** 0.647) if b > 1.0 else b


def step(codes: Codes, temp: float, rh: float, wind: float, rain: float, month: int) -> float:
    rh = min(max(rh, 0.0), 100.0)
    codes.ffmc = fine_fuel(temp, rh, wind, rain, codes.ffmc)
    codes.dmc = duff_moisture(temp, rh, rain, codes.dmc, month)
    codes.dc = drought(temp, rain, codes.dc, month)
    return fire_weather(initial_spread(codes.ffmc, wind), buildup(codes.dmc, codes.dc))
