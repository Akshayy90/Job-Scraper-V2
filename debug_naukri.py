from pathlib import Path

from playwright.sync_api import sync_playwright

from scraper.config import get_settings


def main() -> None:
    settings = get_settings()
    if not settings.target_urls:
        raise SystemExit("TARGET_URLS is empty")

    url = settings.target_urls[0]
    output = Path(settings.output_dir)
    output.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000},
            locale="en-US",
        )
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=settings.request_timeout_ms)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(1000)

        html_path = output / "naukri_debug.html"
        png_path = output / "naukri_debug.png"
        html_path.write_text(page.content(), encoding="utf-8")
        page.screenshot(path=str(png_path), full_page=True)

        cards = page.locator("div.srp-jobtuple-wrapper")
        print("URL:", page.url)
        print("TITLE:", page.title())
        print("JOB CARDS:", cards.count())
        print("NEXT:", page.locator('link[rel="next"]').get_attribute("href"))
        print("HTML:", html_path)
        print("SCREENSHOT:", png_path)

        context.close()
        browser.close()


if __name__ == "__main__":
    main()
