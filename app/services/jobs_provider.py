"""Native Python implementation of the supplied LinkedIn guest-job query module.

This fetches public guest-job listing HTML and parses it locally. It is not an official
LinkedIn API; HTML selectors/endpoints can change, and requests may be rate-limited.
Keep request rates conservative and comply with the site's applicable terms.
"""
from __future__ import annotations

import asyncio
import html as html_lib
import json
import logging
import random
import re
import time
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60 * 60
BATCH_SIZE = 25
MAX_CONSECUTIVE_ERRORS = 3
REQUEST_TIMEOUT_SECONDS = 10.0
DETAIL_REQUEST_TIMEOUT_SECONDS = 15.0
DETAIL_FETCH_CONCURRENCY = 3

# Stable User-Agent: the JavaScript library's random-useragent dependency is not needed in Python.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Referer": "https://www.google.com/",
    "X-Requested-With": "XMLHttpRequest",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}
DETAIL_HEADERS = {
    **{key: value for key, value in DEFAULT_HEADERS.items() if key != "X-Requested-With"},
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class JobCache:
    """Simple in-memory TTL cache, equivalent to the JavaScript JobCache."""

    def __init__(self, ttl: int = CACHE_TTL_SECONDS) -> None:
        self.cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self.ttl = ttl

    def set(self, key: str, value: list[dict[str, Any]]) -> None:
        self.cache[key] = (time.monotonic(), value)

    def get(self, key: str) -> list[dict[str, Any]] | None:
        item = self.cache.get(key)
        if item is None:
            return None
        timestamp, data = item
        if time.monotonic() - timestamp > self.ttl:
            self.cache.pop(key, None)
            return None
        return data

    def clear(self) -> None:
        now = time.monotonic()
        expired = [key for key, (timestamp, _) in self.cache.items() if now - timestamp > self.ttl]
        for key in expired:
            self.cache.pop(key, None)

    def size(self) -> int:
        self.clear()
        return len(self.cache)


cache = JobCache()


class Query:
    def __init__(self, query_obj: dict[str, Any] | None = None) -> None:
        query_obj = query_obj or {}
        self.host = str(query_obj.get("host") or "www.linkedin.com").strip()
        self.keyword = self._clean_query_value(query_obj.get("keyword"))
        self.location = self._clean_query_value(query_obj.get("location"))
        self.date_since_posted = str(query_obj.get("dateSincePosted") or "")
        self.job_type = str(query_obj.get("jobType") or "")
        self.remote_filter = str(query_obj.get("remoteFilter") or "")
        self.salary = str(query_obj.get("salary") or "")
        self.experience_level = str(query_obj.get("experienceLevel") or "")
        self.sort_by = str(query_obj.get("sortBy") or "")
        self.limit = self._to_int(query_obj.get("limit"), default=0)
        self.page = self._to_int(query_obj.get("page"), default=0)
        self.has_verification = self._to_bool(query_obj.get("has_verification", False))
        self.under_10_applicants = self._to_bool(query_obj.get("under_10_applicants", False))

    @staticmethod
    def _clean_query_value(value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip())

    @staticmethod
    def _to_int(value: Any, default: int = 0) -> int:
        try:
            return max(0, int(value or default))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _to_bool(value: Any) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def get_date_since_posted(self) -> str:
        return {
            "past month": "r2592000",
            "past week": "r604800",
            "24hr": "r86400",
        }.get(self.date_since_posted.lower(), "")

    def get_experience_level(self) -> str:
        return {
            "internship": "1",
            "entry level": "2",
            "associate": "3",
            "senior": "4",
            "director": "5",
            "executive": "6",
        }.get(self.experience_level.lower(), "")

    def get_job_type(self) -> str:
        return {
            "full time": "F",
            "full-time": "F",
            "part time": "P",
            "part-time": "P",
            "contract": "C",
            "temporary": "T",
            "volunteer": "V",
            "internship": "I",
        }.get(self.job_type.lower(), "")

    def get_remote_filter(self) -> str:
        return {
            "on-site": "1",
            "on site": "1",
            "remote": "2",
            "hybrid": "3",
        }.get(self.remote_filter.lower(), "")

    def get_salary(self) -> str:
        return {
            "40000": "1",
            "60000": "2",
            "80000": "3",
            "100000": "4",
            "120000": "5",
        }.get(self.salary, "")

    def get_page(self) -> int:
        return self.page * BATCH_SIZE

    def url(self, start: int = 0) -> str:
        params: dict[str, str | int] = {}
        if self.keyword:
            params["keywords"] = self.keyword
        if self.location:
            params["location"] = self.location
        if self.get_date_since_posted():
            params["f_TPR"] = self.get_date_since_posted()
        if self.get_salary():
            params["f_SB2"] = self.get_salary()
        if self.get_experience_level():
            params["f_E"] = self.get_experience_level()
        if self.get_remote_filter():
            params["f_WT"] = self.get_remote_filter()
        if self.get_job_type():
            params["f_JT"] = self.get_job_type()

        # Preserve the JavaScript module's query semantics. LinkedIn may ignore these filters
        # on some guest search endpoints, but they are included when supplied/defaulted.
        params["f_VJ"] = "true" if self.has_verification else "false"
        params["f_EA"] = "true" if self.under_10_applicants else "false"
        params["start"] = start + self.get_page()
        if self.sort_by == "recent":
            params["sortBy"] = "DD"
        elif self.sort_by == "relevant":
            params["sortBy"] = "R"

        request = httpx.Request(
            "GET",
            f"https://{self.host}/jobs-guest/jobs/api/seeMoreJobPostings/search",
            params=params,
        )
        return str(request.url)

    def get_cache_key(self) -> str:
        return f"{self.url(0)}_limit:{self.limit}"

    async def fetch_job_batch(self, start: int) -> list[dict[str, Any]]:
        url = self.url(start)
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=True) as client:
            response = await client.get(url, headers=DEFAULT_HEADERS)
        if response.status_code == 429:
            raise RuntimeError("LinkedIn returned HTTP 429: rate limit reached")
        response.raise_for_status()
        return parse_job_list(response.text)

    async def get_jobs(self) -> list[dict[str, Any]]:
        cache_key = self.get_cache_key()
        cached_jobs = cache.get(cache_key)
        if cached_jobs is not None:
            log.debug("Returning cached LinkedIn guest-job results for key %s", cache_key)
            return cached_jobs

        all_jobs: list[dict[str, Any]] = []
        start = 0
        consecutive_errors = 0

        while True:
            try:
                jobs = await self.fetch_job_batch(start)
                if not jobs:
                    break
                all_jobs.extend(jobs)
                log.info("Fetched %d jobs; total=%d", len(jobs), len(all_jobs))

                if self.limit and len(all_jobs) >= self.limit:
                    all_jobs = all_jobs[: self.limit]
                    break

                consecutive_errors = 0
                start += BATCH_SIZE
                await asyncio.sleep(2.0 + random.random())
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                consecutive_errors += 1
                log.warning(
                    "Error fetching LinkedIn jobs batch (attempt %d/%d): %s",
                    consecutive_errors,
                    MAX_CONSECUTIVE_ERRORS,
                    exc,
                )
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    log.error("Stopping LinkedIn job search after consecutive request failures")
                    break
                await asyncio.sleep(2**consecutive_errors)

        if all_jobs:
            # Search cards do not contain full descriptions. Fetch each job's detail page
            # separately and parse its JobPosting JSON-LD, with HTML selectors as fallback.
            semaphore = asyncio.Semaphore(DETAIL_FETCH_CONCURRENCY)

            async def enrich_description(job: dict[str, Any]) -> None:
                if job.get("description"):
                    return
                job_url = str(job.get("jobUrl") or "")
                if not job_url:
                    job["description"] = ""
                    return
                async with semaphore:
                    # Small jitter avoids sending a burst of detail-page requests at once.
                    await asyncio.sleep(random.uniform(0.2, 0.6))
                    job["description"] = await fetch_job_description(job_url)

            await asyncio.gather(*(enrich_description(job) for job in all_jobs))
            cache.set(cache_key, all_jobs)
        return all_jobs


