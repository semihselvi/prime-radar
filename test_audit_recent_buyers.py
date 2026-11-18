import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

import audit_recent_buyers as audit


class BuyerAuditPrivacyTests(unittest.TestCase):
    def test_audit_reports_counts_without_personal_messages_or_handles(self):
        row = MagicMock()
        row.to_dict.return_value = {
            "author": "@private_buyer_handle",
            "message": "PRIVATE CUSTOMER MESSAGE CONTAINS PERSONAL DETAILS",
            "url": "https://t.me/example/123",
            "lead_class": "HOT BUYER",
            "language": "RU",
            "v6_notified_at": "2026-11-18T07:10:00+00:00",
        }
        old_row = MagicMock()
        old_row.to_dict.return_value = {
            "author": "@older_customer",
            "message": "NOT FOR CURRENT REPORT",
            "v6_notified_at": "2026-09-18T07:10:00+00:00",
        }
        database = MagicMock()
        database.collection.return_value.stream.return_value = [row, old_row]
        output = io.StringIO()
        with patch.object(audit.core, "db", return_value=database):
            with redirect_stdout(output):
                audit.main()

        printed = output.getvalue()
        self.assertNotIn("PRIVATE CUSTOMER", printed)
        self.assertNotIn("@private_buyer_handle", printed)
        self.assertNotIn("https://t.me/example", printed)
        self.assertTrue(printed.startswith("RECENT_BUYER_AUDIT "))
        summary = json.loads(printed.split("RECENT_BUYER_AUDIT ", 1)[1])
        self.assertEqual(summary["count"], 1)
        self.assertEqual(summary["class_counts"]["HOT BUYER"], 1)
        self.assertTrue(summary["details_redacted"])


if __name__ == "__main__":
    unittest.main()
