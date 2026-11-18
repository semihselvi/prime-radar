"""One-time private admin handoff of manually reviewable public buyer signals.

NOT a lead notification. Does not contact prospects. No personal content in GitHub logs.
Idempotent Firestore claim prevents repeat sends on CI retry.
"""
from __future__ import annotations
from datetime import datetime, timezone
from collections import Counter
import os
import re
import requests
from google.api_core.exceptions import AlreadyExists, Conflict
import main as core
import nc_v6_broad_radar as radar

START = "2026-11-18T08:00:00+00:00"
END = "2026-11-19T00:00:00+00:00"
MARKER = "prime-review-handoff-2026-11-18"
max_items = 5

def dt(v):
    try:
        item=datetime.fromisoformat(str(v or ""))
        return item.replace(tzinfo=timezone.utc) if item.tzinfo is None else item
    except (TypeError,ValueError):
        return None

def run():
    db=core.db()
    found=[]
    seen=set()
    counts=Counter()
    for doc in db.collection(core.COLLECTION).where("found_at", ">=", START).limit(450).stream():
        x=doc.to_dict() or {}
        timestamp=dt(x.get("found_at"))
        if timestamp is None or timestamp>=dt(END): continue
        if str(x.get("platform") or x.get("source") or "").lower()!="telegram":continue
        eligible,reason=radar.buyer_notification_eligibility(x)
        if eligible or reason!="buyer_needs_review":continue
        if x.get("buyer_review_status")!="pending":continue
        if any(x.get(k) for k in ("v5_notified_at","v6_notified_at","core_notified_at")):continue
        url=str(x.get("url") or "").strip()
        author=str(x.get("author") or "").strip()
        message=" ".join(str(x.get("message") or x.get("text") or "").split())
        score=int(x.get("intent_score") or 0)
        specifics=int(x.get("specificity") or 0)
        match=re.fullmatch(r"https?://t\.me/(?:s/)?[A-Za-z0-9_]+/\d+(?:\?[^\s]*)?",url)
        if not match or not author or author in {"-","unknown"} or not message:continue
        key=url.split("?")[0].lower()
        if key in seen:continue
        seen.add(key)
        counts["review_candidates"]+=1
        # Buyer-shaped but ambiguous. High-specificity evidence goes to HUMAN
        # review only, never through HOT/WARM automatic sales notifications.
        if specifics < 2:continue
        counts["specific_review"]+=1
        recency=dt(x.get("message_time"))
        age_days=(datetime.now(timezone.utc)-recency).total_seconds()/86400 if recency else 100
        if age_days > 30:continue
        found.append((specifics,score,-age_days,author,message,url))
    found.sort(reverse=True)
    chosen=found[:max_items]
    print("PRIME_REVIEW_HANDOFF_COUNTS",dict(counts),
          "chosen",len(chosen),"message_text_redacted",True)
    if not chosen:return
    token=os.getenv("TELEGRAM_BOT_TOKEN","").strip()
    chat=os.getenv("TELEGRAM_CHAT_ID","").strip()
    if not token or not chat:raise RuntimeError("Admin Telegram destination not configured")
    marker=db.collection("prime_buyer_review_handoff_runs").document(MARKER)
    try:
        marker.create({"status":"claimed","claimed_at":datetime.now(timezone.utc).isoformat(),
                       "count":len(chosen)})
    except (AlreadyExists,Conflict):
        print("PRIME_REVIEW_HANDOFF_SKIPPED_ALREADY_CLAIMED")
        return
    chunks=["PRIME KIBRIS | MANUEL ALICI INCELEMESI",
            "Bunlar dogrulanmis alici / satis firsati DEGILDIR.",
            "Otomatik HOT bildirimi yerine insan kontrolu icin secilen kayitlar:"]
    for i, (specificity,score,age,author,msg,url) in enumerate(chosen,1):
        chunks.append(f"{i}) {author} | sinyal {score}/100 | ayrinti {specificity}\n{msg[:230]}\n{url}")
    chunks.append("Once satin alma niyetini, guncelligi ve dogrudan iletisim uygunlugunu teyit edin.")
    body="\n\n".join(chunks)
    try:
        resp=requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                           json={"chat_id":chat,"text":body,"disable_web_page_preview":True},
                           timeout=20)
        resp.raise_for_status()
        response=resp.json()
        if response.get("ok") is not True:raise RuntimeError("Telegram returned ok=false")
        marker.set({"status":"delivered","delivered_at":datetime.now(timezone.utc).isoformat(),
                    "telegram_message_id":response.get("result",{}).get("message_id")},merge=True)
        print("PRIME_REVIEW_HANDOFF_SUCCESS",len(chosen),"private_telegram_only")
    except Exception as exc:
        marker.set({"status":"uncertain","error_type":type(exc).__name__},merge=True)
        raise RuntimeError("Review handoff ambiguous; no automatic retry") from exc

if __name__=="__main__":
    run()
