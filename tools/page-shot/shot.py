import argparse
import sys

from playwright.sync_api import sync_playwright


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a page headless and save a full-page PNG")
    parser.add_argument("url")
    parser.add_argument("out")
    parser.add_argument("--width", type=int, default=1400)
    parser.add_argument("--height", type=int, default=1000)
    parser.add_argument("--wait-text", default=None)
    parser.add_argument("--fill", nargs=2, metavar=("SELECTOR", "TEXT"), default=None)
    parser.add_argument("--click", action="append", default=[])
    parser.add_argument("--settle-ms", type=int, default=4000)
    parser.add_argument("--local-storage", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--press-enter", action="store_true")
    parser.add_argument("--select", nargs=2, action="append", default=[], metavar=("SELECTOR", "VALUE"))
    args = parser.parse_args()
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": args.width, "height": args.height})
        for item in args.local_storage:
            key, value = item.split("=", 1)
            page.add_init_script(f"window.localStorage.setItem({key!r}, {value!r})")
        page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.goto(args.url, wait_until="networkidle", timeout=60000)
        if args.wait_text:
            page.get_by_text(args.wait_text).first.wait_for(timeout=30000)
        if args.fill:
            page.fill(args.fill[0], args.fill[1])
            if args.press_enter:
                page.press(args.fill[0], "Enter")
                page.wait_for_timeout(args.settle_ms)
        for target in args.click:
            page.get_by_text(target, exact=False).first.click()
            page.wait_for_timeout(args.settle_ms)
        for selector, value in args.select:
            page.select_option(selector, value)
            page.wait_for_timeout(args.settle_ms)
        page.wait_for_timeout(args.settle_ms)
        page.screenshot(path=args.out, full_page=True)
        browser.close()
    for line in errors:
        print(line)
    print(f"saved {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