def _clean_description(raw_description: Any) -> str:
    """Convert HTML found in JSON-LD or the visible description block into readable plain text."""
    if not raw_description:
        return ""
    raw = html_lib.unescape(str(raw_description))
    body = BeautifulSoup(raw, "html.parser")

    # Preserve paragraphs, headings, line breaks and list items rather than flattening the
    # entire description into one sentence. This makes the stored text useful to search and LLMs.
    for br in body.find_all("br"):
        br.replace_with("\n")
    for li in body.find_all("li"):
        li.insert_before("\n• ")
        li.insert_after("\n")
    for block in body.find_all(["p", "div", "h1", "h2", "h3", "h4", "h5", "h6"]):
        block.insert_before("\n")
        block.insert_after("\n")

    text = body.get_text("", strip=False).replace("\xa0", " ")
    lines = []
    for line in text.splitlines():
        clean_line = re.sub(r"\s+", " ", line).strip()
        if clean_line:
            lines.append(clean_line)
    return "\n".join(lines).strip()


def _find_jobposting_description(data: Any) -> str:
    """Recursively inspect JSON-LD objects/arrays for schema.org JobPosting."""
    if isinstance(data, list):
        for item in data:
            description = _find_jobposting_description(item)
            if description:
                return description
        return ""
    if not isinstance(data, dict):
        return ""

    type_value = data.get("@type", [])
    types = type_value if isinstance(type_value, list) else [type_value]
    if any(str(item).lower() == "jobposting" for item in types):
        description = data.get("description")
        if isinstance(description, str) and description.strip():
            return description

    for value in data.values():
        description = _find_jobposting_description(value)
        if description:
            return description
    return ""


