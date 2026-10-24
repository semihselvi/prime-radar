import unittest

import northlab_sales_radar as radar


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


if __name__ == "__main__":
    unittest.main()
