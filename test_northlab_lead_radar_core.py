import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import northlab_lead_radar_core as core


class NorthlabLeadRadarCoreTests(unittest.TestCase):
    def test_accepts_explicit_hot_buyer(self):
        self.assertTrue(core.is_actionable_buyer({
            "market": "north_cyprus",
            "intent_type": "BUYER",
            "lead_class": "HOT BUYER",
            "message": "Куплю квартиру 3+1 в Querencia.",
            "lead_reasons": ["explicit_purchase_intent"],
            "specificity": 2,
        }))

    def test_accepts_specific_owner_direct_search(self):
        self.assertTrue(core.is_actionable_buyer({
            "market": "north_cyprus",
            "intent_type": "BUYER",
            "lead_class": "WARM BUYER",
            "message": "Ищу кто продает от собственника 2+1 в 4 очереди Цезаря",
            "lead_reasons": ["implicit_property_demand", "owner_direct_buyer_preference"],
            "specificity": 3,
        }))

    def test_rejects_implicit_property_demand(self):
        self.assertFalse(core.is_actionable_buyer({
            "market": "north_cyprus",
            "intent_type": "BUYER",
            "lead_class": "WARM BUYER",
            "message": "Ищу квартиру 2+1 на Северном Кипре",
            "lead_reasons": ["implicit_property_demand"],
            "specificity": 1,
        }))

    def test_rejects_property_research_signal(self):
        self.assertFalse(core.is_actionable_buyer({
            "market": "north_cyprus",
            "intent_type": "BUYER",
            "lead_class": "WARM BUYER",
            "message": "Какие квартиры лучше смотреть на Северном Кипре?",
            "lead_reasons": ["property_research_signal"],
            "specificity": 1,
        }))

    def test_rejects_tenant(self):
        self.assertFalse(core.is_actionable_buyer({
            "market": "north_cyprus",
            "intent_type": "TENANT",
            "lead_class": "HOT TENANT",
            "message": "Сниму 1+1 в Искеле на шесть месяцев.",
        }))

    def test_rejects_relocation_and_investor_chatter(self):
        self.assertFalse(core.is_actionable_buyer({
            "market": "north_cyprus",
            "intent_type": "RELOCATION",
            "lead_class": "RELOCATION",
            "message": "Thinking about moving to North Cyprus.",
        }))
        self.assertFalse(core.is_actionable_buyer({
            "market": "north_cyprus",
            "intent_type": "INVESTOR",
            "lead_class": "INVESTOR",
            "message": "What are the yields in North Cyprus?",
        }))

    def test_rejects_car_purchase_even_if_upstream_labels_buyer(self):
        self.assertFalse(core.is_actionable_buyer({
            "market": "north_cyprus",
            "intent_type": "BUYER",
            "lead_class": "HOT BUYER",
            "author": "@anna_smrnva",
            "message": "Куплю авто ~5000£ либо с первым взносом в рассрочку",
            "lead_reasons": ["explicit_purchase_intent"],
            "specificity": 2,
        }))

    def test_rejects_buyer_label_if_message_is_rental(self):
        self.assertFalse(core.is_actionable_buyer({
            "market": "north_cyprus",
            "intent_type": "BUYER",
            "lead_class": "HOT BUYER",
            "message": "Looking to rent a 1+1 in Iskele for six months.",
            "lead_reasons": ["explicit_purchase_intent"],
            "specificity": 2,
        }))


class PrimeBuyerNotificationRecoveryTests(unittest.TestCase):
    def test_project_only_property_name_passes_final_gate(self):
        self.assertTrue(core.is_actionable_buyer({
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


class PrimeBuyerScanFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_unauthorized_telegram_scan_fails_workflow(self):
        with patch.object(core.radar.core, "db", return_value=MagicMock()), patch.object(
            core.radar, "broad_telegram_scan", new_callable=AsyncMock
        ) as scan:
            scan.return_value = {"status": "skipped_unauthorized", "new_leads": []}
            with self.assertRaisesRegex(RuntimeError, "skipped_unauthorized"):
                await core.scan_once()


if __name__ == "__main__":
    unittest.main()