def parse_job_description(page_html: str) -> str:
    """Extract the full job description from a LinkedIn job detail HTML page.

    The supplied example page embeds the description in a schema.org JobPosting
    JSON-LD script. HTML selectors are used for pages where that script is absent.
    """
    try:
        soup = BeautifulSoup(page_html or "", "html.parser")
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            script_text = script.string or script.get_text()
            if not script_text:
                continue
            try:
                data = json.loads(script_text.strip())
            except (json.JSONDecodeError, TypeError):
                continue
            raw_description = _find_jobposting_description(data)
            if raw_description:
                description = _clean_description(raw_description)
                if description:
                    return description

        for selector in (
            ".show-more-less-html__markup",
            ".description__text",
            ".decorated-job-posting__details",
            "#job-details",
        ):
            node = soup.select_one(selector)
            if node:
                description = _clean_description(str(node))
                if description:
                    return description

        return ""
    except Exception:
        log.exception("Unable to parse LinkedIn job description page")
        return ""


_description_cache: dict[str, tuple[float, str]] = {}


def _description_cache_key(job_url: str) -> str:
    parsed = urlsplit(job_url.strip())
    # Ignore tracking parameters so the same job URL is cached across listing pages.
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), "", ""))


async def fetch_job_description(job_url: str) -> str:
    """Make a second request to jobUrl and return the description, or empty text on failure.

    A detail-page failure should not discard an otherwise usable job listing.
    """
    if not job_url:
        return ""
    try:
        parsed = urlsplit(job_url.strip())
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in {"http", "https"} or not (host == "linkedin.com" or host.endswith(".linkedin.com")):
            log.warning("Skipping non-LinkedIn job detail URL: %s", job_url)
            return ""
        cache_key = _description_cache_key(job_url)
        cached = _description_cache.get(cache_key)
        now = time.monotonic()
        if cached and now - cached[0] <= CACHE_TTL_SECONDS:
            return cached[1]
        if cached:
            _description_cache.pop(cache_key, None)

        async with httpx.AsyncClient(timeout=DETAIL_REQUEST_TIMEOUT_SECONDS, follow_redirects=True) as client:
            response = await client.get(job_url, headers=DETAIL_HEADERS)
        if response.status_code == 429:
            log.warning("LinkedIn rate limited job detail request: %s", job_url)
            return ""
        response.raise_for_status()
        final_host = (response.url.host or "").lower()
        if not (final_host == "linkedin.com" or final_host.endswith(".linkedin.com")):
            log.warning("LinkedIn job page redirected to an unexpected host: %s", response.url)
            return ""
        description = parse_job_description(response.text)
        if description:
            _description_cache[cache_key] = (time.monotonic(), description)
        else:
            log.info("No description found on LinkedIn job detail page: %s", job_url)
        return description
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        log.warning("Could not fetch job description from %s: %s", job_url, exc)
        return ""


