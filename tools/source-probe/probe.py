import argparse
import sys

import httpx

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
}
PROFILES = {
    "tool": {"User-Agent": "riesgo-comunal/0.1"},
    "compatible": {"User-Agent": "Mozilla/5.0 (compatible; riesgo-comunal/0.1)"},
    "browser": BROWSER_HEADERS,
}


def probe_http(url: str, name: str, headers: dict[str, str]) -> str:
    try:
        response = httpx.get(url, headers=headers, follow_redirects=True, timeout=30)
    except httpx.HTTPError as error:
        return f"{name}: error {error!r}"
    return f"{name}: {response.status_code} {len(response.content)} bytes server={response.headers.get('server')}"


def probe_browser(url: str) -> str:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            response = browser.new_page(user_agent=BROWSER_HEADERS["User-Agent"]).goto(url, timeout=60000)
            return f"chromium: {response.status if response else 'no response'} {len(response.body()) if response else 0} bytes"
        except Exception as error:
            return f"chromium: error {error!r}"
        finally:
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Report how a source URL answers different clients")
    parser.add_argument("url")
    parser.add_argument("--browser", action="store_true")
    args = parser.parse_args()
    print(f"ip: {httpx.get('https://api.ipify.org', timeout=30).text}")
    for name, headers in PROFILES.items():
        print(probe_http(args.url, name, headers))
    if args.browser:
        print(probe_browser(args.url))
    return 0


if __name__ == "__main__":
    sys.exit(main())
