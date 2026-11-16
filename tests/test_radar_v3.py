import unittest
from datetime import datetime, timedelta, timezone
from northlab_v3.core import (
    Discovery, make_candidate, qualify, confirm_opportunity, canonical_url,
)
from northlab_v3.discover import parse_rss, fetch_rss, scan, SEARCHES
from northlab_v3.__main__ import review_candidates

NOW = datetime(2026, 11, 16, 18, tzinfo=timezone.utc)
TEXT = "İstanbul şirketimiz için CRM sistemini geliştirmek istiyoruz, teklif almak istiyoruz."
NC = "Gazimağusa firmamız için web sitesi yaptırmak istiyoruz; ajans arıyoruz."


def obs(text=TEXT, url="https://example.com/request/123"):
    return Discovery(url, "Yeni yazılım talebi", text, NOW.isoformat(), NOW.isoformat())


def candidate(text=TEXT):
    c, reason = make_candidate(obs(text))
    assert reason == "review_required", reason
    return c


def approved(c=None, age=1, quote="CRM sistemini geliştirmek istiyoruz"):
    c = c or candidate()
    return {
        "candidate_id": c["candidate_id"], "decision": "approve",
        "reviewer": "NorthLab sales", "reviewed_at": NOW.isoformat(),
        "source_published_at": (NOW - timedelta(days=age)).isoformat(),
        "source_url": c["source_url"], "buyer_company": "Example Ltd",
        "buyer_company_evidence_url": "https://example.com/about",
        "buyer_company_checked_directly": True, "country": "TR",
        "buyer_request_quote": quote,
        "request_is_external_contract": True, "agency_eligible": True,
        "source_publication_checked_directly": True,
        "contact_checked_directly": True,
        "contact_evidence_url": "https://example.com/contact",
        "contact": {"kind": "email", "value": "info@example.com"},
    }


