"""Read-only, aggregate-only audit of Prime buyer funnel (no customer text or URLs)."""
from collections import Counter
from datetime import datetime, timezone, timedelta
import json
import main as core
import nc_v6_broad_radar as radar

CUTOFF = datetime(2026,11,18,8,0,0,tzinfo=timezone.utc)
END = datetime(2026,11,19,0,0,0,tzinfo=timezone.utc)
db = core.db()
reasons, classes, sources, notified = Counter(),Counter(),Counter(),Counter()
buyer_pool = Counter()
rows = db.collection(core.COLLECTION).where("found_at", ">=", CUTOFF.isoformat()).limit(450).stream()
total=0
for snap in rows:
    d=snap.to_dict() or {}
    try:
        found=datetime.fromisoformat(str(d.get("found_at") or ""))
        if found.tzinfo is None: found=found.replace(tzinfo=timezone.utc)
        if found >= END: continue
    except (ValueError, TypeError): continue
    if str(d.get("platform") or d.get("source") or "").casefold()!="telegram": continue
    total+=1
    eligibility, reason=radar.buyer_notification_eligibility(d)
    reasons[reason]+=1
    classes[str(d.get("lead_class") or "missing")]+=1
    sources[str(d.get("source_type") or "unknown")]+=1
    buyer_pool[str(d.get("intent_type") or "missing")]+=1
    if eligibility: notified["eligible"]+=1
    if any(d.get(k) for k in ("v5_notified_at","v6_notified_at","core_notified_at")): notified["already_notified"]+=1
    if d.get("buyer_review_status")=="pending": notified["review_pending"]+=1
# Never emit personal information, authored texts, URLs, record ids, or secrets.
print("PRIME_FUNNEL_AUDIT",json.dumps({
    "window_start":CUTOFF.isoformat(),"window_end":END.isoformat(),
    "sample_count":total,"limit":450,
    "eligibility_reasons":dict(reasons),"lead_classes":dict(classes),
    "intent_types":dict(buyer_pool),"source_types":dict(sources),
    "delivery_and_review":dict(notified),
    "privacy":"aggregate_only","read_only":True,
},ensure_ascii=False))
