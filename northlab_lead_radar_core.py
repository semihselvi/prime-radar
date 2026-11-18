from __future__ import annotations

import asyncio
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

import nc_v6_broad_radar as radar


VERSION = "1.2-recall-first-wide-net"


def is_actionable_buyer(lead: dict[str, Any]) -> bool:
    """Use the exact same delivery policy as the Telegram notification boundary."""
    eligible, _reason = radar.buyer_notification_eligibility(lead)
    return eligible


def _record_review_pending(db, lead: dict[str, Any], reason: str, now: datetime) -> bool:
    """Persist uncertain buyers for human verification without sending an alert."""
    lead_id = str(lead.get("lead_id") or "")
    if not lead_id:
        return False
    ref = db.collection(radar.core.COLLECTION).document(lead_id)
    snap = ref.get()
    previous = (snap.to_dict() or {}) if snap.exists else {}
    if previous.get("buyer_review_status") in {"dismissed", "approved", "contacted", "completed"}:
        return False
    if previous.get("buyer_review_status") == "pending" and previous.get("buyer_review_reason") == reason:
        return False
    ref.set({
        "buyer_review_status": "pending",
        "buyer_review_reason": reason,
        "buyer_review_at": now.isoformat(),
    }, merge=True)
    return True


def recover_recent_unnotified(db, now: datetime, max_send: int = 3) -> dict[str, int]:
    """Bounded 14-day replay of accepted but never notified Telegram leads.

    Already-notified rows are never resent. Reclassify against current rules
    rather than relying on stale labels. This does NOT scrape old rejected posts.
    """
    stats = {"scanned": 0, "eligible": 0, "notified": 0, "review_saved": 0, "errors": 0}
    if max_send <= 0:
        return stats
    cutoff = (now - timedelta(days=14)).isoformat()
    try:
        rows = (
            db.collection(radar.core.COLLECTION)
            .where("message_time", ">=", cutoff)
            .limit(180)
            .stream()
        )
        for snap in rows:
            stats["scanned"] += 1
            if stats["notified"] >= max_send:
                break
            lead = snap.to_dict() or {}
            if str(lead.get("platform") or lead.get("source") or "").casefold() != "telegram":
                continue
            if any(lead.get(k) for k in ("v5_notified_at", "v6_notified_at", "core_notified_at")):
                continue
            message = str(lead.get("message") or lead.get("text") or "")
            signal, _reason = radar.classify_text(
                message,
                group=str(lead.get("group") or ""),
                author=str(lead.get("author") or ""),
            )
            if signal is None:
                continue
            candidate = {**lead, **signal, "lead_id": snap.id}
            eligible, reason = radar.buyer_notification_eligibility(candidate)
            if not eligible:
                if reason == "buyer_needs_review":
                    if _record_review_pending(db, candidate, reason, now):
                        stats["review_saved"] += 1
                continue
            stats["eligible"] += 1
            if radar.notify_lead(candidate, "RECOVERED"):
                _mark_notified(db, candidate, now)
                stats["notified"] += 1
    except Exception as exc:
        stats["errors"] += 1
        print("PRIME_BUYER_RECOVERY_ERROR", type(exc).__name__, str(exc)[:300])
    return stats


def _mark_notified(db, lead: dict[str, Any], when: datetime) -> None:
    lead_id = str(lead.get("lead_id") or "")
    if not lead_id:
        return
    db.collection(radar.core.COLLECTION).document(lead_id).set(
        {
            "v6_notified_at": when.isoformat(),
            "core_notified_at": when.isoformat(),
            "core_version": VERSION,
        },
        merge=True,
    )


@contextmanager
def _prime_scan_environment():
    """Scope legacy environment-driven policy to one scan; never leak it to later runs."""
    defaults = {
        "RADAR_GLOBAL_TELEGRAM_DAYS": "30",
        "RADAR_PUBLIC_PEER_SCAN_LIMIT": "180",
        "RADAR_LEARNED_TELEGRAM_QUERIES": "40",
        "RADAR_SOURCE_EXPANSION_SEEDS": "16",
        "RADAR_SOURCE_EXPANSION_CANDIDATES": "48",
    }
    keys = ("RADAR_SALES_ONLY", *defaults)
    previous = {key: os.environ.get(key) for key in keys}
    os.environ["RADAR_SALES_ONLY"] = "1"
    for key, value in defaults.items():
        os.environ.setdefault(key, value)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


async def scan_once() -> dict[str, Any]:
    with _prime_scan_environment():
        return await _scan_once_with_policy()


async def _scan_once_with_policy() -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    db = radar.core.db()

    result = await radar.broad_telegram_scan(db, started)
    if str(result.get("status") or "").startswith("skipped"):
        raise RuntimeError("PRIME_BUYER_TELEGRAM_SCAN_UNAVAILABLE: " + str(result.get("status")))
    raw = list(result.get("new_leads") or [])
    buyers = []
    review_saved = 0
    for lead in raw:
        eligible, reason = radar.buyer_notification_eligibility(lead)
        if eligible:
            buyers.append(lead)
        elif reason == "buyer_needs_review":
            if _record_review_pending(db, lead, reason, started):
                review_saved += 1

    notified = 0
    for lead in buyers:
        if radar.notify_lead(lead, "NEW"):
            _mark_notified(db, lead, started)
            notified += 1

    recovery = recover_recent_unnotified(db, started)
    summary = {
        "recovery": recovery,
        "version": VERSION,
        "status": result.get("status", "unknown"),
        "groups": result.get("groups", 0),
        "messages": result.get("messages", 0),
        "raw_new": len(raw),
        "buyers": len(buyers),
        "review_saved": review_saved,
        "notified": notified,
        "group_discovery_joined": result.get("group_discovery_joined", 0),
        "group_discovery_joined_samples": result.get("group_discovery_joined_samples", []),
        "group_discovery_found": result.get("group_discovery_found", 0),
        "public_bootstrap_seeds": radar.DEBUG.get("source_expansion_bootstrap_seeds", 0),
        "public_seed_fetch_ok": radar.DEBUG.get("source_expansion_seed_fetch_ok", 0),
        "public_seed_valid_matches": radar.DEBUG.get("source_expansion_seed_valid_matches", 0),
        "errors": result.get("errors", 0),
        "joined_groups_total": result.get("candidate_first_total_groups", 0),
        "joined_groups_count": radar.DEBUG.get("joined_groups_count", 0),
        "joined_channels_count": radar.DEBUG.get("joined_channels_count", 0),
        "joined_hours": radar.DEBUG.get("joined_scan_hours", 0),
        "joined_primary_signal_pass": radar.DEBUG.get("signal_pass", 0),
        "joined_rejections": dict(radar.DEBUG.get("reject_reasons") or {}),
        "buyer_reject_public_links": dict(radar.DEBUG.get("buyer_reject_public_links") or {}),
        "joined_extra_messages": radar.DEBUG.get("strict_extra_messages_scanned", 0),
        "global_search_raw": radar.DEBUG.get("global_search_raw", 0),
        "global_search_signal_pass": radar.DEBUG.get("global_search_signal_pass", 0),
        "global_search_accepted": radar.DEBUG.get("global_search_accepted", 0),
        "global_search_rejections": dict(radar.DEBUG.get("global_search_reject_reasons") or {}),
        "review_qualified": radar.DEBUG.get("review_qualified", 0),
        "started_at": started.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

    # Logs only. No zero-result/debug Telegram messages.
    print("PRIME_KIBRIS_BUYER_RADAR", summary)
    return summary


def main() -> None:
    asyncio.run(scan_once())


if __name__ == "__main__":
    main()
