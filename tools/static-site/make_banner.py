import argparse
import base64
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
SOURCES = HERE.parents[1] / "assets" / "graficas-vodanovik"
RENDER_SIZE = 1080
LOGO_HEIGHT = 168
BANNER_SIZE = (1600, 200)
SILHOUETTE_SHARE = 0.86
SILHOUETTE_CUTOFF = 12
LOGO_FLOOR = 24


def render_svg(path: Path, size: int) -> Image.Image:
    data = base64.b64encode(path.read_bytes()).decode()
    html = f'<html><body style="margin:0;background:transparent"><img src="data:image/svg+xml;base64,{data}" width="{size}" height="{size}"></body></html>'
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": size, "height": size})
        page.set_content(html, wait_until="load")
        png = page.screenshot(omit_background=True)
        browser.close()
    return Image.open(BytesIO(png)).convert("RGBA")


def make_logo(source: Path) -> Image.Image:
    luminance = render_svg(source, RENDER_SIZE).convert("L")
    alpha = luminance.point(lambda v: max(0, v - LOGO_FLOOR) * 255 // (255 - LOGO_FLOOR))
    logo = Image.new("RGBA", luminance.size, (255, 255, 255, 0))
    logo.putalpha(alpha)
    logo = logo.crop(alpha.getbbox())
    width = round(logo.width * LOGO_HEIGHT / logo.height)
    return logo.resize((width, LOGO_HEIGHT), Image.LANCZOS)


def silhouette(image: Image.Image, height: int) -> tuple[Image.Image, Image.Image]:
    corner = image.crop((0, 0, RENDER_SIZE, RENDER_SIZE // 5)).resize((1, 1), Image.BOX).getpixel((0, 0))
    base = Image.new("RGB", image.size, corner)
    lift = ImageChops.subtract(image, base).convert("L").point(lambda v: 255 if v > SILHOUETTE_CUTOFF else 0).filter(ImageFilter.MedianFilter(9))
    box = lift.getbbox()
    scale = height / (box[3] - box[1])
    size = (round((box[2] - box[0]) * scale), height)
    return image.crop(box).resize(size, Image.LANCZOS), lift.crop(box).filter(ImageFilter.GaussianBlur(4)).resize(size, Image.LANCZOS)


def make_background(source: Path) -> Image.Image:
    image = render_svg(source, RENDER_SIZE).convert("RGB")
    width, height = BANNER_SIZE
    background = image.resize((width, width), Image.LANCZOS).crop((0, 0, width, height))
    shape, mask = silhouette(image, round(height * SILHOUETTE_SHARE))
    background.paste(shape, ((width - shape.width) // 2, (height - shape.height) // 2), mask)
    return background


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=HERE / "vendor")
    args = parser.parse_args()
    make_logo(SOURCES / "4.svg").save(args.out / "senator-logo.png", optimize=True)
    make_background(SOURCES / "1.svg").save(args.out / "senator-banner.webp", quality=72, method=6)


if __name__ == "__main__":
    main()
