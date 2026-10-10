import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from make_banner import RENDER_SIZE, SOURCES, make_logo, render_svg, silhouette

HERE = Path(__file__).resolve().parent

RED = (228, 40, 39)
DEEP = (214, 21, 42)
WHITE = (255, 255, 255)
NAVY_DEEP = (26, 43, 61)
PREVIEW_SIZE = (1200, 630)
TEXTURE_BAND = 280
MAP_BOX = (870, 60, 1170, 580)


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def navy_texture(source: Image.Image, size: tuple[int, int]) -> Image.Image:
    width, height = size
    band = source.resize((width, width), Image.LANCZOS).crop((0, 0, width, TEXTURE_BAND))
    flipped = band.transpose(Image.FLIP_TOP_BOTTOM)
    texture = Image.new("RGBA", size)
    for index in range(height // TEXTURE_BAND + 1):
        texture.paste(band if index % 2 == 0 else flipped, (0, index * TEXTURE_BAND))
    return texture


def preview(fonts: tuple[Path, Path], out: Path) -> None:
    regular, bold = fonts
    source = render_svg(SOURCES / "1.svg", RENDER_SIZE).convert("RGB")
    image = navy_texture(source, PREVIEW_SIZE)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 600, 1200, 630), fill=NAVY_DEEP)
    shape, mask = silhouette(source, MAP_BOX[3] - MAP_BOX[1])
    shape = shape.convert("RGBA")
    shape.putalpha(mask)
    shape.thumbnail((MAP_BOX[2] - MAP_BOX[0], MAP_BOX[3] - MAP_BOX[1]), Image.LANCZOS)
    image.alpha_composite(shape, ((MAP_BOX[0] + MAP_BOX[2] - shape.width) // 2, (MAP_BOX[1] + MAP_BOX[3] - shape.height) // 2))
    logo = make_logo(SOURCES / "4.svg")
    logo = logo.resize((round(logo.width * 150 / logo.height), 150), Image.LANCZOS)
    image.alpha_composite(logo, (64, 420))
    draw = ImageDraw.Draw(image)
    draw.text((64, 72), "Riesgo en mi comuna", font=font(bold, 76), fill=WHITE)
    draw.text((64, 166), "Región del Maule", font=font(bold, 52), fill=WHITE)
    draw.text((64, 256), "Alertas oficiales, mapa y pronóstico", font=font(regular, 34), fill=WHITE)
    draw.text((64, 300), "de las 30 comunas, en un solo lugar", font=font(regular, 34), fill=WHITE)
    text_x = 64 + logo.width + 36
    draw.text((text_x, 438), "Una iniciativa de la oficina de la", font=font(regular, 28), fill=WHITE)
    draw.text((text_x, 476), "senadora Paulina Vodanovic", font=font(bold, 32), fill=WHITE)
    draw.text((text_x, 536), "synterra.cl/maule", font=font(bold, 28), fill=WHITE)
    image.convert("RGB").save(out, "JPEG", quality=86, optimize=True, progressive=True)


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
    preview((args.regular_font, args.bold_font), args.out / "og-maule.jpg")
    icon(180, args.out / "icon-180.png")
    icon(32, args.out / "icon-32.png")
    print(f"preview and icons written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
