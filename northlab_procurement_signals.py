"""Conservative review-only signals from official procurement search results.

This classifier does not claim a tender is open or that NorthLab qualifies to bid.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

OFFICIAL_HOSTS = frozenset({"kksrsb.org", "ungm.org"})
PROCUREMENT_RE = re.compile(
    r"\b(?:ihalesi|ihale|teklif(?:ler)?|tender|procurement|rfp|request for proposals?)\b",
    re.IGNORECASE,
)
TECH_RE = re.compile(
    r"(?:yazılım|yazilim|entegrasyon|veri göçü|web(?:site|site development| development)?\b|"
    r"software|api\b|crm\b|website|application development|mobile app)",
    re.IGNORECASE,
)
NON_PROJECT_RE = re.compile(
    r"(?:teknik personel sınavı|personnel recruitment|job opening|training course|ihale sonucu)",
    re.IGNORECASE,
)


def _is_official_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        return parsed.scheme == "https" and any(
            host == allowed or host.endswith("." + allowed)
            for allowed in OFFICIAL_HOSTS
        )
    except ValueError:
        return False


def classify_official_procurement(text: str, url: str) -> dict | None:
    """Return a manual-review candidate, never an eligibility-approved HOT lead."""
    if not _is_official_url(url):
        return None
    compact = " ".join(str(text or "").split())
    if not PROCUREMENT_RE.search(compact) or not TECH_RE.search(compact):
        return None
    if NON_PROJECT_RE.search(compact):
        return None
    is_turkish = bool(re.search(r"[çğıöşüİı]", compact))
    types = ["SOFTWARE"]
    if re.search(r"(?:entegrasyon|integration|api\b|veri göçü)", compact, re.I):
        types.append("INTEGRATION")
    if re.search(r"(?:website|web sitesi|web development)", compact, re.I):
        types.append("WEBSITE")
    return {
        "lead_class": "RFP REVIEW",
        "intent_score": 85,
        "project_types": types,
        "language": "TR" if is_turkish else "EN",
        "reasons": [
            "official_procurement_notice",
            "deadline_not_verified",
            "supplier_eligibility_not_verified",
        ],
    }
