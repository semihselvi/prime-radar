"""Evidence-based sales notification gate.

The classifier is a broad discovery stage. A source snippet containing words such
as 'need a website' is not proof that its author wants to buy development.
Only an attributable buyer-side project request may be sent as a sales alert.
Unattributable, weak or ambiguous records remain available for manual review.
"""
from __future__ import annotations

import re
from typing import Any


# Requiring a buyer-speaker (rather than an SEO keyword) is deliberate:
# "Need a website for your business?" is not the advertiser buying a website.
BUYER_SPEAKER_RE = re.compile(
    r"(?:"
    r"\b(?:we|i)\s+(?:really\s+)?(?:need|want|are\s+looking\s+for|am\s+looking\s+for|"
    r"are\s+seeking|am\s+seeking|would\s+like\s+to|plan\s+to|want\s+to\s+hire)\b|"
    r"\b(?:our|my)\s+(?:business|company|restaurant|hotel|clinic|store|shop|agency|team)\b"
    r".{0,90}\b(?:need|needs|want|wants|looking\s+for|seeking|hire|hiring|redesign)\b|"
    r"\b(?:looking\s+for|seeking|hiring)\s+(?:a\s+|an\s+)?"
    r"(?:developer|agency|web\s+designer|software\s+company|someone)\b"
    r".{0,120}\b(?:my|our|company|business|project|build|develop|redesign)\b|"
    r"\b(?:firmam[ıi]z|i[sş]letmemiz|[sş]irketimiz|bizim\s+(?:i[sş]letme|[sş]irket))\b"
    r".{0,140}\b(?:laz[ıi]m|ihtiyac|ar[ıi]yoruz|yapt[ıi]rmak|teklif|geli[sş]tir)\w*|"
    r"\b(?:нам|мы|нашему\s+бизнесу|нашей\s+компании|для\s+нашей\s+компании)\b"
    r".{0,140}\b(?:нужен|нужна|нужно|ищем|разработ|создать|сделать|система|систему)\w*|"
    r"\b(?:нужен|нужна|нужно)\b.{0,90}\b(?:для\s+нашей\s+компании|для\s+нашего\s+бизнеса)\b"
    r")",
    re.I | re.S,
)

# A user asking somebody to USE an existing site is not buying a site.
EXISTING_SITE_TASK_RE = re.compile(
    r"(?:зарегистрирова\w*|регистрац\w*|авторизова\w*|"
    r"login|log\s*in|sign\s*up|register\s+(?:on|at|to)|"
    r"oturum\s+a[çc]|kay[ıi]t\s+ol)\b.{0,100}"
    r"(?:\b(?:сайт\w*|site|website|магазин\w*|shop|portal)\b)|"
    r"\b(?:на|в|через)\s+сайт\w*\b.{0,100}"
    r"(?:зарегистрирова\w*|регистрац\w*|войти|вход)",
    re.I | re.S,
)

# Generic educational questions do not identify a commissioning buyer.
EDITORIAL_QUESTION_RE = re.compile(
    r"(?:\bdo\s+i\s+need\s+a\s+website\b|\bwhat\s+is\s+(?:a\s+)?website\b|"
    r"\bhow\s+to\s+(?:build|create|make)\s+(?:a\s+)?website\b)",
    re.I,
)

# These represent a demand FOR professional creation, not a verb about using a site.
COMMISSION_RE = re.compile(
    r"(?:\b(?:build|redesign|develop|create|implement|integrate|automate|replace|hire|hiring|contract|"
    r"developer|designer|agency|web\s+development|software|crm|booking\s+system|web\s+app|mobile\s+app)\b|"
    r"\b(?:website|web\s*site|e[-\s]?commerce)\b.{0,80}\b(?:for\s+(?:our|my)|redesign|build|developer)\b|"
    r"\b(?:web\s+sitesi|yaz[ıi]l[ıi]m|otomasyon|entegrasyon|crm|"
    r"rezervasyon\s+sistemi|geli[sş]tir|yapt[ıi]r)\w*|"
    r"\b(?:разработчик\w*|разработ\w*|созда\w*|сдела\w*|"
    r"систем\w*|веб[-\s]?сайт\w*|автоматизац\w*|интеграц\w*)\b)",
    re.I | re.S,
)


def qualify_for_sales_alert(lead: dict[str, Any]) -> tuple[str, str]:
    """Return (ready|review|reject, reason). Never treat keyword score as buyer evidence."""
    text = " ".join(str(lead.get("text") or lead.get("message") or "").split())
    if not text:
        return "reject", "empty_content"
    if EXISTING_SITE_TASK_RE.search(text):
        return "reject", "existing_site_task_not_development"
    if EDITORIAL_QUESTION_RE.search(text):
        return "reject", "editorial_question_not_purchase"

    # The broad classifier already removes many providers. This positive
    # gate is independent and does not promote third-party promotional copy.
    if not BUYER_SPEAKER_RE.search(text) or not COMMISSION_RE.search(text):
        return "reject", "no_attributable_buyer_project_request"

    if not str(lead.get("url") or "").strip():
        return "review", "source_link_missing"
    author = str(lead.get("author") or "").strip()
    if not author or author in {"-", "unknown", "anonymous"}:
        return "review", "buyer_identity_unverified"
    return "ready", "attributed_buyer_request"
