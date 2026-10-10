import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

VIEWPORTS = {"phone": (390, 844), "desktop": (1366, 900)}


def capture(url: str, out: Path, settle_ms: int) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    written = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, (width, height) in VIEWPORTS.items():
            page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
            errors = []
            page.on("pageerror", lambda exc, sink=errors: sink.append(str(exc)))
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(settle_ms)
            target = out / f"{name}.png"
            page.screenshot(path=str(target), full_page=True)
            written.append(target)
            for message in errors:
                print(f"{name} page error: {message}")
            page.close()
        browser.close()
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Full-page phone and desktop screenshots of a published page, headless")
    parser.add_argument("url")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--settle-ms", type=int, default=3000)
    args = parser.parse_args()
    for path in capture(args.url, args.out, args.settle_ms):
        print(path)


if __name__ == "__main__":
    main()
