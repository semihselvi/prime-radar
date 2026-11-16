"""NorthLab v3: independent, evidence-led discovery and review pipeline."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from .core import qualify, confirm_opportunity
from .discover import scan


def review_candidates(report: dict, reviews: list[dict], confirmations: list[dict], *, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    if not isinstance(report.get("review_queue"), list) or not isinstance(reviews, list) or not isinstance(confirmations, list):
        raise ValueError("Invalid input schema")
    review_ids = [r.get("candidate_id") for r in reviews if isinstance(r, dict)]
    if len(review_ids) != len(set(review_ids)):
        raise ValueError("Duplicate human review IDs")
    confirmations_by_id = {}
    for r in confirmations:
        key = r.get("candidate_id") if isinstance(r, dict) else None
        if not isinstance(key, str) or key in confirmations_by_id:
            raise ValueError("Invalid or duplicate confirmation IDs")
        confirmations_by_id[key] = r
    reviews_by_id = {r["candidate_id"]: r for r in reviews if isinstance(r, dict) and "candidate_id" in r}
    contactable, qualified, rejections = [], [], []
    for candidate in report["review_queue"]:
        if not isinstance(candidate, dict) or "candidate_id" not in candidate:
            continue
        lead, reason = qualify(candidate, reviews_by_id.get(candidate["candidate_id"]), now=now)
        if not lead:
            rejections.append({"candidate_id": candidate["candidate_id"], "reason": reason})
            continue
        contactable.append(lead)
        confirmation = confirmations_by_id.get(candidate["candidate_id"])
        if confirmation:
            opened, reason = confirm_opportunity(lead, confirmation, now=now)
            if opened:
                qualified.append(opened)
            else:
                rejections.append({"candidate_id": candidate["candidate_id"], "reason": reason})
    return {
        "stage": "MANUAL_REVIEW_ONLY",
        "contactable_unconfirmed_count": len(contactable),
        "qualified_opportunity_count": len(qualified),
        "outreach_messages_sent": 0,
        "contactable_unconfirmed": contactable,
        "qualified_opportunities": qualified,
        "rejections": rejections,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="NorthLab v3 safe sales radar")
    sub = parser.add_subparsers(dest="command", required=True)
    discovery = sub.add_parser("discover")
    discovery.add_argument("--out", default="northlab-v3-shadow.json")
    review = sub.add_parser("review")
    review.add_argument("--input", required=True)
    review.add_argument("--reviews", required=True)
    review.add_argument("--confirmations")
    review.add_argument("--out", default="northlab-v3-reviewed.json")
    args = parser.parse_args(argv)
    if args.command == "discover":
        result = scan()
        keys = ("status", "query_count", "successful_search_feeds", "raw_results",
                "review_queue_count", "qualified_lead_count", "contacts_sent")
        code = 0 if result["status"] != "SOURCE_FAILURE" else 2
    else:
        report = json.loads(Path(args.input).read_text(encoding="utf-8"))
        reviews = json.loads(Path(args.reviews).read_text(encoding="utf-8"))
        confirmations = json.loads(Path(args.confirmations).read_text(encoding="utf-8")) if args.confirmations else []
        result = review_candidates(report, reviews, confirmations)
        keys = ("stage", "contactable_unconfirmed_count", "qualified_opportunity_count", "outreach_messages_sent")
        code = 0
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: result[k] for k in keys}, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
