from contextlib import contextmanager
from playwright.sync_api import sync_playwright


@contextmanager
def browser_session(headless: bool):
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000},
            screen={"width": 1440, "height": 1000},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            color_scheme="light",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/151.0.0.0 Safari/537.36"
            ),
        )
        # Keep normal browser behavior while making the environment consistent.
        context.set_default_timeout(30000)
        try:
            yield context
        finally:
            context.close()
            browser.close()
