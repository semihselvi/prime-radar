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


    # Regression cases from the Nov 12 Telegram alerts: 12 false positives
    # and one genuine buyer-intent post to preserve.
    def test_regression_reddit_www_dns_support_not_sales(self):
        self.assertReject(
            "Help with website redirection. Hello, I'm looking for some help with issues I'm having "
            "with my website. My website was originally hosted through Wix. The www prefix no longer "
            "works; I get a privacy error and tried changing DNS settings.",
            "unpaid_technical_support",
        )

    def test_regression_law_firm_buyer_stays_actionable(self):
        lead, reason = radar.classify(
            "I'm looking for a full stack web developer for a newly established law firm, "
            "if you or anyone you know can develop a website please reply here with a portfolio, thanks!"
        )
        self.assertIsNotNone(lead, reason)
        self.assertIn(lead["lead_class"], {"HOT PROJECT", "WARM PROJECT"})

    def test_regression_marketing_article_11_reasons(self):
        self.assertReject(
            "11 Reasons Your Business May Need a Website - Grigora Blog. "
            "Start with a real customer task rather than assuming every business needs a large online store.",
            "editorial_or_guide",
        )

    def test_regression_marketing_article_duplicate(self):
        self.assertReject(
            "11 Reasons Your Business May Need a Website. Explore 11 practical benefits of a business website.",
            "editorial_or_guide",
        )

    def test_regression_company_ranking_not_buyer(self):
        self.assertReject(
            "Top Web Development Companies in 2026 - Techreviewer.co. "
            "When looking for a web developer, reading customer reviews and case studies helps select the right website development company.",
            "editorial_or_guide",
        )

    def test_regression_upwork_marketplace_category_not_buyer(self):
        self.assertTrue(radar.non_buyer_web_source(
            "https://www.upwork.com/freelance-jobs/website-development/"
        ))

    def test_regression_telegram_russian_residence_permit(self):
        self.assertReject(
            "Геч ничего хранить не будет, карту вернули значит внж не нужен, аннулируют. "
            "После одобрение у вас код для отслеживания приходит, открываете сайт и следите где ваш пластик",
            "immigration_portal_help",
        )

    def test_regression_telegram_russian_tourist_visa(self):
        self.assertReject(
            "Здравствуйте, насколько я понял, теперь турвизу продлять нужно через интернет, "
            "вот изучаю тему. Нашел тут куар код, перекидывает на сайт, а что там дальше выбирать?",
            "immigration_portal_help",
        )

    def test_regression_facebook_50_dollar_websites_seller(self):
        self.assertReject(
            "Professional Web Developer | Websites Starting at Just $50. Need a website for your "
            "business, brand, or idea? I build any type of website, fast, clean, and fully responsive.",
            "service_provider_promo",
        )

    def test_regression_facebook_group_landing_is_not_post(self):
        self.assertTrue(radar.non_buyer_web_source(
            "https://www.facebook.com/groups/2327375611076477/"
        ))

    def test_regression_small_business_website_guide(self):
        self.assertReject(
            "Do I Need a Website for My Small Business? 5 Answers. For most, yes. "
            "See when social media or a Google profile is enough.",
            "editorial_or_guide",
        )

    def test_regression_web_design_sales_pitch_on_x(self):
        self.assertReject(
            "Need a website that does more than display a few pages? "
            "From online shops to custom functionality, I can help build something around how your business actually works!",
            "service_provider_promo",
        )

    def test_regression_facebook_business_sales_pitch(self):
        self.assertReject(
            "If you own a business, you need a website. It helps customers find you faster. "
            "Need one? Tell me about your business let's get you a website.",
            "service_provider_promo",
        )

    def test_regression_instagram_agency_sales_pitch(self):
        self.assertReject(
            "Need a website for your business? I'm currently taking on new projects. "
            "Drop a comment or send me a DM. Let's talk.",
            "service_provider_promo",
        )


if __name__ == "__main__":
    unittest.main()
