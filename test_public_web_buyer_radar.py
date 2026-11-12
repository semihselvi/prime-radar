import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import public_web_buyer_radar as web


class PublicWebBuyerRadarTests(unittest.TestCase):
    def test_target_forum_discovery_only_allows_two_domains(self):
        sample = [
            {"url": "https://forum.donanimhaber.com/yatirim-amacli-konut-alinir-mi--160559823", "title": "Kıbrıs"},
            {"url": "https://unrelated.example.com/spam", "title": "Not allowed"},
        ]
        with patch.object(web.forum_engine, "discover_forum_threads", return_value={
            "threads": ["https://kibkomnorthcyprusforum.com/viewtopic.php?t=123"],
            "error": "", "engine": "phpbb",
        }), patch.object(web, "bing_rss", return_value=sample):
            rows, debug = web.discover_target_forum_rows()
        self.assertTrue(any(r["source"] == "Kibkom" for r in rows))
        self.assertTrue(any(r["source"] == "DonanımHaber" for r in rows))
        self.assertFalse(any("unrelated.example.com" in r["url"] for r in rows))
        self.assertTrue(all(r["source"] in {"Kibkom", "DonanımHaber"} for r in rows))

    def test_donanimhaber_must_explicitly_mention_north_cyprus(self):
        with patch.dict(os.environ, {"RADAR_SALES_ONLY": "1"}):
            signal, reason = web.classify_window(
                "İstanbul'da 2+1 daire satın almak istiyorum, bütçem 6 milyon TL.",
                implicit_north_cyprus=False,
            )
        self.assertIsNone(signal)
        self.assertEqual(reason, "no_north_context")

    def test_undated_forum_post_must_not_be_hot(self):
        freshness, age = web._freshness(None)
        self.assertEqual((freshness, age), ("unknown", None))

    def test_extracts_buyer_window_from_forum_text(self):
        text = (
            "Forum navigation random text. "
            "We are moving to Northern Cyprus and I am looking to buy a 3 bed villa in Kyrenia, "
            "budget £180,000. We would like a pool. "
            "More unrelated replies and footer."
        )
        windows = web.extract_candidate_windows(text)
        self.assertTrue(windows)
        self.assertIn("looking to buy", windows[0].lower())
        self.assertIn("Northern Cyprus", windows[0])

    def test_real_english_buyer_is_accepted(self):
        with patch.dict(os.environ, {"RADAR_SALES_ONLY": "1"}):
            signal, reason = web.classify_window(
                "I am looking to buy a 3 bed villa in Northern Cyprus near Kyrenia. "
                "My budget is £180,000."
            )
        self.assertIsNotNone(signal, reason)
        self.assertEqual(reason, "accepted")
        self.assertEqual(signal["intent_type"], "BUYER")

    def test_real_russian_buyer_is_accepted(self):
        with patch.dict(os.environ, {"RADAR_SALES_ONLY": "1"}):
            signal, reason = web.classify_window(
                "Хочу купить квартиру 2+1 в Фамагусте на Северном Кипре. Бюджет 150000£."
            )
        self.assertIsNotNone(signal, reason)
        self.assertEqual(signal["intent_type"], "BUYER")

    def test_kibkom_source_context_counts_as_north_cyprus(self):
        with patch.dict(os.environ, {"RADAR_SALES_ONLY": "1"}):
            signal, reason = web.classify_window(
                "I am looking to buy a 2+1 apartment. My budget is £150,000.",
                implicit_north_cyprus=True,
            )
        self.assertIsNotNone(signal, reason)
        self.assertEqual(reason, "accepted")
        self.assertEqual(signal["intent_type"], "BUYER")

    def test_seller_listing_is_not_buyer(self):
        with patch.dict(os.environ, {"RADAR_SALES_ONLY": "1"}):
            signal, reason = web.classify_window(
                "North Cyprus apartment for sale. Available units from £120,000. "
                "Contact our sales team today to buy a property."
            )
        self.assertIsNone(signal)
        self.assertIn(reason, {"supply_or_agent", "commercial_provider", "no_explicit_purchase_intent"})

    def test_non_north_cyprus_buyer_is_rejected(self):
        with patch.dict(os.environ, {"RADAR_SALES_ONLY": "1"}):
            signal, reason = web.classify_window(
                "I am looking to buy an apartment in Valencia, Spain, budget €200,000."
            )
        self.assertIsNone(signal)
        self.assertEqual(reason, "no_north_context")

    def test_absolute_expat_date_is_parsed(self):
        dt = web._parse_date("04 July 2025 05:40:40")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2025)
        self.assertEqual(dt.month, 7)
        self.assertEqual(dt.day, 4)

    def test_relative_forum_dates_are_parsed(self):
        four_weeks = web._parse_date("4 weeks ago")
        three_years = web._parse_date("3 years ago")
        self.assertIsNotNone(four_weeks)
        self.assertIsNotNone(three_years)
        self.assertLessEqual((datetime.now(timezone.utc) - four_weeks).days, 29)
        self.assertGreaterEqual((datetime.now(timezone.utc) - three_years).days, 1090)

    def test_visible_expat_timestamp_is_recovered_not_member_since(self):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(
            "<html><body>Member since 02 July 2025 Revlon80 New member "
            "04 July 2025 05:40:40 Hi all, seriously considering buying a villa.</body></html>",
            "html.parser",
        )
        dt = web._visible_forum_date(soup, "https://www.expat.com/en/forum/europe/cyprus/north-cyprus/1100730.html")
        self.assertIsNotNone(dt)
        self.assertEqual((dt.year, dt.month, dt.day), (2025, 7, 4))

    def test_visible_relative_last_year_is_stale(self):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(
            "<html><body>Revlon80 New member last year #1 "
            "We are seriously considering buying a villa.</body></html>",
            "html.parser",
        )
        dt = web._visible_forum_date(soup)
        self.assertIsNotNone(dt)
        self.assertEqual(web._freshness(dt)[0], "stale")

    def test_freshness_buckets(self):
        fresh = datetime.now(timezone.utc) - timedelta(days=3)
        warm = datetime.now(timezone.utc) - timedelta(days=20)
        stale = datetime.now(timezone.utc) - timedelta(days=90)

        self.assertEqual(web._freshness(fresh)[0], "0_7d")
        self.assertEqual(web._freshness(warm)[0], "8_45d")
        self.assertEqual(web._freshness(stale)[0], "stale")
        self.assertEqual(web._freshness(None), ("unknown", None))



    def test_direct_rss_parser_extracts_entry(self):
        xml = """<?xml version="1.0"?>
        <rss version="2.0"><channel>
          <item>
            <title>Looking to buy in North Cyprus</title>
            <link>https://britishexpats.com/forum/cyprus-117/example.html</link>
            <pubDate>Fri, 25 Sep 2026 10:00:00 GMT</pubDate>
            <description>I am looking to buy a villa in Kyrenia.</description>
          </item>
        </channel></rss>"""
        rows = web.discovery.parse_feed_entries(xml)
        self.assertEqual(len(rows), 1)
        self.assertIn("Looking to buy", rows[0]["title"])
        self.assertIn("britishexpats.com", rows[0]["url"])
        self.assertIn("Kyrenia", rows[0]["text"])

    def test_expat_listing_thread_link_extraction(self):
        html = """
        <html><body>
          <a href="/en/forum/europe/cyprus/north-cyprus/123456-looking-to-buy.html">buyer</a>
          <a href="/en/forum/europe/cyprus/north-cyprus/">forum root</a>
          <a href="/en/forum/europe/cyprus/999999-other.html">other</a>
        </body></html>
        """
        urls = web.discovery.extract_listing_thread_links(
            html,
            "https://www.expat.com/en/forum/europe/cyprus/north-cyprus/",
            include_pattern=r"/en/forum/europe/cyprus/north-cyprus/\d+[-/]",
        )
        self.assertEqual(
            urls,
            ["https://www.expat.com/en/forum/europe/cyprus/north-cyprus/123456-looking-to-buy.html"],
        )

