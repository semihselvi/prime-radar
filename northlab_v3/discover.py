"""Bounded public-source discovery. Fixed search provider; no arbitrary URL fetching."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
from xml.etree import ElementTree

from .core import Discovery, make_candidate

BING_RSS = "https://www.bing.com/search"
SEARCHES = (
    '"Kuzey Kıbrıs" "web sitesi" "ajans arıyoruz"',
    '"KKTC" "yazılım firması arıyoruz"',
    '"Girne" "web sitesi yaptırmak istiyoruz"',
    '"Kıbrıs" "CRM" "teklif almak istiyoruz"',
    '"Türkiye" "web sitesi yaptırmak istiyoruz"',
    '"İstanbul" "web sitemizi yenilemek istiyoruz"',
    '"Ankara" "CRM" "teklif almak istiyoruz"',
    '"İzmir" "otomasyon" "ajans arıyoruz"',
    '"Türkiye" "özel yazılım" "firma arıyoruz"',
    'site:linkedin.com/posts/ "web sitesi" "ajans arıyoruz" "Türkiye"',
    'site:linkedin.com/posts/ "yazılım" "teklif almak istiyoruz" "Türkiye"',
    '"Mersin" "e-ticaret sitesi" "yaptırmak istiyoruz"',
)
MAX_BYTES = 256_000
MAX_RESULTS_PER_QUERY = 10


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_rss(query: str, *, opener=None) -> bytes:
    if query not in SEARCHES:
        raise ValueError("Unapproved discovery query")
    params = urlencode({"format": "rss", "q": query, "setlang": "tr-TR", "cc": "tr"})
    request = Request(f"{BING_RSS}?{params}", headers={
        "User-Agent": "NorthLabPublicResearch/3.0 (+https://northlab.pro)",
        "Accept": "application/rss+xml,application/xml,text/xml",
        "Accept-Encoding": "identity",
    })
    with (opener or build_opener(NoRedirect())).open(request, timeout=12) as response:
        if response.status != 200:
            raise RuntimeError("Search provider HTTP not OK")
        mime = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if mime not in {"text/xml", "application/xml", "application/rss+xml", "text/plain"}:
            raise RuntimeError("Unexpected RSS response type")
        data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES or b"<!DOCTYPE" in data.upper():
            raise RuntimeError("Oversized or invalid search feed")
        return data


def parse_rss(body: bytes, discovered_at: str) -> list[Discovery]:
    root = ElementTree.fromstring(body)
    if root.tag != "rss":
        raise ValueError("Not RSS")
    result = []
    for item in root.findall(".//channel/item")[:MAX_RESULTS_PER_QUERY]:
        indexed = item.findtext("pubDate")
        if indexed:
            try:
                dt = parsedate_to_datetime(indexed).astimezone(timezone.utc)
                indexed = dt.isoformat()
            except (TypeError, ValueError, OverflowError):
                indexed = None
        result.append(Discovery(
            source_url=item.findtext("link") or "",
            title=item.findtext("title") or "",
            excerpt=item.findtext("description") or "",
            discovered_at=discovered_at,
            indexed_at=indexed,
        ))
    return result


def scan(*, now: datetime | None = None, fetch=fetch_rss) -> dict:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Timezone aware now required")
    timestamp = now.astimezone(timezone.utc).isoformat()
    seen, queue, rejected, provider_errors = set(), [], Counter(), []
    successful_feeds = 0
    raw_count = 0
    for index, query in enumerate(SEARCHES):
        try:
            rows = parse_rss(fetch(query), timestamp)
            successful_feeds += 1
        except Exception as exc:
            provider_errors.append({"query_index": index, "reason": type(exc).__name__})
            continue
        raw_count += len(rows)
        for row in rows:
            candidate, reason = make_candidate(row)
            if not candidate:
                rejected[reason] += 1
                continue
            if candidate["candidate_id"] in seen:
                rejected["duplicate"] += 1
                continue
            seen.add(candidate["candidate_id"])
            queue.append(candidate)
    return {
        "version": "3.0-shadow",
        "run_at": timestamp,
        "status": "DISCOVERY_ONLY" if successful_feeds else "SOURCE_FAILURE",
        "market_scope": ["KKTC", "TR"],
        "query_count": len(SEARCHES),
        "successful_search_feeds": successful_feeds,
        "raw_results": raw_count,
        "review_queue_count": len(queue),
        "qualified_lead_count": 0,
        "contacts_sent": 0,
        "rejected": dict(rejected),
        "provider_errors": provider_errors,
        "review_queue": queue,
    }
