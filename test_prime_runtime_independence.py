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

    def test_paid_search_provider_is_per_instance(self):
        a = PaidBuyerSearch()
        b = PaidBuyerSearch()
        a.serper_disabled = True
        self.assertFalse(b.serper_disabled)
        self.assertFalse(a.exa_disabled)

    def test_existing_rental_inventory_exclusions(self):
        self.assertTrue(policy.web_listing_url("https://example.com/flats-for-rent/123"))
        self.assertFalse(policy.web_listing_url("https://example.com/discussions/buy-apartment"))
        self.assertIsNotNone(policy.WEB_LISTING_RE.search(
            "Agency report. Contact the agent to view property."
        ))


if __name__ == "__main__":
    unittest.main()