class PulseMarketSourceRegressionTests(unittest.TestCase):
    """Marketplace summaries must never mix sales, rentals or unrelated URLs."""

    def test_only_individual_same_origin_buyer_listing_links(self):
        html = """
        <main>
          <article><a href="/listing/123-buy"><h3>Куплю квартиру 1+1 Four Seasons Life</h3></a></article>
          <article><a href="/listing/456-buy"><h3>Ищу квартиру 2+1 в Гирне</h3></a></article>
          <article><a href="/listing/789-rent"><h3>Ищу в аренду квартиру 2+1</h3></a></article>
          <article><a href="https://evil.example.com/tracker"><h3>Куплю квартиру 3+1</h3></a></article>
          <article><h3>Ищу квартиру в Royal Sun Residence</h3><a href="/listing/unrelated">not same headline</a></article>
          <article><a href="/blog/market"><h3>Куплю квартиру 1+1</h3></a></article>
          <article><a href="/listing/666-sale"><h3>Продам квартиру 2+1</h3></a></article>
        </main>
        """
        rows, stats = web.extract_pulsemarket_card_rows(html)
        self.assertEqual(len(rows), 2)
        self.assertEqual([r["url"] for r in rows], [
            "https://web.pulsemarket.eu/listing/123-buy",
            "https://web.pulsemarket.eu/listing/456-buy",
        ])
        self.assertGreaterEqual(stats["unlinked_buyer_cards"], 1)
        self.assertTrue(all(r["source"] == "PulseMarket" for r in rows))
        self.assertTrue(all(not r["rss_published"] for r in rows))
        self.assertTrue(all(not r["implicit_nc"] for r in rows))

    def test_homepage_and_outside_domains_never_become_buyer_urls(self):
        for link in (
            "/", "#buy", "javascript:void(0)", "/blog/advert",
            "https://outsider.example/listing/1", "http://web.pulsemarket.eu/listing/1",
        ):
            with self.subTest(link=link):
                self.assertEqual(
                    web.pulsemarket_detail_url(web.PULSEMARKET_HOME, link), ""
                )

    def test_site_search_and_homepage_discovery_deduplicate(self):
        from unittest.mock import MagicMock
        html = '<a href="/ads/real-123"><h3>Куплю квартиру 2+1 в Искеле</h3></a>'
        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.raise_for_status.return_value = None
        hits = [
            {"url": "https://web.pulsemarket.eu/ads/real-123"},
            {"url": "https://another.example.com/ads/real-123"},
            {"url": "https://web.pulsemarket.eu/"},
        ]
        with patch.object(web.requests, "get", return_value=mock_resp), patch.object(
            web, "bing_rss", return_value=hits
        ):
            rows, debug = web.discover_pulsemarket_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(debug["linked_buyer_cards"], 1)
        self.assertEqual(rows[0]["url"], "https://web.pulsemarket.eu/ads/real-123")

    def test_unlinked_aggregator_message_can_not_become_sales_alert(self):
        html = """
        <section><h3>Ищу для клиента квартиру 2+1 в Гирне</h3>
        <p>Покупка напрямую от собственников</p></section>
        """
        rows, stats = web.extract_pulsemarket_card_rows(html)
        self.assertEqual(rows, [])
        self.assertEqual(stats["unlinked_buyer_cards"], 1)


if __name__ == "__main__":
    unittest.main()