def clear_description_cache() -> None:
    _description_cache.clear()


def parse_job_list(job_data: str) -> list[dict[str, Any]]:
    """Parse listing cards using the selectors from the supplied Cheerio implementation."""
    try:
        soup = BeautifulSoup(job_data or "", "html.parser")
        parsed_jobs: list[dict[str, Any]] = []
        for element in soup.select("li"):
            try:
                position = _select_text(element, ".base-search-card__title")
                company = _select_text(element, ".base-search-card__subtitle")
                location = _select_text(element, ".job-search-card__location")
                time_element = element.select_one("time")
                date = time_element.get("datetime") if time_element else None
                salary = _select_text(element, ".job-search-card__salary-info")
                job_link = element.select_one(".base-card__full-link")
                job_url = urljoin("https://www.linkedin.com", job_link.get("href", "")) if job_link else ""
                logo_element = element.select_one(".artdeco-entity-image")
                company_logo = ""
                if logo_element:
                    company_logo = str(
                        logo_element.get("data-delayed-url")
                        or logo_element.get("src")
                        or ""
                    )
                ago_time = _select_text(element, ".job-search-card__listdate")

                if not position or not company:
                    continue

                parsed_jobs.append({
                    "position": position,
                    "company": company,
                    "location": location,
                    "date": date,
                    "salary": salary or "Not specified",
                    "jobUrl": job_url,
                    "companyLogo": company_logo,
                    "agoTime": ago_time,
                    "description": "",
                })
            except Exception:
                log.exception("Unable to parse one LinkedIn job card")
        return parsed_jobs
    except Exception:
        log.exception("Unable to parse LinkedIn job-list response")
        return []


def _select_text(element: Any, selector: str) -> str:
    node = element.select_one(selector)
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip() if node else ""


async def fetch_jobs(options: dict[str, Any]) -> list[dict[str, Any]]:
    """Public adapter consumed by app.services.search.fetch_and_store()."""
    return await Query(options).get_jobs()


def normalize_job(raw: dict[str, Any]) -> dict[str, Any]:
    # The listing-card fields are supplemented by a detail-page request for the full description.
    # Do not infer salary values where a job does not publish them.
    salary = str(raw.get("salary") or "Not specified").strip()
    return {
        "position": str(raw.get("position") or raw.get("title") or "Untitled role"),
        "company": str(raw.get("company") or "Unknown"),
        "location": str(raw.get("location") or "Not specified"),
        "posted_date": raw.get("date"),
        "salary_text": salary or "Not specified",
        "salary_min": None,
        "salary_max": None,
        "job_url": str(raw.get("jobUrl") or raw.get("url") or ""),
        "company_logo": raw.get("companyLogo") or None,
        "ago_time": raw.get("agoTime") or None,
        "description": str(raw.get("description") or raw.get("jobDescription") or "").strip(),
    }


def clear_cache() -> None:
    cache.clear()


def get_cache_size() -> int:
    return cache.size()
