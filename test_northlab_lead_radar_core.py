import os
import unittest
from datetime import datetime, timezone
from google.api_core.exceptions import AlreadyExists
from unittest.mock import AsyncMock, MagicMock, patch

import northlab_lead_radar_core as core

def is_actionable_buyer(lead):
    return core.radar.buyer_notification_eligibility(lead)[0]



class NorthlabLeadRadarCoreTests(unittest.TestCase):
    def test_accepts_explicit_hot_buyer(self):
        self.assertTrue(is_actionable_buyer({
            "market": "north_cyprus",
            "intent_type": "BUYER",
            "lead_class": "HOT BUYER",
            "message": "Куплю квартиру 3+1 в Querencia.",
            "lead_reasons": ["explicit_purchase_intent"],
            "specificity": 2,
        }))

    def test_accepts_specific_owner_direct_search(self):
        self.assertTrue(is_actionable_buyer({
            "market": "north_cyprus",
            "intent_type": "BUYER",
            "lead_class": "WARM BUYER",
            "message": "Ищу кто продает от собственника 2+1 в 4 очереди Цезаря",
            "lead_reasons": ["implicit_property_demand", "owner_direct_buyer_preference"],
            "intent_score": 80,
            "specificity": 3,
        }))

    def test_rejects_implicit_property_demand(self):
        self.assertFalse(is_actionable_buyer({
            "market": "north_cyprus",
            "intent_type": "BUYER",
            "lead_class": "WARM BUYER",
            "message": "Ищу квартиру 2+1 на Северном Кипре",
            "lead_reasons": ["implicit_property_demand"],
            "specificity": 1,
        }))

    def test_rejects_property_research_signal(self):
        self.assertFalse(is_actionable_buyer({
            "market": "north_cyprus",
            "intent_type": "BUYER",
            "lead_class": "WARM BUYER",
            "message": "Какие квартиры лучше смотреть на Северном Кипре?",
            "lead_reasons": ["property_research_signal"],
            "specificity": 1,
        }))

    def test_rejects_tenant(self):
        self.assertFalse(is_actionable_buyer({
            "market": "north_cyprus",
            "intent_type": "TENANT",
            "lead_class": "HOT TENANT",
            "message": "Сниму 1+1 в Искеле на шесть месяцев.",
        }))

    def test_rejects_relocation_and_investor_chatter(self):
        self.assertFalse(is_actionable_buyer({
            "market": "north_cyprus",
            "intent_type": "RELOCATION",
            "lead_class": "RELOCATION",
            "message": "Thinking about moving to North Cyprus.",
        }))
        self.assertFalse(is_actionable_buyer({
            "market": "north_cyprus",
            "intent_type": "INVESTOR",
            "lead_class": "INVESTOR",
            "message": "What are the yields in North Cyprus?",
        }))

    def test_rejects_car_purchase_even_if_upstream_labels_buyer(self):
        self.assertFalse(is_actionable_buyer({
            "market": "north_cyprus",
            "intent_type": "BUYER",
            "lead_class": "HOT BUYER",
            "author": "@anna_smrnva",
            "message": "Куплю авто ~5000£ либо с первым взносом в рассрочку",
            "lead_reasons": ["explicit_purchase_intent"],
            "specificity": 2,
        }))

    def test_rejects_buyer_label_if_message_is_rental(self):
        self.assertFalse(is_actionable_buyer({
            "market": "north_cyprus",
            "intent_type": "BUYER",
            "lead_class": "HOT BUYER",
            "message": "Looking to rent a 1+1 in Iskele for six months.",
            "lead_reasons": ["explicit_purchase_intent"],
            "specificity": 2,
        }))


