import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "backend"))

from app.db import get_engine, rows

RED = (228, 40, 39)
DEEP = (214, 21, 42)
WHITE = (255, 255, 255)
SCALE_X = 0.82


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def rings(geometry: dict) -> list[list[list[float]]]:
    polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    return [polygon[0] for polygon in polygons]


def draw_region(image: Image.Image, shapes: list[dict], box: tuple[int, int, int, int]) -> None:
    points = [(x * SCALE_X, y) for shape in shapes for ring in rings(shape) for x, y in ring]
    x0, x1 = min(p[0] for p in points), max(p[0] for p in points)
    y0, y1 = min(p[1] for p in points), max(p[1] for p in points)
    left, top, right, bottom = box
    scale = min((right - left) / (x1 - x0), (bottom - top) / (y1 - y0))
    offset_x = left + ((right - left) - (x1 - x0) * scale) / 2
    offset_y = top + ((bottom - top) - (y1 - y0) * scale) / 2
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for shape in shapes:
        for ring in rings(shape):
            xy = [(offset_x + (x * SCALE_X - x0) * scale, offset_y + (y1 - y) * scale) for x, y in ring]
            draw.polygon(xy, fill=(255, 255, 255, 60), outline=(255, 255, 255, 235), width=2)
    image.alpha_composite(overlay)


def preview(shapes: list[dict], fonts: tuple[Path, Path], out: Path) -> None:
    regular, bold = fonts
    image = Image.new("RGBA", (1200, 630), RED + (255,))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 600, 1200, 630), fill=DEEP)
    draw_region(image, shapes, (870, 60, 1170, 580))
    draw = ImageDraw.Draw(image)
    draw.text((64, 92), "Riesgo en mi comuna", font=font(bold, 76), fill=WHITE)
    draw.text((64, 186), "Región del Maule", font=font(bold, 52), fill=WHITE)
    draw.text((64, 276), "Alertas oficiales, mapa y pronóstico", font=font(regular, 34), fill=WHITE)
    draw.text((64, 320), "de las 30 comunas, en un solo lugar", font=font(regular, 34), fill=WHITE)
    draw.text((64, 452), "Una iniciativa de la oficina de la", font=font(regular, 30), fill=WHITE)
    draw.text((64, 492), "senadora Paulina Vodanovic", font=font(bold, 34), fill=WHITE)
    draw.text((64, 552), "synterra.cl/maule", font=font(bold, 28), fill=WHITE)
    image.convert("RGB").save(out, "PNG", optimize=True)


def icon(size: int, out: Path) -> None:
    big = 180
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    unit = big / 32
    draw.rounded_rectangle((0, 0, big - 1, big - 1), radius=6 * unit, fill=RED + (255,))
    draw.polygon([(16 * unit, 5 * unit), (29 * unit, 27 * unit), (3 * unit, 27 * unit)], fill=WHITE + (255,))
    draw.rectangle((14.5 * unit, 12 * unit, 17.5 * unit, 20 * unit), fill=RED + (255,))
    draw.rectangle((14.5 * unit, 22 * unit, 17.5 * unit, 25 * unit), fill=RED + (255,))
    image.resize((size, size), Image.LANCZOS).save(out, "PNG", optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the link preview image and PNG icons for the static site")
    parser.add_argument("--regular-font", type=Path, required=True)
    parser.add_argument("--bold-font", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=HERE / "vendor")
    args = parser.parse_args()
    with get_engine().connect() as conn:
        shapes = [
            json.loads(r["g"])
            for r in rows(conn, "select st_asgeojson(st_simplifypreservetopology(boundary, 0.003)) as g from municipality where cut_code like '07%'")
        ]
    preview(shapes, (args.regular_font, args.bold_font), args.out / "og-maule.png")
    icon(180, args.out / "icon-180.png")
    icon(32, args.out / "icon-32.png")
    print(f"preview and icons written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
