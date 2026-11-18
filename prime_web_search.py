"""Independent paid-web search adapter for Prime buyer sourcing.

No V5 imports, no global monkey-patching. Circuit breakers are per scanner
instance, and empty/failed primary searches can fall back to Bing RSS.
"""
from __future__ import annotations

import os
import requests


class PaidBuyerSearch:
    def __init__(self):
        self.exa_disabled = False
        self.serper_disabled = False

    @staticmethod
    def _query(query: str, domains: list[str] | None):
        if not domains:
            return query
        return query + " (" + " OR ".join(f"site:{d}" for d in domains) + ")"

    def search(self, query: str, domains: list[str] | None = None) -> list[dict]:
        exa_key = os.getenv("EXA_API_KEY", "").strip()
        if exa_key and not self.exa_disabled:
            payload = {"query": query, "type": "auto", "numResults": 5,
                       "contents": {"text": True}}
            if domains:
                payload["includeDomains"] = domains
            try:
                resp = requests.post(
                    "https://api.exa.ai/search", json=payload,
                    headers={"x-api-key": exa_key, "Content-Type": "application/json"},
                    timeout=30,
                )
                if resp.status_code == 200:
                    return [
                        {"source": "Exa", "url": row.get("url", ""),
                         "title": row.get("title", ""),
                         "text": row.get("text", ""),
                         "published": row.get("publishedDate", ""), "author": ""}
                        for row in (resp.json().get("results") or [])[:5]
                    ]
                if resp.status_code in {402, 429}:
                    self.exa_disabled = True
            except requests.RequestException:
                pass

        serper_key = os.getenv("SERPER_API_KEY", "").strip()
        if not serper_key or self.serper_disabled:
            return []

        try:
            resp = requests.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": serper_key, "Content-Type": "application/json"},
                json={"q": self._query(query, domains), "num": 10, "hl": "en"},
                timeout=30,
            )
            if resp.status_code != 200:
                try:
                    detail = str(resp.json()).casefold()
                except ValueError:
                    detail = str(resp.text[:400]).casefold()
                if (resp.status_code in {402, 429}
                        or "not enough credits" in detail
                        or "insufficient credit" in detail
                        or "quota" in detail):
                    self.serper_disabled = True
                return []
            return [
                {"source": "Serper", "url": row.get("link", ""),
                 "title": row.get("title", ""),
                 "text": row.get("snippet", ""),
                 "published": "", "author": ""}
                for row in (resp.json().get("organic") or [])[:10]
            ]
        except requests.RequestException:
            return []
