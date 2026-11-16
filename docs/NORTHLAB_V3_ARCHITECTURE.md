# NORTHLAB SATIŞ RADARI — V3 KÖK MİMARİ (yama değil)

**Durum: Bağımsız shadow sürüm; üretim geçişi yapılmadı.**
V2'nin üstüne regex, ScrapeGraphAI veya yeni yama eklenmedi. Yalnız `northlab_v3/` paketi ve `.github/workflows/northlab-v3-shadow.yml` oluşturuldu. Prime Kıbrıs, eski NorthLab ve başka radarların iş akışları korunuyor.

## Kanıtlanan mevcut mimari sorunları

16 Kasım 2026 son kayıt: 93 Telegram grubu, 1.259 mesaj, 227 web sonucu, 25 source hub sonucu, **0 lead ve 0 bildirim**. V2 küresel/İngilizce aramalar, Reddit, Bluesky, Telegram genel grupları ve regex puanlama kullanıyor. Kullanıcının hedefi **KKTC ve Türkiye** iken kaynak coğrafyası zorunlu değil. Gerçek alıcı, ilan tarihi, doğrudan iletişim ve satın alma yetkisi zorunlu doğrulanmıyor. Eski birim testlerinin geçmesi ticari başarı kanıtı değil.

## Yeni tasarımın ayrı katmanları

1. **DISCOVERY:** KKTC/TR odaklı 12 sabit halka açık sorgu. Yalnız `https://www.bing.com/search` üzerinden RSS, sınırlı yanıt boyutu, redirect yok. RSS bağlantıları **hiçbir zaman ziyaret edilmiyor**; böylece keyfî URL taraması/SSRF yürütülmüyor. Başka ülke, iş ilanı, servis sağlayıcı promosyonu veya R10 gibi kapalı pazar yeri reddedilir. Çıktı `REVIEW_REQUIRED`, satış fırsatı değil. RSS `pubDate` kaydı, orijinal ilan tarihi yerine `indexed_at_not_publication_date` olarak saklanır.
2. **MANUAL EVIDENCE:** İnsan tarafından orijinal ilan tarihi (en çok 14 gün), şirket kimliği ve ülke, aynı sayfada görünen birebir alıcı talebi, ajans olarak teklif verme uygunluğu ve üyelik engeli olmayan doğrudan şirket iletişimi kontrol edilir. Kanıt URL'leri zorunlu. Çıktı `CONTACTABLE_UNCONFIRMED` — işin hâlâ açık olduğunu göstermez.
3. **BUYER CONFIRMATION:** Alıcı e-posta, WhatsApp veya görüşmede işin hâlâ açık olduğunu doğrulamazsa gerçek fırsat üretilmez. Kanıt referansı ve doğrulayan kişi zorunlu. Çıktı `QUALIFIED_OPPORTUNITY` — satış/ödeme değil.
4. **COMMERCIAL (üretim geçişinde):** İlk temas, görüşme, teklif, sözleşme ve tahsilat ayrıca izlenir. Henüz CRM entegrasyonu, otomatik gönderim veya canlı zamanlayıcı yok.

Review içindeki `true` bayrakları dış kanıtın yerine geçmez; incelemeyi yapan kişi kaynakları gerçekten açmalıdır. Bu bilinçli bir insan denetimi aşamasıdır.

## Çalıştırma

Python 3.12, üçüncü taraf kütüphane, API key veya ücretli hizmet gerektirmez.

```bash
python -m unittest discover -s tests -p 'test_radar_v3.py' -v
python -m northlab_v3 discover --out northlab-v3-shadow.json
```

Çıktıda `review_queue_count` otomatik müşteri sayısı **değildir**. `qualified_lead_count=0` ve `contacts_sent=0` beklenen emniyet koşuludur. Tüm arama kaynakları çalışmazsa `SOURCE_FAILURE` ile iş akışı başarısız olur.

İncelemeyi yalnız yerel ortamda yap. Gerçek şirket telefon/e-posta/özel konuşma kayıtlarını açık GitHub'a veya CI artifact'ine ekleme:

```bash
python -m northlab_v3 review --input northlab-v3-shadow.json --reviews private-review.json --out private-evaluation.json
python -m northlab_v3 review --input northlab-v3-shadow.json --reviews private-review.json --confirmations private-confirmations.json --out private-evaluation.json
```

`private-review.json` JSON array öğeleri: `candidate_id`, `decision:"approve"`, `reviewer`, `reviewed_at`, `source_published_at`, `source_url`, `buyer_company`, `buyer_company_evidence_url`, `buyer_company_checked_directly:true`, `country:"KKTC"|"TR"`, `buyer_request_quote`, `request_is_external_contract:true`, `agency_eligible:true`, `source_publication_checked_directly:true`, `contact_checked_directly:true`, `contact_evidence_url`, `contact:{kind:"email"|"phone"|"website_contact",value:"..."}`.

`private-confirmations.json` JSON array öğeleri: `candidate_id`, `buyer_confirmed_open:true`, `replied_at`, `reviewed_by`, `reply_evidence_reference` (ör. `call-note:local-record-id`).

## Üretime geçiş için koşullar

- Bağımsız CI birim testleri ve **gerçek halka açık kaynak shadow çalışması** geçmeli.
- İlk kaynak yalnız Bing RSS. Tek kaynakla pazarın tamamı taranmış sayılmaz. İkinci bağımsız kaynak gerçek şartları doğrulanmadan eklenmeyecek.
- Son 14 gün için orijinal ilan tarihini doğrulayan gerçek örnekler bulunmalı; satıcı promosyonu, personel alımı, kapanmış ilan, yabancı ülke ve erişilemeyen platformlar elenmeli.
- En az bir alıcıdan gerçek güncel yanıt ve kanıt kaydı olmadan ticari fırsat sayısı sıfır kalmalı.
- Kaynak doğruluğu ve gerçek ortam testi geçmeden eski NorthLab `schedule` kapatılmaz, yeni zamanlayıcı açılmaz. Cutover yapılırken diğer marka iş akışlarının regresyon testleri ve geri dönüş prosedürü zorunludur.

**Sınır:** Bu, mimari değişimdir; müşteri bulduğunu kanıtlamaz. Halka açık arama motorunda indekslenmeyen LinkedIn/Facebook/WhatsApp özel taleplerini göremez. Bu yüzden veri kaynağı tedariki, yazılımdan bağımsız bir ticari gereksinimdir.
