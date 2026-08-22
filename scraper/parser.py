from __future__ import annotations

# Generic fallback parser for non-adapter sites. Naukri is intentionally handled
# by scraper.adapters.naukri.NaukriAdapter in pipeline.py.

import json
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

import dateparser
from bs4 import BeautifulSoup

from .models import Job


JOB_URL_RE = re.compile(
    r"(job|jobs|career|careers|vacancy|vacancies|opening|openings|"
    r"position|positions|employment|apply)", re.I,
)

ROLE_RE = re.compile(
    r"(software|full[\s-]?stack|frontend|front[\s-]?end|backend|back[\s-]?end|"
    r"developer|engineer|data|machine learning|ai|intern|designer|"
    r"analyst|manager|devops|qa|tester|consultant|architect|scientist)", re.I,
)

DEADLINE_RE = re.compile(
    r"(deadline|last date|apply before|application closes?|closing date)"
    r"\s*[:\-]?\s*([^\n|]{3,80})", re.I,
)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_date(value: str) -> str:
    if not value:
        return ""
    dt = dateparser.parse(value, settings={"RETURN_AS_TIMEZONE_AWARE": False})
    return dt.strftime("%Y-%m-%d") if dt else ""


def _json_ld_objects(soup: BeautifulSoup) -> list[dict]:
    objects = []
    for tag in soup.select('script[type="application/ld+json"]'):
        raw = tag.string or tag.get_text()
        try:
            data = json.loads(raw)
        except Exception:
            continue
        if isinstance(data, list):
            objects.extend(x for x in data if isinstance(x, dict))
        elif isinstance(data, dict):
            graph = data.get("@graph")
            if isinstance(graph, list):
                objects.extend(x for x in graph if isinstance(x, dict))
            else:
                objects.append(data)
    return objects


def _json_ld_jobs(soup: BeautifulSoup, page_url: str) -> list[Job]:
    jobs = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for obj in _json_ld_objects(soup):
        typ = obj.get("@type", "")
        types = typ if isinstance(typ, list) else [typ]
        if not any(str(t).lower() == "jobposting" for t in types):
            continue

        org = obj.get("hiringOrganization") or {}
        place = obj.get("jobLocation") or {}
        if isinstance(place, list):
            place = place[0] if place else {}
        address = place.get("address") or {} if isinstance(place, dict) else {}
        location = ", ".join(
            x for x in [
                address.get("addressLocality", ""),
                address.get("addressRegion", ""),
                address.get("addressCountry", ""),
            ] if x
        )
        url = urljoin(page_url, str(obj.get("url") or page_url))
        date_added = normalize_date(str(obj.get("datePosted", "")))
        deadline = normalize_date(str(obj.get("validThrough", "")))

        jobs.append(Job(
            company_name=clean_text(str(org.get("name", ""))),
            role=clean_text(str(obj.get("title", ""))),
            link=url,
            location=clean_text(location),
            date_added=date_added or datetime.now().strftime("%Y-%m-%d"),
            deadline=deadline,
            status="Open",
            last_checked=now,
            source=urlparse(page_url).netloc,
        ))
    return jobs


def _extract_links(soup: BeautifulSoup, page_url: str) -> list[tuple[str, str]]:
    found = []
    for a in soup.select("a[href]"):
        href = a.get("href", "").strip()
        text = clean_text(a.get_text(" ", strip=True))
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")) or not text:
            continue
        absolute = urljoin(page_url, href)
        if urlparse(absolute).netloc != urlparse(page_url).netloc:
            continue
        if JOB_URL_RE.search(absolute) or ROLE_RE.search(text):
            found.append((text, absolute))

    seen = set()
    result = []
    for text, url in found:
        key = url.split("#")[0].rstrip("/")
        if key not in seen:
            seen.add(key)
            result.append((text, key))
    return result


def _guess_company(soup: BeautifulSoup) -> str:
    for selector in ['[itemprop="hiringOrganization"]', '[class*="company"]', '[class*="employer"]', '[class*="brand"]']:
        node = soup.select_one(selector)
        if node:
            value = clean_text(node.get_text(" ", strip=True))
            if 2 <= len(value) <= 120:
                return value
    return ""


def _guess_role(soup: BeautifulSoup) -> str:
    for selector in ["h1", '[itemprop="title"]', "main h1", "article h1"]:
        node = soup.select_one(selector)
        if node:
            value = clean_text(node.get_text(" ", strip=True))
            if 3 <= len(value) <= 180:
                return value
    return ""


def _guess_location(soup: BeautifulSoup) -> str:
    for selector in ['[itemprop="jobLocation"]', '[class*="location"]', '[class*="Location"]']:
        node = soup.select_one(selector)
        if node:
            value = clean_text(node.get_text(" ", strip=True))
            if 2 <= len(value) <= 160:
                return value
    return ""


def _guess_deadline(text: str) -> str:
    match = DEADLINE_RE.search(text)
    return normalize_date(match.group(2)) if match else ""


def parse_job_detail(html: str, page_url: str) -> Job | None:
    soup = BeautifulSoup(html, "html.parser")
    ld_jobs = _json_ld_jobs(soup, page_url)
    if ld_jobs:
        return ld_jobs[0]

    title = _guess_role(soup)
    if not title:
        return None

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = clean_text(soup.get_text(" ", strip=True))
    return Job(
        company_name=_guess_company(soup),
        role=title,
        link=page_url,
        location=_guess_location(soup),
        date_added=datetime.now().strftime("%Y-%m-%d"),
        deadline=_guess_deadline(text),
        status="Open",
        last_checked=now,
        source=urlparse(page_url).netloc,
    )


def parse_listing_page(html: str, page_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    ld_jobs = _json_ld_jobs(soup, page_url)
    if ld_jobs:
        return [(job.role, job.link) for job in ld_jobs if job.link]
    return _extract_links(soup, page_url)