class PrimeBuyerNotificationRecoveryTests(unittest.TestCase):
    def test_project_only_property_name_passes_final_gate(self):
        self.assertTrue(is_actionable_buyer({
            "market": "north_cyprus",
            "intent_type": "BUYER",
            "lead_class": "HOT BUYER",
            "message": "Куплю в Caesar Resort",
            "lead_reasons": ["explicit_purchase_intent"],
            "specificity": 1,
        }))

    def test_delivery_failure_does_not_claim_sent(self):
        lead = {
            "market": "north_cyprus",
            "intent_type": "BUYER",
            "lead_class": "HOT BUYER",
            "message": "Куплю квартиру 2+1 в Caesar Resort",
            "lead_reasons": ["explicit_purchase_intent"],
            "specificity": 2,
        }
        with patch.object(core.radar.core, "telegram", return_value=False):
            self.assertFalse(core.radar.notify_lead(lead))
        with patch.object(core.radar.core, "telegram", return_value=True):
            self.assertTrue(core.radar.notify_lead(lead))

    def test_recovery_only_sends_unnotified_qualified_recent_telegram(self):
        delivered_before = MagicMock()
        delivered_before.id = "sent"
        delivered_before.to_dict.return_value = {
            "platform": "Telegram",
            "market": "north_cyprus",
            "message": "Куплю квартиру 2+1 в Caesar Resort",
            "v6_notified_at": "2026-11-10T12:00:00+00:00",
        }
        unnotified = MagicMock()
        unnotified.id = "missed"
        unnotified.to_dict.return_value = {
            "platform": "Telegram",
            "market": "north_cyprus",
            "message": "Куплю квартиру 2+1 в Caesar Resort",
            "group": "North Cyprus Expats",
        }
        db = MagicMock()
        db.collection.return_value.where.return_value.limit.return_value.stream.return_value = iter([
            delivered_before, unnotified,
        ])
        from datetime import datetime, timezone
        with patch.object(core.radar, "classify_text", return_value=({
            "intent_type": "BUYER",
            "lead_class": "HOT BUYER",
            "lead_reasons": ["explicit_purchase_intent"],
            "specificity": 2,
        }, "accepted")), patch.object(core.radar, "notify_lead", return_value=True) as notify, patch.object(core, "_mark_notified") as mark:
            result = core.recover_recent_unnotified(db, datetime(2026, 11, 12, tzinfo=timezone.utc))
        self.assertEqual(result["scanned"], 2)
        self.assertEqual(result["eligible"], 1)
        self.assertEqual(result["notified"], 1)
        notify.assert_called_once()
        mark.assert_called_once()


class PrimeBuyerPolicyIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def test_scan_restores_environment_after_exception(self):
        with patch.dict(os.environ, {"RADAR_SALES_ONLY": "0"}):
            with patch.object(core.radar.core, "db", return_value=MagicMock()), \
                 patch.object(core.radar, "broad_telegram_scan", new_callable=AsyncMock) as scan:
                scan.return_value = {"status": "skipped_unauthorized", "new_leads": []}
                with self.assertRaises(RuntimeError):
                    await core.scan_once()
            self.assertEqual(os.environ["RADAR_SALES_ONLY"], "0")


class PrimeBuyerScanFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_unauthorized_telegram_scan_fails_workflow(self):
        with patch.object(core.radar.core, "db", return_value=MagicMock()), patch.object(
            core.radar, "broad_telegram_scan", new_callable=AsyncMock
        ) as scan:
            scan.return_value = {"status": "skipped_unauthorized", "new_leads": []}
            with self.assertRaisesRegex(RuntimeError, "skipped_unauthorized"):
                await core.scan_once()


class PrimeBuyerCanonicalGateTests(unittest.TestCase):
    def setUp(self):
        self.uncertain = {
            "lead_id": "review-candidate-001",
            "market": "north_cyprus",
            "intent_type": "BUYER",
            "lead_class": "WARM BUYER",
            "message": "Ищу 2+1 в искеле от собственника с помесячной оплатой",
            "lead_reasons": ["implicit_property_demand", "owner_direct_buyer_preference"],
            "specificity": 2,
            "intent_score": 74,
        }

    def test_uncertain_owner_direct_request_is_review_not_alert(self):
        eligible, reason = core.radar.buyer_notification_eligibility(self.uncertain)
        self.assertFalse(eligible)
        self.assertEqual(reason, "buyer_needs_review")
        self.assertFalse(is_actionable_buyer(self.uncertain))
        with patch.object(core.radar.core, "telegram") as telegram:
            self.assertFalse(core.radar.notify_lead(self.uncertain))
            telegram.assert_not_called()

    def test_stronger_owner_direct_signal_uses_same_final_gate(self):
        stronger = dict(self.uncertain, intent_score=80, specificity=3)
        eligible, reason = core.radar.buyer_notification_eligibility(stronger)
        self.assertTrue(eligible, reason)
        self.assertTrue(is_actionable_buyer(stronger))

    def test_review_queue_is_idempotent(self):
        from datetime import datetime, timezone
        db = MagicMock()
        doc = db.collection.return_value.document.return_value
        doc.get.return_value.exists = False
        now = datetime(2026, 11, 18, tzinfo=timezone.utc)
        self.assertTrue(core._record_review_pending(db, self.uncertain, "buyer_needs_review", now))
        payload = doc.set.call_args.args[0]
        self.assertEqual(payload["buyer_review_status"], "pending")
        self.assertNotIn("v6_notified_at", payload)
        doc.get.return_value.exists = True
        doc.get.return_value.to_dict.return_value = payload
        self.assertFalse(core._record_review_pending(db, self.uncertain, "buyer_needs_review", now))
        self.assertEqual(doc.set.call_count, 1)


