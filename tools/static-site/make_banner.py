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
    logo = Image.new("RGBA", luminance.size, (255, 255, 255, 0))
    logo.putalpha(luminance)
    logo = logo.crop(luminance.point(lambda v: 255 if v > 24 else 0).getbbox())
    width = round(logo.width * LOGO_HEIGHT / logo.height)
    return logo.resize((width, LOGO_HEIGHT), Image.LANCZOS)


def make_background(source: Path) -> Image.Image:
    image = render_svg(source, RENDER_SIZE).convert("RGB")
    width, height = BANNER_SIZE
    background = image.resize((width, width), Image.LANCZOS).crop((0, 0, width, height))
    base = Image.new("RGB", image.size, background.resize((1, 1), Image.BOX).getpixel((0, 0)))
    lift = ImageChops.subtract(image, base).convert("L").point(lambda v: 255 if v > SILHOUETTE_CUTOFF else 0).filter(ImageFilter.MedianFilter(9))
    box = lift.getbbox()
    scale = height * SILHOUETTE_SHARE / (box[3] - box[1])
    size = (round((box[2] - box[0]) * scale), round((box[3] - box[1]) * scale))
    silhouette = image.crop(box).resize(size, Image.LANCZOS)
    mask = lift.crop(box).filter(ImageFilter.GaussianBlur(4)).resize(size, Image.LANCZOS)
    background.paste(silhouette, ((width - size[0]) // 2, (height - size[1]) // 2), mask)
    return background


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=HERE / "vendor")
    args = parser.parse_args()
    make_logo(SOURCES / "4.svg").save(args.out / "senator-logo.png", optimize=True)
    make_background(SOURCES / "1.svg").save(args.out / "senator-banner.webp", quality=72, method=6)


if __name__ == "__main__":
    main()
