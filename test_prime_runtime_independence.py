"""Regression contract: Prime production must not import the V5 patch chain."""
from __future__ import annotations

import subprocess
import sys
import unittest

import prime_buyer_policy as policy
from prime_web_search import PaidBuyerSearch


class PrimeRuntimeIndependenceTests(unittest.TestCase):
    def test_isolated_import_does_not_load_any_legacy_v5_modules(self):
        code = (
            "import sys, nc_v6_broad_radar, northlab_lead_radar_core; "
            "legacy = sorted(k for k in sys.modules "
            "if k.startswith('main_v5') or k.startswith('nc_v5_')); "
            "assert not legacy, legacy"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code], capture_output=True,
            text=True, timeout=20,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr[-1800:])

    def test_goods_guards_match_previously_reviewed_examples(self):
        cases = [
            ("Куплю моющий робот пылесос для большой квартиры", True),
            ("Куплю телефон в Искеле", True),
            ("Куплю квартиру 2+1 в Искеле", False),
            ("Looking to buy a villa in Long Beach", False),
            ("Хочу купить дом в Лапта", False),
            ("Куплю 1+1 Royal Sun Elite", False),
        ]
        for message, blocked in cases:
            with self.subTest(message=message):
                self.assertIs(policy.is_nonproperty_goods_request(message), blocked)

    def test_extracted_guards_match_legacy_inside_disposable_subprocess(self):
        # V5 itself applies global monkey patches, so run comparison in an
        # isolated process. Never import legacy modules into production tests.
        code = """
import prime_buyer_policy as new
import nc_v5_batch_quality_guard as old
messages = [
    "Куплю моющий робот пылесос для большой квартиры",
    "Куплю телефон в Искеле",
    "Куплю квартиру 2+1 в Искеле",
    "Куплю 1+1 Royal Sun Elite",
    "Хочу купить дом в Лапта",
    "Куплю столик для квартиры",
    "Куплю смартфон в Фамагусте",
    "Куплю 2+1 в Long Beach с мебелью",
    "Looking to buy a villa in Long Beach",
    "Need a plumber to repair our apartment",
    "Looking for a lawyer for our villa purchase",
    "Продам квартиру в Искеле. Цена £120000",
    "Срочная продажа квартиры, цена 120000£",
    "Контакт менеджер PulseMarket",
    "Новое объявление: цена 100000£",
]
for msg in messages:
    assert new.is_nonproperty_goods_request(msg) == old.is_nonproperty_goods_request(msg), msg
    assert bool(new.TG_STRONG_SUPPLY_RE.search(msg)) == bool(old.radar.TG_STRONG_SUPPLY_RE.search(msg)), msg
    assert bool(new.TG_SERVICE_REQUEST_RE.search(msg)) == bool(old.radar.TG_SERVICE_REQUEST_RE.search(msg)), msg
for url in (
    "https://example.com/flats-for-rent/1",
    "https://expat.com/housing/2",
    "https://example.com/discussions/buy-flat",
):
    assert new.web_listing_url(url) == old.radar._web_listing_url(url), url
assert new.WEB_LISTING_RE.pattern == old.radar._WEB_LISTING_RE.pattern
"""
        proc = subprocess.run([sys.executable, "-c", code],
                              capture_output=True, text=True, timeout=20)
        self.assertEqual(proc.returncode, 0, proc.stderr[-1700:])

    def test_paid_search_provider_is_per_instance(self):
        a = PaidBuyerSearch()
        b = PaidBuyerSearch()
        a.serper_disabled = True
        self.assertFalse(b.serper_disabled)
        self.assertFalse(a.exa_disabled)

    def test_v6_web_buyer_path_preserves_multilingual_explicit_purchase(self):
        import nc_v6_broad_radar as v6
        examples = [
            "I want to buy an apartment in North Cyprus, budget £120000 near Long Beach.",
            "Я хочу купить квартиру 2+1 в Искеле, бюджет 120000£.",
            "Kuzey Kıbrıs'ta 2+1 daire satın almak istiyorum, bütçem £120000.",
        ]
        for text in examples:
            with self.subTest(text=text):
                record = {
                    "url": "https://example.org/forum/request",
                    "title": "Home purchase request",
                    "text": text,
                    "published": "2026-11-18",
                }
                result = v6.broad_web_classifier(record)
                self.assertIsNotNone(result, text)
                self.assertEqual(result["intent_type"], "BUYER")

    def test_v6_web_path_rejects_rental_listing(self):
        import nc_v6_broad_radar as v6
        listing = {
            "url": "https://example.org/flats-for-rent/123",
            "title": "For Rent in North Cyprus",
            "text": "Apartment 2+1 in Long Beach, monthly rental £700.",
        }
        self.assertIsNone(v6.broad_web_classifier(listing))

    def test_existing_rental_inventory_exclusions(self):
        self.assertTrue(policy.web_listing_url("https://example.com/flats-for-rent/123"))
        self.assertFalse(policy.web_listing_url("https://example.com/discussions/buy-apartment"))
        self.assertIsNotNone(policy.WEB_LISTING_RE.search(
            "Agency report. Contact the agent to view property."
        ))


if __name__ == "__main__":
    unittest.main()
