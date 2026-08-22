from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv(override=True)


@dataclass(frozen=True)
class Settings:
    target_urls: list[str]
    google_sheets_url: str
    google_service_account_file: str
    headless: bool
    request_timeout_ms: int
    max_pages_per_target: int
    max_jobs_per_target: int
    debug: bool
    save_html: bool
    save_screenshots: bool
    output_dir: str


def _parse_urls(value: str) -> list[str]:
    if not value:
        return []

    normalized = value.replace("\r\n", "\n").replace(",", "\n")
    return [
        line.strip()
        for line in normalized.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {
        "1", "true", "yes", "y", "on"
    }


def get_settings() -> Settings:
    return Settings(
        target_urls=_parse_urls(os.getenv("TARGET_URLS", "")),
        google_sheets_url=os.getenv("GOOGLE_SHEETS_URL", "").strip(),
        google_service_account_file=os.getenv(
            "GOOGLE_SERVICE_ACCOUNT_FILE",
            "credentials/service-account.json",
        ).strip(),
        headless=_bool("HEADLESS", True),
        request_timeout_ms=int(os.getenv("REQUEST_TIMEOUT_MS", "30000")),
        max_pages_per_target=max(1, int(os.getenv("MAX_PAGES_PER_TARGET", "3"))),
        max_jobs_per_target=max(1, int(os.getenv("MAX_JOBS_PER_TARGET", "100"))),
        debug=_bool("DEBUG", False),
        save_html=_bool("SAVE_HTML", False),
        save_screenshots=_bool("SCREENSHOTS", False),
        output_dir=os.getenv("OUTPUT_DIR", "output").strip() or "output",
    )
