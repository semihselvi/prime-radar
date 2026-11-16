import unittest

from northlab_procurement_signals import classify_official_procurement


class OfficialTenderSignalTests(unittest.TestCase):
    def test_official_local_software_tender_is_review_only(self):
        result = classify_official_procurement(
            "KKTC Sigorta Bilgi Merkezi Yazılım Geliştirme Sistem Entegrasyonu ve Bakım Hizmetleri İhalesi",
            "https://kksrsb.org/hakkimizda/duyurular/item/358-example.html",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["lead_class"], "RFP REVIEW")
        self.assertIn("INTEGRATION", result["project_types"])
        self.assertIn("supplier_eligibility_not_verified", result["reasons"])

    def test_official_un_web_app_rfp_is_review_only(self):
        result = classify_official_procurement(
            "REQUEST FOR PROPOSAL FOR WEB / APP DEVELOPMENT AND MAINTENANCE SERVICES",
            "https://www.ungm.org/Public/Notice/319702",
        )
        self.assertEqual(result["lead_class"], "RFP REVIEW")

    def test_fake_lookalike_domain_rejected(self):
        self.assertIsNone(classify_official_procurement(
            "Yazılım geliştirme ihalesi", "https://kksrsb.org.evil.test/notice"))

    def test_http_rejected(self):
        self.assertIsNone(classify_official_procurement(
            "Yazılım geliştirme ihalesi", "http://kksrsb.org/notice"))

    def test_no_procurement_phrase_rejected(self):
        self.assertIsNone(classify_official_procurement(
            "Yazılım hizmetlerimiz", "https://kksrsb.org/hakkimizda"))

    def test_no_software_rejected(self):
        self.assertIsNone(classify_official_procurement(
            "Bina tadilat ihalesi", "https://kksrsb.org/hakkimizda/ihale"))

    def test_personnel_recruitment_rejected(self):
        self.assertIsNone(classify_official_procurement(
            "Teknik personel sınavı için yazılım ihalesi",
            "https://kksrsb.org/hakkimizda/ihale"))


if __name__ == "__main__":
    unittest.main()