class PrimeBuyerReviewScanTests(unittest.IsolatedAsyncioTestCase):
    async def test_scan_persists_uncertain_buyer_without_false_notification(self):
        from datetime import datetime, timezone
        lead = {
            "lead_id": "review-candidate-002",
            "market": "north_cyprus",
            "intent_type": "BUYER",
            "lead_class": "WARM BUYER",
            "message": "Ищу 2+1 в искеле от собственника с помесячной оплатой",
            "lead_reasons": ["implicit_property_demand", "owner_direct_buyer_preference"],
            "specificity": 2,
            "intent_score": 74,
        }
        db = MagicMock()
        db.collection.return_value.document.return_value.get.return_value.exists = False
        with patch.object(core.radar.core, "db", return_value=db), \
             patch.object(core.radar, "broad_telegram_scan", new_callable=AsyncMock) as scan, \
             patch.object(core, "recover_recent_unnotified", return_value={"scanned": 0, "eligible": 0, "notified": 0, "review_saved": 0, "errors": 0}), \
             patch.object(core.radar, "notify_lead") as notify:
            scan.return_value = {"status": "completed", "new_leads": [lead], "groups": 1, "messages": 1, "errors": 0}
            summary = await core.scan_once()
        self.assertEqual(summary["review_saved"], 1)
        self.assertEqual(summary["buyers"], 0)
        self.assertEqual(summary["notified"], 0)
        notify.assert_not_called()



class PrimeAtomicNotificationLedgerTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 18, tzinfo=timezone.utc)
        self.lead = {
            "lead_id": "source-a",
            "market": "north_cyprus", "intent_type": "BUYER",
            "lead_class": "HOT BUYER",
            "author": "@Chrkibris1",
            "group": "СЕВЕРНЫЙ КИПР | НЕДВИЖИМОСТЬ",
            "url": "https://t.me/cyprusprop/984807",
            "message": "Куплю 2+1 в Grand Sapphire напрямую от собственника.",
            "lead_reasons": ["explicit_purchase_intent", "owner_direct_buyer_preference"],
            "specificity": 2,
        }

    def test_new_and_recovered_share_same_public_message_key(self):
        same_message = dict(self.lead, lead_id="source-b",
                            url="https://t.me/CYPRUSPROP/984807?single",
                            author="Another source attribution")
        self.assertEqual(core._notification_key(self.lead),
                         core._notification_key(same_message))
        different_message = dict(self.lead, url="https://t.me/cyprusprop/984808")
        self.assertNotEqual(core._notification_key(self.lead),
                            core._notification_key(different_message))

    def test_claim_prevents_same_message_notification_twice(self):
        db = MagicMock()
        record = db.collection.return_value.document.return_value
        record.create.side_effect = [None, AlreadyExists("same message")]
        with patch.object(core, "_already_notified_public_link", return_value=False), \
             patch.object(core.radar, "notify_lead", return_value=True) as send, \
             patch.object(core, "_mark_notified"):
            first = core._deliver_once(db, self.lead, "NEW", self.now)
            second = core._deliver_once(db, dict(self.lead, lead_id="source-b"),
                                        "RECOVERED", self.now)
        self.assertEqual((first, second), ("delivered", "duplicate"))
        self.assertEqual(send.call_count, 1)

    def test_preexisting_notification_in_legacy_collection_is_suppressed(self):
        db = MagicMock()
        snap = MagicMock()
        snap.to_dict.return_value = {"v6_notified_at": self.now.isoformat()}
        db.collection.return_value.where.return_value.limit.return_value.stream.return_value = [snap]
        self.assertTrue(core._already_notified_public_link(db, self.lead))
        with patch.object(core.radar, "notify_lead") as send:
            self.assertEqual(core._deliver_once(db, self.lead, "RECOVERED", self.now),
                             "duplicate")
        send.assert_not_called()

    def test_uncertain_api_result_never_auto_retries(self):
        db = MagicMock()
        doc = db.collection.return_value.document.return_value
        with patch.object(core, "_already_notified_public_link", return_value=False), \
             patch.object(core.radar, "notify_lead", return_value=False) as send, \
             patch.object(core, "_mark_notified") as mark:
            result = core._deliver_once(db, self.lead, "RECOVERED", self.now)
        self.assertEqual(result, "uncertain")
        self.assertEqual(send.call_count, 1)
        mark.assert_not_called()
        self.assertEqual(doc.set.call_args.args[0]["status"], "uncertain")

    def test_actual_rukhshona_buyer_intent_is_preserved(self):
        lead = {
            "market": "north_cyprus", "intent_type": "BUYER",
            "lead_class": "HOT BUYER",
            "author": "Rukhshona Inomjonova",
            "message": "Здравствуйте! Куплю готовую квартиру 2+1 или 3+1 в рассрочку. Рассматриваю варианты в районах Yeniboğaziçi, Фамагуста или Лонг бич.",
            "lead_reasons": ["explicit_purchase_intent", "region_present"],
            "specificity": 2,
        }
        self.assertTrue(is_actionable_buyer(lead))


if __name__ == "__main__":
    unittest.main()
