from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from rich.console import Console

from .adapters import NaukriAdapter
from .browser import browser_session
from .config import Settings
from .models import Job
from .parser import parse_job_detail, parse_listing_page

console = Console()
ADAPTERS = [NaukriAdapter()]


def _adapter_for(url: str):
    for adapter in ADAPTERS:
        if adapter.can_handle(url):
            return adapter
    return None


def _dedupe(jobs: list[Job]) -> list[Job]:
    unique: dict[str, Job] = {}
    for job in jobs:
        key = job.link.split("#", 1)[0].rstrip("/") if job.link else ""
        if key and key not in unique:
            unique[key] = job
    return list(unique.values())


def _save_debug(page, settings: Settings, source: str, page_number: int) -> None:
    if not (settings.save_html or settings.save_screenshots):
        return
    folder = Path(settings.output_dir) / "debug"
    folder.mkdir(parents=True, exist_ok=True)
    safe_source = source.replace(".", "_").replace("/", "_")
    stem = f"{safe_source}_page_{page_number}"
    if settings.save_html:
        (folder / f"{stem}.html").write_text(page.content(), encoding="utf-8")
    if settings.save_screenshots:
        page.screenshot(path=str(folder / f"{stem}.png"), full_page=True)


def _scrape_naukri(adapter: NaukriAdapter, context, target: str, settings: Settings) -> list[Job]:
    jobs: list[Job] = []
    current_url = target
    seen_pages: set[str] = set()

    for page_number in range(1, settings.max_pages_per_target + 1):
        clean_page_url = current_url.split("#", 1)[0]
        if clean_page_url in seen_pages:
            break
        seen_pages.add(clean_page_url)

        page = context.new_page()
        page.set_default_timeout(settings.request_timeout_ms)
        try:
            console.print(f"  [blue]Naukri page {page_number}:[/blue] {current_url}")
            response = page.goto(
                current_url,
                wait_until="domcontentloaded",
                timeout=settings.request_timeout_ms,
            )
            if response:
                console.print(f"    HTTP status: {response.status}")

            # Do not wait for networkidle: Naukri can keep analytics/ad requests alive.
            page.wait_for_timeout(2500)
            adapter.wait_for_results(page, min(settings.request_timeout_ms, 15000))

            if settings.debug:
                _save_debug(page, settings, urlparse(current_url).netloc, page_number)

            page_jobs = adapter.extract_jobs(page, current_url)
            console.print(f"    Found [yellow]{len(page_jobs)}[/yellow] real job cards")

            if not page_jobs:
                info = adapter.diagnostic(page)
                console.print(f"    [yellow]Naukri returned 0 cards.[/yellow]")
                console.print(f"    Page title: {info['title']}")
                console.print(f"    Final URL: {info['url']}")
                console.print(f"    Body preview: {info['body_preview']}")
                console.print(
                    "    [dim]If this is a challenge/empty page, run with HEADLESS=false "
                    "and inspect output/debug/naukri_page_1.html.[/dim]"
                )
                break

            jobs.extend(page_jobs)
            if len(jobs) >= settings.max_jobs_per_target:
                return jobs[: settings.max_jobs_per_target]

            next_url = adapter.next_page_url(page)
            if not next_url:
                console.print("    [dim]No next page found.[/dim]")
                break
            if next_url.split("#", 1)[0] in seen_pages:
                break
            current_url = next_url
        except Exception as exc:
            console.print(f"  [red]Naukri page failed:[/red] {current_url} ({exc})")
            break
        finally:
            page.close()

    return jobs[: settings.max_jobs_per_target]


def _scrape_generic(context, target: str, settings: Settings) -> list[Job]:
    all_jobs: list[Job] = []
    page = context.new_page()
    page.set_default_timeout(settings.request_timeout_ms)
    try:
        page.goto(target, wait_until="domcontentloaded", timeout=settings.request_timeout_ms)
        page.wait_for_timeout(1000)
        html = page.content()
        candidates = parse_listing_page(html, target)
        console.print(f"  Found [yellow]{len(candidates)}[/yellow] candidate links")
        if not candidates:
            job = parse_job_detail(html, page.url)
            if job:
                all_jobs.append(job)
            return all_jobs
        visited: set[str] = set()
        for _, job_url in candidates:
            if len(visited) >= settings.max_jobs_per_target:
                break
            clean_url = job_url.split("#", 1)[0].rstrip("/")
            if clean_url in visited:
                continue
            visited.add(clean_url)
            detail = context.new_page()
            detail.set_default_timeout(settings.request_timeout_ms)
            try:
                detail.goto(clean_url, wait_until="domcontentloaded", timeout=settings.request_timeout_ms)
                detail.wait_for_timeout(500)
                job = parse_job_detail(detail.content(), detail.url)
                if job:
                    all_jobs.append(job)
            except Exception as exc:
                console.print(f"  [red]Skipped:[/red] {clean_url} ({exc})")
            finally:
                detail.close()
    finally:
        page.close()
    return all_jobs


def run_pipeline(settings: Settings) -> list[Job]:
    all_jobs: list[Job] = []
    with browser_session(settings.headless) as context:
        for target in settings.target_urls:
            console.print(f"[cyan]Target:[/cyan] {target}")
            adapter = _adapter_for(target)
            try:
                if adapter:
                    all_jobs.extend(_scrape_naukri(adapter, context, target, settings))
                else:
                    all_jobs.extend(_scrape_generic(context, target, settings))
            except Exception as exc:
                console.print(f"[red]Target failed:[/red] {target} ({exc})")

    jobs = _dedupe(all_jobs)
    console.print(f"[green]Normalized jobs:[/green] {len(jobs)}")
    return jobs