class V3Contract(unittest.TestCase):
    def test_tr_review_only(self):
        c = candidate()
        self.assertEqual(c["market_hint_unverified"], "TR")
        self.assertEqual(c["status"], "REVIEW_REQUIRED")
        self.assertFalse(c["sales_outreach_allowed"])

    def test_north_cyprus_review_only(self):
        self.assertEqual(candidate(NC)["market_hint_unverified"], "KKTC")

    def test_japan_excluded(self):
        c, reason = make_candidate(obs("Tokyo şirketimiz için web sitesi yaptırmak istiyoruz"))
        self.assertIsNone(c)
        self.assertEqual(reason, "geography_unsubstantiated")

    def test_ambiguous_market_excluded(self):
        self.assertEqual(make_candidate(obs("İstanbul ve Girne için CRM yaptırmak istiyoruz"))[1], "geography_ambiguous")

    def test_provider_promo_rejected(self):
        self.assertIsNone(make_candidate(obs("İstanbul CRM yazılım hizmeti veriyoruz, ihtiyacınız var mı?"))[0])

    def test_employment_rejected(self):
        self.assertIsNone(make_candidate(obs("İstanbul şirketimiz için yazılımcı arıyoruz tam zamanlı maaş CV gönder"))[0])

    def test_tender_rejected(self):
        self.assertIsNone(make_candidate(obs("Girne CRM ihale teminat şartıyla ajans arıyoruz"))[0])

    def test_membership_r10_rejected(self):
        self.assertEqual(make_candidate(obs(url="https://www.r10.net/thread/1"))[1], "invalid_source")

    def test_ip_literal_prohibited(self):
        with self.assertRaises(ValueError):
            canonical_url("https://169.254.169.254/metadata")

    def test_non_https_prohibited(self):
        for url in ["http://example.com", "https://u:p@example.com/", "https://localhost/", "javascript:alert(1)"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                canonical_url(url)

    def test_review_required_before_any_sales_record(self):
        c = candidate()
        self.assertEqual(qualify(c, {}, now=NOW)[1], "missing_matching_human_review")

    def test_three_month_old_request_excluded(self):
        c = candidate()
        self.assertEqual(qualify(c, approved(c, age=90), now=NOW)[1], "stale_request_or_review")

    def test_approved_still_unconfirmed(self):
        c = candidate()
        lead, reason = qualify(c, approved(c), now=NOW)
        self.assertEqual(reason, "contactable_unconfirmed")
        self.assertEqual(lead["status"], "CONTACTABLE_UNCONFIRMED")
        self.assertFalse(lead["confirmed_currently_open"])
        self.assertFalse(lead["outreach_authorized_automatically"])
        self.assertFalse(lead["sale_won"])

    def test_false_quote_rejected(self):
        c = candidate()
        self.assertEqual(qualify(c, approved(c, quote="ERP 10000 euro ödeme"), now=NOW)[1],
                         "buyer_quote_not_in_source_excerpt")

    def test_company_not_verified_rejected(self):
        c = candidate()
        r = approved(c)
        r["buyer_company_checked_directly"] = False
        self.assertEqual(qualify(c, r, now=NOW)[1], "buyer_identity_not_verified")

    def test_published_date_not_verified_rejected(self):
        c = candidate()
        r = approved(c)
        r["source_publication_checked_directly"] = False
        self.assertEqual(qualify(c, r, now=NOW)[1], "external_contact_or_date_not_verified")

    def test_country_not_supported(self):
        c = candidate()
        r = approved(c)
        r["country"] = "JAPAN"
        self.assertEqual(qualify(c, r, now=NOW)[1], "market_unverified_or_mismatch")

    def test_closed_platform_contact_rejected(self):
        c = candidate()
        r = approved(c)
        r["contact"] = {"kind": "website_contact", "value": "https://r10.net/thread/1"}
        self.assertEqual(qualify(c, r, now=NOW)[1], "contact_invalid_or_membership_only")

    def test_future_publication_rejected(self):
        c = candidate()
        self.assertEqual(qualify(c, approved(c, age=-1), now=NOW)[1], "chronology_invalid")

    def test_social_dm_not_a_direct_contact(self):
        c = candidate()
        r = approved(c)
        r["contact"] = {"kind": "social_dm", "value": "LinkedIn"}
        self.assertEqual(qualify(c, r, now=NOW)[1], "contact_invalid_or_membership_only")

    def test_no_qualified_opportunity_before_buyer_reply(self):
        c = candidate()
        reachable, _ = qualify(c, approved(c), now=NOW)
        self.assertEqual(confirm_opportunity(reachable, {}, now=NOW)[1], "no_buyer_confirmation")

    def test_confirmed_buyer_reply_becomes_qualified(self):
        c = candidate()
        reachable, _ = qualify(c, approved(c), now=NOW)
        result, reason = confirm_opportunity(reachable, {
            "buyer_confirmed_open": True, "replied_at": NOW.isoformat(),
            "reviewed_by": "NorthLab", "reply_evidence_reference": "call-note:northlab-123",
        }, now=NOW)
        self.assertEqual(reason, "qualified_opportunity")
        self.assertTrue(result["confirmed_currently_open"])
        self.assertFalse(result["sale_won"])

    def test_confirmation_without_documented_reply_fails(self):
        c = candidate()
        reachable, _ = qualify(c, approved(c), now=NOW)
        self.assertEqual(confirm_opportunity(reachable, {
            "buyer_confirmed_open": True, "replied_at": NOW.isoformat(),
            "reviewed_by": "NorthLab", "reply_evidence_reference": "",
        }, now=NOW)[1], "buyer_reply_evidence_missing")

    def test_indexed_date_not_post_date(self):
        raw = b'<rss version="2.0"><channel><item><title>CRM</title><description>' + TEXT.encode() + b'</description><link>https://example.com/post</link><pubDate>Mon, 16 Nov 2026 18:00:00 GMT</pubDate></item></channel></rss>'
        row = parse_rss(raw, NOW.isoformat())[0]
        c, _ = make_candidate(row)
        self.assertIsNotNone(row.indexed_at)
        self.assertNotIn("source_published_at", c)

    def test_unapproved_provider_query_forbidden(self):
        with self.assertRaises(ValueError):
            fetch_rss("http://169.254.169.254")

    def test_discovery_never_auto_contacts(self):
        raw = b'<rss version="2.0"><channel><item><title>CRM</title><description>' + TEXT.encode() + b'</description><link>https://example.com/post</link></item></channel></rss>'
        report = scan(now=NOW, fetch=lambda query: raw)
        self.assertEqual(report["status"], "DISCOVERY_ONLY")
        self.assertEqual(report["qualified_lead_count"], 0)
        self.assertEqual(report["contacts_sent"], 0)
        self.assertEqual(report["review_queue_count"], 1)

    def test_search_failure_is_not_success(self):
        def fail(q):
            raise TimeoutError("Unavailable")
        report = scan(now=NOW, fetch=fail)
        self.assertEqual(report["status"], "SOURCE_FAILURE")
        self.assertEqual(len(report["provider_errors"]), len(SEARCHES))

    def test_manual_review_pipeline_separates_stages(self):
        c = candidate()
        result = review_candidates({"review_queue": [c]}, [approved(c)], [], now=NOW)
        self.assertEqual(result["contactable_unconfirmed_count"], 1)
        self.assertEqual(result["qualified_opportunity_count"], 0)
        self.assertEqual(result["outreach_messages_sent"], 0)

    def test_duplicate_manual_review_forbidden(self):
        c = candidate()
        with self.assertRaises(ValueError):
            review_candidates({"review_queue": [c]}, [approved(c), approved(c)], [], now=NOW)


if __name__ == "__main__":
    unittest.main()
