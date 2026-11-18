import json
from datetime import datetime, timezone
import main as core

START = datetime.fromisoformat("2026-10-07T12:24:00+00:00")

def parse_dt(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z","+00:00"))
    except Exception:
        return None

def main():
    """Aggregate buyer-delivery audit without exposing customer messages in CI logs."""
    db = core.db()
    rows = []
    for snap in db.collection(core.COLLECTION).stream():
        data = snap.to_dict() or {}
        timestamp = parse_dt(data.get("v6_notified_at") or data.get("core_notified_at"))
        if timestamp is None or timestamp < START:
            continue
        rows.append((timestamp, data))
    rows.sort(key=lambda item: item[0])

    from collections import Counter
    classes = Counter(str(data.get("lead_class") or "unknown") for _time, data in rows)
    languages = Counter(str(data.get("language") or "unknown") for _time, data in rows)
    summary = {
        "count": len(rows),
        "since": START.isoformat(),
        "first_notified_at": rows[0][0].isoformat() if rows else None,
        "last_notified_at": rows[-1][0].isoformat() if rows else None,
        "class_counts": dict(classes),
        "language_counts": dict(languages),
        "missing_source_link": sum(1 for _time, data in rows if not data.get("url")),
        "details_redacted": True,
    }
    print("RECENT_BUYER_AUDIT", json.dumps(summary, ensure_ascii=False))


if __name__=="__main__":
    main()
