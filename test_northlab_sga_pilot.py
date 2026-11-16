import unittest
from unittest.mock import patch
from northlab_sga_pilot import validate_url, normalize_result, run, main


class ScrapeGraphPilotTests(unittest.TestCase):
    def test_exact_allowlist_accepts_public_https(self):
        url = 'https://www.northlab.pro/contact/'
        self.assertEqual(validate_url(url, 'www.northlab.pro'), url)

    def test_rejects_unapproved_subdomain(self):
        with self.assertRaises(ValueError):
            validate_url('https://evil.northlab.pro/', 'northlab.pro')

    def test_rejects_local_and_ip_hosts(self):
        for host in ('localhost', '127.0.0.1', '169.254.169.254', '[::1]'):
            with self.subTest(host=host), self.assertRaises(ValueError):
                validate_url('https://' + host + '/', host)

    def test_rejects_non_https_and_credentials(self):
        for url in ('http://northlab.pro/', 'https://me:pass@northlab.pro/',
                    'https://northlab.pro:443/', 'https://northlab.pro/?q=a'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_url(url, 'northlab.pro')

    def test_dry_run_never_calls_model_or_imports_library(self):
        with patch('northlab_sga_pilot.ollama_model_ready', side_effect=AssertionError('called')):
            got = run('https://northlab.pro/', 'northlab.pro', 'llama3.2')
        self.assertEqual(got['stage'], 'dry_run')
        self.assertFalse(got['qualified_sales_lead'])

    def test_fail_closed_when_local_model_is_missing(self):
        with patch('northlab_sga_pilot.ollama_model_ready', return_value=False):
            with self.assertRaisesRegex(RuntimeError, 'not installed'):
                run('https://northlab.pro/', 'northlab.pro', 'llama3.2', True)

    def test_does_not_upgrade_model_claim_to_real_lead(self):
        got = normalize_result({'company_name': 'Example',
                                'possible_digital_gaps': [{'finding': 'No booking system', 'supporting_quote': 'Call us'}],
                                'procurement_statement': 'We need a CRM'}, 'https://northlab.pro/')
        self.assertFalse(got['qualified_sales_lead'])
        self.assertFalse(got['evidence_verified_against_source'])
        self.assertTrue(got['review_required'])

    def test_requires_supporting_quote_for_gap(self):
        got = normalize_result({'possible_digital_gaps': [
            {'finding': 'No shop', 'supporting_quote': ''}, {'finding': 'No CRM'},
            {'finding': 'Contact only', 'supporting_quote': 'Call us'}]}, 'https://northlab.pro/')
        self.assertEqual(len(got['result']['possible_digital_gaps']), 1)

    def test_bad_output_fails_closed(self):
        with self.assertRaises(ValueError):
            normalize_result(['text'], 'https://northlab.pro/')

    def test_invalid_model_rejected(self):
        with self.assertRaises(ValueError):
            run('https://northlab.pro/', 'northlab.pro', 'openai/gpt-4o', True)

    def test_manual_cli_dry_run(self):
        with patch('builtins.print'):
            self.assertEqual(main(['--url', 'https://northlab.pro/', '--allow-host', 'northlab.pro']), 0)


if __name__ == '__main__':
    unittest.main()
