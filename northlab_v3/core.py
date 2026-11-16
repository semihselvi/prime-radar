"""Independent NorthLab v3 evidence gate. Standard library, no network or side effects.

Acquisition is not qualification. No automatic message, CRM write, scoring or spend.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import ipaddress
import re
from urllib.parse import urlsplit, urlunsplit

MAX_AGE_DAYS = 14
SUPPORTED_MARKETS = frozenset({"TR", "KKTC"})
BLOCKED_HOSTS = frozenset({
    "r10.net", "www.r10.net", "bionluk.com", "www.bionluk.com",
    "armut.com", "www.armut.com", "upwork.com", "www.upwork.com",
    "fiverr.com", "www.fiverr.com", "freelancer.com", "www.freelancer.com",
})

# Discovery signal only; no BUYER or HOT status is ever emitted by keyword matching.
BUY_WORDS = re.compile(
    r"(?:\b(?:arıyoruz|arıyorum|teklif\s+(?:bekliyoruz|alacağız|almak\s+istiyoruz)|"
    r"yaptırmak\s+istiyoruz|yaptıracağız|ihtiyacımız\s+var|"
    r"geliştirmek\s+istiyoruz|yenilemek\s+istiyoruz|"
    r"çözüm\s+ortağı\s+arıyoruz|ajans\s+arıyoruz|"
    r"freelancer\s+arıyoruz|geliştirici\s+arıyoruz)\b|"
    r"\b(?:looking\s+for\s+(?:an?\s+)?(?:agency|developer|software\s+firm)|"
    r"need\s+(?:an?\s+)?(?:agency|developer)|request\s+for\s+proposal)\b)",
    re.I,
)
TECH_WORDS = re.compile(
    r"(?:\b(?:crm|erp|seo|web\s*sitesi|internet\s*sitesi|web\s*tasarım|"
    r"yazılım|otomasyon|e[-\s]?ticaret|mobil\s*uygulama|rezervasyon\s*sistemi|"
    r"randevu\s*sistemi|stok\s*takip|api\s*entegrasyon|"
    r"website|software|booking\s*system|automation)\b)", re.I,
)
NEGATIVE_WORDS = re.compile(
    r"(?:\b(?:iş\s*ilanı|tam\s*zamanlı|part\s*time|full\s*time|cv\s*gönder|"
    r"maaş|stajyer|staj|job\s*opening|we\s+are\s+hiring|"
    r"kurs|eğitim\s+programı|tutorial|freelancer\s+olarak\s+hizmet|"
    r"biz\s+web\s+sitesi\s+yapıyoruz|web\s+tasarım\s+hizmeti|"
    r"yazılım\s+hizmeti\s+veriyoruz|hizmetlerimiz|"
    r"nasıl\s+yapılır|how\s+to|müşterim\s+için|"
    r"başvuru\s+kabul|ihale|teminat|ekap)\b)", re.I,
)
MARKET_TOKENS = {
    "KKTC": re.compile(r"(?:\bKKTC\b|\bKuzey\s+Kıbrıs\b|\bGirne\b|\bGazimağusa\b|\bLefkoşa\b|\bİskele\b|\bFamagusta\b|\bKyrenia\b|\bTRNC\b)", re.I),
    "TR": re.compile(r"(?:\bTürkiye\b|\bİstanbul\b|\bAnkara\b|\bİzmir\b|\bBursa\b|\bAntalya\b|\bAdana\b|\bMersin\b|\bKonya\b|\bGaziantep\b|\bTurkey\b)", re.I),
}


def utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("Naive timestamps are prohibited")
    return dt.astimezone(timezone.utc)


def parse_iso(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Missing ISO-8601 timestamp")
    return utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def canonical_url(value: str) -> str:
    if not isinstance(value, str) or not value or any(c.isspace() for c in value):
        raise ValueError("Invalid URL")
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.port is not None:
        raise ValueError("Only public HTTPS URLs without credentials/port are supported")
    host = parts.hostname.lower().rstrip(".")
    if "." not in host or ".." in host or host.endswith(".local") or host in {"localhost", "127.0.0.1"}:
        raise ValueError("Invalid hostname")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("IP literal URLs are not accepted")
    if host in BLOCKED_HOSTS or any(host.endswith("." + h) for h in BLOCKED_HOSTS):
        raise ValueError("Membership-only or unsupported marketplace URL")
    return urlunsplit(("https", host, parts.path or "/", parts.query, ""))


def compact(value: str) -> str:
    return " ".join(str(value or "").split())[:12000]


@dataclass(frozen=True)
class Discovery:
    source_url: str
    title: str
    excerpt: str
    discovered_at: str
    indexed_at: str | None = None
    platform: str = "public_search"


def discovery_id(source_url: str) -> str:
    return sha256(canonical_url(source_url).encode()).hexdigest()[:20]


def make_candidate(signal: Discovery) -> tuple[dict | None, str]:
    """Weak signals go to review, NEVER to an automatic sales alert."""
    try:
        url = canonical_url(signal.source_url)
        parse_iso(signal.discovered_at)
    except (ValueError, TypeError):
        return None, "invalid_source"
    text = compact(signal.title + " " + signal.excerpt)
    if not text:
        return None, "empty"
    if NEGATIVE_WORDS.search(text):
        return None, "employment_supplier_education_or_tender"
    if not BUY_WORDS.search(text) or not TECH_WORDS.search(text):
        return None, "no_direct_buyer_signal"
    hints = [market for market, pattern in MARKET_TOKENS.items() if pattern.search(text)]
    if not hints:
        return None, "geography_unsubstantiated"
    if len(hints) > 1:
        return None, "geography_ambiguous"
    return {
        "candidate_id": discovery_id(url),
        "source_url": url,
        "title": compact(signal.title)[:240],
        "excerpt": compact(signal.excerpt)[:5000],
        "market_hint_unverified": hints[0],
        "discovered_at": signal.discovered_at,
        "indexed_at_not_publication_date": signal.indexed_at,
        "status": "REVIEW_REQUIRED",
        "verified_buyer": False,
        "contact_verified": False,
        "sales_outreach_allowed": False,
    }, "review_required"


def _contact_allowed(contact: dict) -> bool:
    kind, value = contact.get("kind"), str(contact.get("value") or "").strip()
    if kind == "email":
        return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+%-]{0,100}@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", value))
    if kind == "phone":
        return bool(re.fullmatch(r"\+[1-9][0-9]{7,14}", value))
    if kind == "website_contact":
        try:
            canonical_url(value)
        except ValueError:
            return False
        return True
    return False


def qualify(candidate: dict, review: dict, *, now: datetime) -> tuple[dict | None, str]:
    """Manual signed evidence required before contactability review is accepted."""
    try:
        now = utc(now)
        if candidate.get("status") != "REVIEW_REQUIRED":
            return None, "not_from_discovery"
        if not review or review.get("candidate_id") != candidate.get("candidate_id"):
            return None, "missing_matching_human_review"
        if review.get("decision") != "approve":
            return None, "not_approved"
        if not isinstance(review.get("reviewer"), str) or len(review["reviewer"].strip()) < 2:
            return None, "reviewer_missing"
        reviewed = parse_iso(review["reviewed_at"])
        published = parse_iso(review["source_published_at"])
        if published > reviewed or reviewed > now + timedelta(minutes=2) or published > now:
            return None, "chronology_invalid"
        if now - published > timedelta(days=MAX_AGE_DAYS) or now - reviewed > timedelta(days=2):
            return None, "stale_request_or_review"
        if review.get("country") not in SUPPORTED_MARKETS or review["country"] != candidate.get("market_hint_unverified"):
            return None, "market_unverified_or_mismatch"
        if not review.get("buyer_company") or not str(review["buyer_company"]).strip():
            return None, "buyer_company_missing"
        if review.get("request_is_external_contract") is not True or review.get("agency_eligible") is not True:
            return None, "employment_or_agency_eligibility_unverified"
        original = compact(candidate.get("title", "") + " " + candidate.get("excerpt", ""))
        quote = compact(review.get("buyer_request_quote", ""))
        if len(quote) < 12 or quote.casefold() not in original.casefold():
            return None, "buyer_quote_not_in_source_excerpt"
        if review.get("buyer_company_checked_directly") is not True:
            return None, "buyer_identity_not_verified"
        try:
            url = canonical_url(review["source_url"])
            evidence_url = canonical_url(review["contact_evidence_url"])
            canonical_url(review["buyer_company_evidence_url"])
        except (ValueError, KeyError):
            return None, "evidence_links_missing_or_blocked"
        if url != candidate.get("source_url"):
            return None, "source_link_mismatch"
        contact = review.get("contact")
        if not isinstance(contact, dict) or not _contact_allowed(contact):
            return None, "contact_invalid_or_membership_only"
        if review.get("contact_checked_directly") is not True or review.get("source_publication_checked_directly") is not True:
            return None, "external_contact_or_date_not_verified"
        return {
            "lead_id": candidate["candidate_id"],
            "status": "CONTACTABLE_UNCONFIRMED",
            "company": compact(review["buyer_company"]),
            "market": review["country"],
            "source_url": url,
            "source_published_at": review["source_published_at"],
            "buyer_request_quote": quote,
            "contact": {"kind": contact["kind"], "value": contact["value"]},
            "contact_evidence_url": evidence_url,
            "reviewed_by": review["reviewer"],
            "reviewed_at": review["reviewed_at"],
            "confirmed_currently_open": False,
            "outreach_authorized_automatically": False,
            "sale_won": False,
        }, "contactable_unconfirmed"
    except (KeyError, TypeError, ValueError):
        return None, "invalid_review"


def confirm_opportunity(contactable: dict, buyer_reply: dict, *, now: datetime) -> tuple[dict | None, str]:
    """The buyer's recent reply, not a website gap, establishes open demand."""
    try:
        now = utc(now)
        if contactable.get("status") != "CONTACTABLE_UNCONFIRMED":
            return None, "not_contactable_review"
        if buyer_reply.get("buyer_confirmed_open") is not True:
            return None, "no_buyer_confirmation"
        reply_date = parse_iso(buyer_reply["replied_at"])
        if reply_date > now or now - reply_date > timedelta(days=7):
            return None, "stale_or_future_confirmation"
        if not isinstance(buyer_reply.get("reviewed_by"), str) or len(buyer_reply["reviewed_by"].strip()) < 2:
            return None, "confirmation_reviewer_missing"
        evidence = str(buyer_reply.get("reply_evidence_reference") or "").strip()
        if not evidence.startswith(("gmail:", "mailbox:", "call-note:", "whatsapp-record:")) or len(evidence) < 12:
            return None, "buyer_reply_evidence_missing"
        return {
            **contactable,
            "status": "QUALIFIED_OPPORTUNITY",
            "confirmed_currently_open": True,
            "buyer_reply_at": buyer_reply["replied_at"],
            "buyer_reply_evidence_reference": evidence,
            "confirmed_by": buyer_reply["reviewed_by"],
            "sale_won": False,
        }, "qualified_opportunity"
    except (KeyError, TypeError, ValueError):
        return None, "invalid_confirmation"
