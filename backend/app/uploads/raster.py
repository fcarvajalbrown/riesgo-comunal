import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np

MAX_PREVIEW_PIXELS = 2048
RAMP = np.array(
    [
        [68, 1, 84],
        [59, 82, 139],
        [33, 145, 140],
        [94, 201, 98],
        [253, 231, 37],
    ],
    dtype=np.float64,
)


class RasterError(ValueError):
    pass


@dataclass
class RasterPreview:
    png: bytes
    footprint: dict[str, Any]
    properties: dict[str, Any]


def _stretch(band: np.ndarray, valid: np.ndarray) -> np.ndarray:
    values = band[valid]
    if values.size == 0:
        return np.zeros(band.shape, dtype=np.float64)
    low, high = np.percentile(values, (2, 98))
    if high <= low:
        high = low + 1
    return np.clip((band.astype(np.float64) - low) / (high - low), 0, 1)


def _ramp(scaled: np.ndarray) -> np.ndarray:
    position = scaled * (len(RAMP) - 1)
    lower = np.floor(position).astype(int).clip(0, len(RAMP) - 2)
    fraction = (position - lower)[..., None]
    return RAMP[lower] * (1 - fraction) + RAMP[lower + 1] * fraction


def render_preview(data: bytes) -> RasterPreview:
    from rasterio.enums import Resampling
    from rasterio.errors import RasterioIOError
    from rasterio.io import MemoryFile
    from rasterio.warp import calculate_default_transform, reproject

    try:
        with MemoryFile(data) as memory, memory.open() as source:
            if source.crs is None:
                raise RasterError("El GeoTIFF no declara su sistema de coordenadas. Expórtelo con su proyección (por ejemplo UTM 18S o 19S).")
            transform, width, height = calculate_default_transform(source.crs, "EPSG:4326", source.width, source.height, *source.bounds)
            scale = max(width, height) / MAX_PREVIEW_PIXELS
            if scale > 1:
                width, height = int(width / scale), int(height / scale)
                transform = transform * transform.scale(scale, scale)
            band_count = min(source.count, 3) if source.count >= 3 else 1
            warped = np.zeros((band_count, height, width), dtype=np.float64)
            for index in range(band_count):
                reproject(
                    source=source.read(index + 1).astype(np.float64),
                    destination=warped[index],
                    src_transform=source.transform,
                    src_crs=source.crs,
                    src_nodata=source.nodata,
                    dst_transform=transform,
                    dst_crs="EPSG:4326",
                    dst_nodata=np.nan,
                    resampling=Resampling.bilinear,
                )
            properties = {
                "crs": source.crs.to_string(),
                "bands": source.count,
                "dtype": source.dtypes[0],
                "width": source.width,
                "height": source.height,
                "resolution": [abs(source.res[0]), abs(source.res[1])],
                "nodata": source.nodata,
            }
    except RasterioIOError as exc:
        raise RasterError(f"No se pudo leer el GeoTIFF: {exc}")

    valid = ~np.isnan(warped).any(axis=0)
    if not valid.any():
        raise RasterError("El GeoTIFF no tiene celdas con datos.")
    if band_count == 3:
        rgb = np.stack([_stretch(np.nan_to_num(b), valid) for b in warped], axis=-1) * 255
    else:
        single = np.nan_to_num(warped[0])
        rgb = _ramp(_stretch(single, valid))
        values = single[valid]
        properties["min"] = float(values.min())
        properties["max"] = float(values.max())
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    rgba[..., :3] = rgb.astype(np.uint8)
    rgba[..., 3] = np.where(valid, 210, 0)

    from rasterio.errors import NotGeoreferencedWarning

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", NotGeoreferencedWarning)
        with MemoryFile() as output:
            with output.open(driver="PNG", width=width, height=height, count=4, dtype="uint8") as png:
                png.write(np.moveaxis(rgba, -1, 0))
            png_bytes = output.read()

    west, north = transform * (0, 0)
    east, south = transform * (width, height)
    footprint = {"type": "Polygon", "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]]}
    properties["bounds"] = [west, south, east, north]
    return RasterPreview(png_bytes, footprint, properties)
