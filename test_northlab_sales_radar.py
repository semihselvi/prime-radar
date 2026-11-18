import os
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import northlab_sales_radar as radar
import northlab_sales_source_hub as source_hub


class NorthlabSalesRadarTests(unittest.TestCase):
    def assertLead(self, text, expected_class):
        lead, reason = radar.classify(text)
        self.assertIsNotNone(lead, (text, reason))
        self.assertEqual(lead["lead_class"], expected_class)
        return lead

    def assertReject(self, text, expected_reason):
        lead, reason = radar.classify(text)
        self.assertIsNone(lead)
        self.assertEqual(reason, expected_reason)

    def test_hot_website_project(self):
        lead = self.assertLead(
            "We need someone to redesign our restaurant website this week. Budget is €1500.",
            "HOT PROJECT",
        )
        self.assertIn("WEBSITE", lead["project_types"])

    def test_warm_website_project(self):
        self.assertLead(
            "Looking for someone who can build a website for a small business.",
            "WARM PROJECT",
        )

    def test_hot_crm_project(self):
        lead = self.assertLead(
            "Firmamız için müşteri takip CRM sistemi lazım, teklif almak istiyoruz.",
            "HOT PROJECT",
        )
        self.assertIn("CRM", lead["project_types"])

    def test_booking_project_ru(self):
        lead = self.assertLead(
            "Нужна система онлайн-бронирования для нашей компании.",
            "HOT PROJECT",
        )
        self.assertIn("BOOKING", lead["project_types"])

    def test_custom_software_project(self):
        lead = self.assertLead(
            "Looking for a developer for a custom software project for our logistics business. Budget €5000.",
            "HOT PROJECT",
        )
        self.assertIn("SOFTWARE", lead["project_types"])

    def test_api_integration_project(self):
        lead = self.assertLead(
            "We need an agency for an API integration project for our CRM.",
            "HOT PROJECT",
        )
        self.assertIn("INTEGRATION", lead["project_types"])

    def test_mobile_app_project(self):
        lead = self.assertLead(
            "Looking for a developer for a mobile app project for our business.",
            "HOT PROJECT",
        )
        self.assertIn("MOBILE_APP", lead["project_types"])

    def test_generic_developer_request_with_project_context(self):
        lead = self.assertLead(
            "Seeking a developer for a web app project. Need someone who can start this week.",
            "HOT PROJECT",
        )
        self.assertIn("SOFTWARE", lead["project_types"])

    def test_partner(self):
        self.assertLead(
            "Looking for a white-label development partner for overflow website projects.",
            "PARTNER",
        )

    def test_problem_signal(self):
        self.assertLead(
            "Our company website is outdated and we need a website redesign.",
            "HOT PROJECT",
        )

    def test_marketplace_bot_ad_rejected(self):
        self.assertReject(
            "🆕 НОВОЕ ОБЪЯВЛЕНИЕ НА PulseMarket! Цена: 1 ₺ 🌐 Смотреть на сайте #спрос",
            "marketplace_ad",
        )

    def test_government_portal_login_problem_rejected(self):
        self.assertReject(
            "Не могу зайти в личный кабинет на сайте permissions.gov/staypermit - пользователь не найден. Куда обращаться?",
            "portal_account_support",
        )

    def test_document_advice_in_personal_account_rejected(self):
        self.assertReject(
            "Если в списке документов в личном кабинете есть пункт с банковской выпиской, то нужна.",
            "document_portal_context",
        )

    def test_tourism_portal_copy_rejected(self):
        self.assertReject(
            "WELCOME TO THE CYPRUS TOURISM PORTAL. Everything you need to plan your perfect trip is here on the Deputy Ministry of Tourism website.",
            "weak_project_signal",
        )

    def test_job_seeker_rejected(self):
        self.assertReject(
            "I am a web developer looking for a job. Here is my CV.",
            "job_seeker",
        )

    def test_full_time_vacancy_rejected(self):
        self.assertReject(
            "Vacancy: full-time web developer, salary €2500.",
            "employment_vacancy",
        )

    def test_service_provider_rejected(self):
        self.assertReject(
            "We build websites and CRM software for businesses. Our services include web design.",
            "service_provider",
        )

    def test_course_rejected(self):
        self.assertReject(
            "Looking for a web development course and tutorial.",
            "education",
        )

    def test_news_post_with_website_phrase_is_rejected(self):
        text = ("Глава Kıb-Tek заявил, что тяжело пострадавший при взрыве трансформатора "
                "рабочий пошёл туда один. Оппозиция в парламенте ТРСК это опровергла: "
                "рядом были шесть человек, нужно расследование. Подробнее на нашем сайте. "
                "Прислать новость")
        signal, reason = radar.classify(text)
        self.assertIsNone(signal)
        self.assertEqual(reason, "news_content")

    def test_provider_pricing_post_is_rejected(self):
        text = ("Need advice on setting the price on my first big project. I just landed my first "
                "big commission. My friend wants me to create an ecommerce website. "
                "What should I be charging him for this project?")
        signal, reason = radar.classify(text)
        self.assertIsNone(signal)
        self.assertEqual(reason, "provider_pricing_or_existing_client")

    def test_facebook_web_developer_group_description_is_not_project(self):
        lead, reason = radar.classify(
            "Do you need a Website Designer or Web Developer? This group is created to holds it's integrity "
            "for the best talents worldwide. Post your Talents or Needs."
        )
        self.assertIsNone(lead)
        self.assertEqual(reason, "community_directory")

    def test_reddit_advice_only_not_hiring_is_not_project(self):
        lead, reason = radar.classify(
            "Looking for information on how to find a web developer for a film society booking site. "
            "For the record, I am not looking to hire someone from here. "
            "I just don't know what to look for when finding information about web developers. "
            "Any tips or guidance would be greatly appreciated. "
            "What is the average cost of creating a website like this?"
        )
        self.assertIsNone(lead)
        self.assertEqual(reason, "advice_only_not_hiring")

    def test_x_join_our_team_web_developer_is_employment(self):
        lead, reason = radar.classify(
            "We are looking for a Professional Web Developer to join our team. Strong experience in HTML, CSS, JavaScript. "
            "Send your portfolio hassankmm274@gmail.com #WebDeveloper #Hiring"
        )
        self.assertIsNone(lead)
        self.assertEqual(reason, "employment_vacancy")

    def test_framer_portfolio_build_request_is_project(self):
        lead, reason = radar.classify(
            "Looking for a talented web developer who knows their way around Framer to build my new portfolio website. "
            "Drop your best work in the replies or shoot me a DM."
        )
        self.assertIsNotNone(lead, reason)
        self.assertIn(lead["lead_class"], {"WARM PROJECT", "HOT PROJECT"})
        self.assertIn("WEBSITE", lead["project_types"])

    def test_guru_marketplace_page_is_not_project(self):
        lead, reason = radar.classify(
            "If you are looking for a web developer for your next project, you can find and hire freelance web developers on Guru."
        )
        self.assertIsNone(lead)
        self.assertEqual(reason, "marketplace_directory")

    def test_visa_site_information_is_not_web_project(self):
        lead, reason = radar.classify(
            "Для россиян ничего не изменилось, кроме того, что продлевать визу при необходимости нужно будет не в полиции, а оформлять на сайте."
        )
        self.assertIsNone(lead)
        self.assertEqual(reason, "reference_site_mention")

    def test_facebook_service_provider_promo_is_rejected(self):
        lead, reason = radar.classify(
            "I'm a Web Developer with 3+ years of experience creating modern websites. Here's what I can help you with: WordPress, Full-Stack, E-commerce and Admin Panels."
        )
        self.assertIsNone(lead)
        self.assertEqual(reason, "service_provider_promo")

    def test_facebook_group_connector_description_is_rejected(self):
        lead, reason = radar.classify(
            "Looking to hire a website designer or developer for your business? This group connects business owners, entrepreneurs, startups, and online sellers with professional website design and development support."
        )
        self.assertIsNone(lead)
        self.assertEqual(reason, "community_directory")

    def test_individual_only_framer_contract_is_not_northlab_lead(self):
        lead, reason = radar.classify(
            "The team is looking for an intermediate to advanced Framer developer on a per-project contract basis. We are looking for an individual developer, not an agency or a white-label team."
        )
        self.assertIsNone(lead)
        self.assertEqual(reason, "individual_only_contract")

    def test_reddit_developer_showcase_is_not_project(self):
        lead, reason = radar.classify(
            "Three years ago I posted this and that website is still being actively developed. "
            "I haven't used any AI-generated code or external libraries. "
            "Anyway this is just me saying that I'm still here."
        )
        self.assertIsNone(lead)
        self.assertEqual(reason, "developer_showcase")

    def test_business_website_article_is_not_project(self):
        lead, reason = radar.classify(
            "Do I need a website for my business, really, in 2026? This guide gives an honest answer, including the cases where you can manage without one."
        )
        self.assertIsNone(lead)
        self.assertEqual(reason, "content_article")

    def test_instagram_web_service_promo_is_not_project(self):
        lead, reason = radar.classify(
            "Need a website but can't face the faff? I build yours first, so you see it before you pay. I'll handle all the techy bits. Just DM me."
        )
        self.assertIsNone(lead)
        self.assertEqual(reason, "service_provider_promo")

    def test_web_n_works_service_promo_is_not_project(self):
        lead, reason = radar.classify(
            "Welcome to Web N Works. We turn your ideas into professional designs. What We Offer: Modern WordPress Website Design, Graphic Design and CV Design."
        )
        self.assertIsNone(lead)
        self.assertEqual(reason, "service_provider_promo")

    def test_showoff_tool_post_is_not_project(self):
        lead, reason = radar.classify(
            "Showoff Saturday: I built a tool that finds local businesses with no real website. I built it, so take this as a showoff post."
        )
        self.assertIsNone(lead)
        self.assertEqual(reason, "developer_showcase")

    def test_link_in_bio_web_service_promo_is_not_project(self):
        lead, reason = radar.classify(
            "Need a website for your business? Check the link in my bio and let's build something great!"
        )
        self.assertIsNone(lead)
        self.assertEqual(reason, "service_provider_promo")


class NorthlabDeliveryRegressionTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 18, tzinfo=timezone.utc)
        self.lead = {
            "lead_id": "known-test-lead",
            "lead_class": "HOT PROJECT",
            "platform": "Web",
            "text": "We need a CRM integration for our business.",
            "url": "https://example.org/request",
        }

    def test_telegram_requires_positive_api_acknowledgement(self):
        response = MagicMock()
        response.json.return_value = {"ok": True}
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test-only", "TELEGRAM_CHAT_ID": "test-only"}), \
             patch.object(radar.core.requests, "post", return_value=response):
            self.assertTrue(radar.core.telegram("hello"))
            response.json.return_value = {"ok": False}
            self.assertFalse(radar.core.telegram("hello"))

    def test_telegram_network_error_is_not_a_delivery(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test-only", "TELEGRAM_CHAT_ID": "test-only"}), \
             patch.object(radar.core.requests, "post", side_effect=TimeoutError("network failed")):
            self.assertFalse(radar.core.telegram("hello"))

    def test_failed_delivery_stays_eligible_and_is_marked_for_retry(self):
        db = MagicMock()
        debug = {"errors": []}
        with patch.object(radar, "_notify", return_value=False):
            delivered = radar.deliver_new_leads(db, [self.lead], self.now, debug)
        self.assertEqual(delivered, 0)
        self.assertEqual(debug["delivery_failures"], 1)
        written = db.collection.return_value.document.return_value.set.call_args.args[0]
        self.assertEqual(written["delivery_status"], "retry_pending")
        self.assertNotIn("notified_at", written)

    def test_successful_delivery_marks_only_confirmed_lead(self):
        db = MagicMock()
        debug = {"errors": []}
        with patch.object(radar, "_notify", return_value=True):
            delivered = radar.deliver_new_leads(db, [self.lead], self.now, debug)
        self.assertEqual(delivered, 1)
        written = db.collection.return_value.document.return_value.set.call_args.args[0]
        self.assertEqual(written["delivery_status"], "delivered")
        self.assertEqual(written["notified_at"], self.now.isoformat())
        self.assertEqual(debug["delivery_failures"], 0)

    def test_unnotified_record_can_be_retried_in_next_run(self):
        db = MagicMock()
        snap = db.collection.return_value.document.return_value.get.return_value
        snap.exists = True
        snap.to_dict.return_value = {"notified_at": None, "first_seen_at": self.now.isoformat()}
        self.assertTrue(radar._save_new(db, dict(self.lead), self.now))


class NorthlabSourceHealthRegressionTests(unittest.TestCase):
    def test_failed_requests_are_not_reported_as_healthy_zero_results(self):
        response = MagicMock()
        response.status_code = 429
        with patch.object(source_hub, "DISCOVERY_QUERIES", []), \
             patch.object(source_hub, "REDDIT_FEEDS", [("test", "https://www.reddit.com/r/test/new/.rss")]), \
             patch.object(source_hub, "BLUESKY_QUERIES", ["need website"]), \
             patch.object(source_hub.SESSION, "get", return_value=response):
            rows, meta = source_hub.collect_all()
        self.assertEqual(rows, [])
        self.assertEqual(meta["source_health"]["reddit"]["status"], "unavailable")
        self.assertEqual(meta["source_health"]["reddit"]["failures"]["http_429"], 1)
        self.assertEqual(meta["source_health"]["bluesky"]["status"], "unavailable")
        self.assertEqual(meta["source_health"]["youtube"]["status"], "no_targets")
        self.assertEqual(meta["source_health"]["forums"]["status"], "no_targets")

    def test_bing_429_is_reported_as_unavailable(self):
        response = MagicMock()
        response.status_code = 429
        health = {}
        with patch.object(radar.requests, "get", return_value=response):
            self.assertEqual(radar._bing_rss("crm agency", health=health), [])
        report = source_hub.summarize_source_health(health)
        self.assertEqual(report["status"], "unavailable")
        self.assertEqual(report["failures"]["http_429"], 1)

    def test_partial_source_failure_is_distinct_from_success(self):
        health = {}
        source_hub.record_source_attempt(health, True)
        source_hub.record_source_attempt(health, False, "http_403")
        report = source_hub.summarize_source_health(health)
        self.assertEqual(report["status"], "degraded")
        self.assertEqual(report["succeeded"], 1)
        self.assertEqual(report["failed"], 1)



if __name__ == "__main__":
    unittest.main()
