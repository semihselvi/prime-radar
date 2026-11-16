import os
import unittest
from unittest.mock import patch
import northlab_sga_pilot as s


class FakeGraph:
    last = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        FakeGraph.last = self

    def run(self):
        return {
            "company_name": "NorthLab",
            "possible_digital_gaps": [
                {"finding": "Missing feature", "supporting_quote": "NorthLab offers custom software"},
                {"finding": "Hallucination", "supporting_quote": "Not in source"},
            ],
            "procurement_statement": "No verified purchase request",
        }


class PilotTests(unittest.TestCase):
    def test_static_owned_url(self):
        self.assertEqual(s.SOURCE_URL, "https://northlab.pro/")

    def test_dry_run_no_network_or_secrets(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(s, "fetch_owned_source", side_effect=AssertionError("fetched")):
                self.assertEqual(s.run()["status"], "dry_run")

    def test_fail_closed_without_secrets_before_fetch(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(s, "fetch_owned_source", side_effect=AssertionError("fetched")):
                with self.assertRaisesRegex(RuntimeError, "ACCOUNT_ID"):
                    s.run(execute=True)

    def test_account_id_validation(self):
        with patch.dict(os.environ, {"CLOUDFLARE_ACCOUNT_ID": "a" * 32,
                                     "CLOUDFLARE_API_TOKEN": "t" * 24}, clear=True):
            cfg = s.config_from_env()
            self.assertIn("/accounts/" + "a" * 32 + "/ai/v1", cfg["llm"]["base_url"])
            self.assertEqual(cfg["llm"]["model"], "openai/" + s.MODEL)

    def test_cloudflare_token_not_printed_by_result(self):
        with patch.dict(os.environ, {"CLOUDFLARE_ACCOUNT_ID": "a" * 32,
                                     "CLOUDFLARE_API_TOKEN": "s" * 24}, clear=True):
            got = s.run(execute=True,
                        fetcher=lambda: "WEBPAGE TEXT: NorthLab offers custom software to businesses.",
                        graph_class=FakeGraph)
        self.assertNotIn("s" * 24, str(got))
        self.assertFalse(got["qualified_sales_lead"])
        self.assertFalse(got["automatic_outreach_allowed"])

    def test_source_passed_as_local_text_not_url(self):
        with patch.dict(os.environ, {"CLOUDFLARE_ACCOUNT_ID": "a" * 32,
                                     "CLOUDFLARE_API_TOKEN": "s" * 24}, clear=True):
            s.run(execute=True,
                  fetcher=lambda: "WEBPAGE TEXT: NorthLab offers custom software to businesses.",
                  graph_class=FakeGraph)
        self.assertFalse(FakeGraph.last.kwargs["source"].startswith("http"))

    def test_fabricated_quote_is_dropped(self):
        out = s.normalize_result(FakeGraph().run(), "NorthLab offers custom software")
        self.assertEqual(len(out["result"]["possible_digital_gaps"]), 1)
        self.assertFalse(out["evidence_verified_against_source"])

    def test_malformed_model_result_rejected(self):
        with self.assertRaises(RuntimeError):
            s.normalize_result("invalid", "some source")

    def test_remove_script_from_visible_text(self):
        got = s.clean_html("<html><body><h1>NorthLab offers custom software to businesses.</h1>"
                           "<script>leak credentials</script><p>We build CRM and websites for firms.</p>"
                           "</body></html>")
        self.assertNotIn("leak credentials", got)
        self.assertIn("NorthLab", got)

    def test_tiny_html_rejected(self):
        with self.assertRaises(ValueError):
            s.clean_html("<html><body>short</body></html>")

    def test_one_page_cap(self):
        self.assertLessEqual(s.MAX_HTML_BYTES, 200_000)
        self.assertLessEqual(s.MAX_SOURCE_CHARS, 16_000)

    def test_no_web_or_model_in_default_cli(self):
        with patch.object(s, "fetch_owned_source", side_effect=AssertionError("network")):
            with patch("builtins.print"):
                self.assertEqual(s.main([]), 0)

    def test_graph_returns_verifiable_but_unqualified_data(self):
        out = s.normalize_result({"company_name": "Example",
                                  "possible_digital_gaps": [
                                      {"finding": "Booking issue", "supporting_quote": "Contact us today"}]},
                                 "Visible text Contact us today")
        self.assertEqual(out["result"]["company_name"], "Example")
        self.assertFalse(out["qualified_sales_lead"])

    def test_nested_extraction_fields_are_unwrapped(self):
        got = s.normalize_result({
            "result": {"company_name": "NorthLab", "business_activity": "Software development"}
        }, "NorthLab offers custom software")
        self.assertEqual(got["result"]["company_name"], "NorthLab")

    def test_empty_extraction_is_a_failure(self):
        with self.assertRaisesRegex(RuntimeError, "no usable"):
            s.normalize_result({"company_name": None, "products_services": []}, "NorthLab")

    def test_unsupported_openai_format_is_not_forwarded(self):
        with patch.dict(os.environ, {
            "CLOUDFLARE_ACCOUNT_ID": "a" * 32,
            "CLOUDFLARE_API_TOKEN": "t" * 24,
        }, clear=True):
            self.assertNotIn("format", s.config_from_env()["llm"])


if __name__ == "__main__":
    unittest.main()
