from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

from ..models import Job


class NaukriAdapter:
    """Naukri search-result adapter using the live rendered DOM."""

    BASE_URL = "https://www.naukri.com"

    # The first selector is the structure observed in the user's captured
    # Naukri DOM. The fallbacks make the adapter a little more resilient.
    CARD_SELECTORS = (
        "div.srp-jobtuple-wrapper",
        "div[data-job-id].srp-jobtuple-wrapper",
        "div[data-job-id]",
    )
    TITLE_SELECTORS = ("h2 a.title", "a.title")
    COMPANY_SELECTORS = ("a.comp-name", "a[class*='comp-name']")
    LOCATION_SELECTORS = (".loc-wrap .locWdth", ".loc-wrap", "[class*='location']")
    EXPERIENCE_SELECTORS = (".exp-wrap .expwdth", ".exp-wrap")
    POSTED_SELECTORS = (".job-post-day", "[class*='job-post-day']")
    NEXT_SELECTORS = (
        'link[rel="next"]',
        'a[rel="next"]',
        'a[aria-label*="Next"]',
        'a[title*="Next"]',
    )

    def can_handle(self, url: str) -> bool:
        return "naukri.com" in urlparse(url).netloc.lower()

    def card_count(self, page) -> int:
        for selector in self.CARD_SELECTORS:
            count = page.locator(selector).count()
            if count:
                return count
        return 0

    def wait_for_results(self, page, timeout_ms: int) -> None:
        # Give Naukri time to render its React content. We deliberately do not
        # require networkidle because ad/analytics requests can stay open.
        deadline = timeout_ms
        start = datetime.now()
        while (datetime.now() - start).total_seconds() * 1000 < deadline:
            if self.card_count(page) > 0:
                return
            page.wait_for_timeout(500)

        # A small scroll often triggers lazy-rendered listing content.
        try:
            page.mouse.wheel(0, 1200)
            page.wait_for_timeout(1500)
        except Exception:
            pass

    def extract_jobs(self, page, source_url: str) -> list[Job]:
        selector = next(
            (s for s in self.CARD_SELECTORS if page.locator(s).count()),
            self.CARD_SELECTORS[0],
        )
        cards = page.locator(selector)
        count = cards.count()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        jobs: list[Job] = []

        for index in range(count):
            card = cards.nth(index)
            try:
                job = self._extract_card(card, now, source_url)
                if job:
                    jobs.append(job)
            except Exception as exc:
                print(f"[NAUKRI] Card {index + 1}/{count} failed: {exc}")

        return jobs

    def next_page_url(self, page) -> str | None:
        for selector in self.NEXT_SELECTORS:
            try:
                locator = page.locator(selector).first
                if locator.count():
                    href = locator.get_attribute("href")
                    if href:
                        return urljoin(page.url, href).split("#", 1)[0]
            except Exception:
                continue
        return None

    def diagnostic(self, page) -> dict[str, str | int]:
        """Return safe diagnostics when Naukri returns no cards."""
        try:
            body_text = " ".join(page.locator("body").inner_text().split())[:500]
        except Exception:
            body_text = ""
        try:
            title = page.title()
        except Exception:
            title = ""
        return {
            "url": page.url,
            "title": title,
            "cards": self.card_count(page),
            "body_preview": body_text,
        }

    def _extract_card(self, card, now: str, source_url: str) -> Job | None:
        title_el = self._first(card, self.TITLE_SELECTORS)
        if title_el is None:
            return None

        role = self._text(title_el)
        link = title_el.get_attribute("href") or ""
        if not role or not link:
            return None

        company = self._text(self._first(card, self.COMPANY_SELECTORS))
        location = self._text(self._first(card, self.LOCATION_SELECTORS))
        experience = self._text(self._first(card, self.EXPERIENCE_SELECTORS))
        posted_age = self._text(self._first(card, self.POSTED_SELECTORS))

        absolute_link = urljoin(self.BASE_URL, link).split("#", 1)[0].rstrip("/")

        # A card without a company is usually not a job result. Skip it rather
        # than putting navigation/sponsored noise into the Sheet.
        if not company:
            return None

        print(
            f"[NAUKRI] {role} | {company} | {location}"
            f" | posted={posted_age or '-'} | exp={experience or '-'}"
        )

        return Job(
            company_name=company,
            role=role,
            link=absolute_link,
            location=location,
            date_added=datetime.now().strftime("%Y-%m-%d"),
            deadline="",
            status="Open",
            last_checked=now,
            source=urlparse(source_url).netloc,
        )

    @staticmethod
    def _first(card, selectors):
        for selector in selectors:
            locator = card.locator(selector).first
            if locator.count():
                return locator
        return None

    @staticmethod
    def _text(locator) -> str:
        if locator is None:
            return ""
        try:
            return " ".join(locator.inner_text().split())
        except Exception:
            return ""

    def save_debug(self, page, output_dir: str, page_number: int) -> None:
        folder = Path(output_dir) / "debug"
        folder.mkdir(parents=True, exist_ok=True)
        stem = f"naukri_page_{page_number}"
        (folder / f"{stem}.html").write_text(page.content(), encoding="utf-8")
        page.screenshot(path=str(folder / f"{stem}.png"), full_page=True)
