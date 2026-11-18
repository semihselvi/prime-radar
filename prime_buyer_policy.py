"""Pure Prime buyer intent guards: extracted from V5.5 and V5 batch-quality code.

These are intentionally dependency-free so production buyer scanning does not
import or mutate any V5 runtime module. Changes require parity regressions.
"""
from __future__ import annotations
import re

TG_NON_PROPERTY_GOODS_RE = re.compile(
    r"(?:"
    r"\bробот[-\s]?пылесос\w*\b|\bпылесос\w*\b|\bшкольн\w*\s+форм\w*\b|"
    r"\bформ[ауые]\b.{0,45}\b(?:школ|сын|доч|ребен|ребён)\w*\b|"
    r"\bтелефон\w*\b|\bсмартфон\w*\b|\bноутбук\w*\b|\bкомпьютер\w*\b|"
    r"\bвелосипед\w*\b|\bколяск\w*\b|\bхолодильник\w*\b|\bстиральн\w*\s+машин\w*\b|"
    r"\bмебел\w*\b|\bдиван\w*\b|\bстол\w*\b|\bстул\w*\b|\bзеркал\w*\b|\bгримерн\w*\b|"
    r"\bкресл\w*\b|\bтелевизор\w*\b|"
    r"\brobot\s+vacuum\b|\bschool\s+uniform\b|\bphone\b|\blaptop\b|\bbicycle\b|"
    r"\bokul\s+formas[ıi]\b|\brobot\s+s[üu]p[üu]rge\b"
    r")",
    re.I | re.S,
)

_RU_PROPERTY_OBJECT = (
    r"(?:недвижимост\w*|квартир\w*|апартамент\w*|вилл\w*|"
    r"дом(?:\b|ом\b|у\b|е\b)|участ\w*|земл\w*|жиль[её]\w*|"
    r"[0-6]\s*\+\s*[0-3]|caesar\s+resort|royal\s+sun(?:\s+elite)?|"
    r"grand\s+sapphire|four\s+seasons|riverside\s+life|isatis|elysium)"
)

# A genuine property purchase overrides the goods guard ONLY when a property
# object is actually present. Previously "хочу купить" alone was enough, so
# flea-market requests such as "хочу купить столик" leaked into the buyer lane.
# Unit configs/projects are valid purchase objects too: "Куплю 1+1 в Royal Sun".
TG_DIRECT_PROPERTY_PURCHASE_RE = re.compile(
    rf"(?:"
    rf"\bкуплю\b.{{0,110}}\b{_RU_PROPERTY_OBJECT}\b|"
    rf"\b(?:хочу|хотим|планирую|планируем|рассматриваю|рассматриваем)\b.{{0,70}}"
    rf"\b(?:купить|покупк\w*)\b.{{0,100}}\b{_RU_PROPERTY_OBJECT}\b|"
    rf"\b(?:хочу|хотим|планирую|планируем|рассматриваю|рассматриваем)\b.{{0,70}}"
    rf"\b{_RU_PROPERTY_OBJECT}\b.{{0,100}}\b(?:купить|покупк\w*)\b|"
    r"\b(?:looking|planning|want(?:ing)?|ready|considering)\b.{0,60}\b(?:buy|buying|purchase)\b"
    r".{0,90}\b(?:property|apartment|flat|house|villa|studio|land)\b|"
    r"\b(?:sat[ıi]n\s+almak|almak)\b.{0,80}\b(?:daire|ev|villa|arsa|gayrimenkul|konut)\b"
    r")",
    re.I | re.S,
)


TG_PURCHASE_VERB_RE = re.compile(
    r"(?:"
    r"\bкуплю\b|\bкупить\b|\bпокупк\w*\b|"
    r"\b(?:buy|buying|purchase|purchasing)\b|"
    r"\b(?:sat[ıi]n\s+almak|almak|alacağım|alacagim|almak\s+istiyorum)\b"
    r")",
    re.I,
)

TG_PROPERTY_OBJECT_RE = re.compile(
    rf"(?:{_RU_PROPERTY_OBJECT}|"
    r"\b(?:property|apartment|flat|house|villa|studio|land|plot)\b|"
    r"\b(?:daire|ev|villa|arsa|gayrimenkul|konut|st[üu]dyo)\b"
    r")",
    re.I,
)


def _goods_is_purchase_target(text: str) -> bool:
    own = str(text or "")
    goods = TG_NON_PROPERTY_GOODS_RE.search(own)
    if not goods:
        return False

    verb = TG_PURCHASE_VERB_RE.search(own)
    if not verb:
        return False

    prop = TG_PROPERTY_OBJECT_RE.search(own)

    # Compare which object is linguistically closest to the purchase verb.
    # This fixes phrases such as:
    # "Куплю моющий робот пылесос для большой квартиры" where квартира is
    # merely usage context, not the thing being purchased.
    verb_center = (verb.start() + verb.end()) / 2
    goods_center = (goods.start() + goods.end()) / 2
    goods_distance = abs(goods_center - verb_center)

    if prop is None:
        return goods_distance <= 140

    prop_center = (prop.start() + prop.end()) / 2
    prop_distance = abs(prop_center - verb_center)

    return goods_distance + 4 < prop_distance


def is_nonproperty_goods_request(text: str) -> bool:
    own = " ".join(str(text or "").split())
    if not TG_NON_PROPERTY_GOODS_RE.search(own):
        return False

    # If the goods noun is the actual target of the purchase verb, incidental
    # housing words ("for a large apartment", "at home") must not override it.
    if _goods_is_purchase_target(own):
        return True

    return not TG_DIRECT_PROPERTY_PURCHASE_RE.search(own)

_WEB_RENTAL_RE = re.compile(
    r"(?:"
    r"\bfor\s+rent\b|\bflats?\s+for\s+rent\b|\bapartments?\s+for\s+rent\b|"
    r"\bhouses?\s+for\s+rent\b|\bmonthly\s+rent\b|\bper\s+month\b|"
    r"\bnot\s+negotiable\b.{0,80}\bper\s+month\b|"
    r"\bà\s+louer\b|\ba\s+louer\b|\bzu\s+mieten\b|\bmietwohnung\b|"
    r"\bаренд\w*\b|\bснять\b|\bсниму\b|\bkiralık\b|\bkiralam\w*\b"
    r")",
    re.I | re.S,
)

_WEB_LISTING_RE = re.compile(
    r"(?:"
    r"\bagency\s+report\b|\breal\s+estate\s+agency\b|\bestate\s+agent\b|"
    r"\bproperty\s+features\s*[:：]|\bvideo\s+walkthrough\s+available\b|"
    r"\bviews?\s+agency\s+report\b|\bnot\s+negotiable\b|"
    r"\bcovered\s+veranda\b|\binternal\s+area\b.{0,30}\bsqm\b|"
    r"\bcontact\s+(?:the\s+)?(?:agent|agency)\b|\bproperty\s+reference\b"
    r")",
    re.I | re.S,
)

# Expat.com's /housing/ area is a classifieds inventory surface, not a user
# discussion forum. It can contain sale/rent adverts whose page chrome mentions
# North Cyprus and whose numeric rent is mistaken for buyer budget.
def _web_listing_url(url: str) -> bool:
    low = str(url or "").casefold()
    if "expat.com/" in low and "/housing/" in low:
        return True
    return any(token in low for token in (
        "/flats-for-rent/", "/flat-for-rent/", "/apartments-for-rent/",
        "/apartment-for-rent/", "/houses-for-rent/", "/house-for-rent/",
        "/properties-for-rent/", "/property-for-rent/",
    ))

TG_BOT_AUTHOR_RE = re.compile(r"^@?[a-z0-9_]*bot$", re.I)

TG_STRONG_SUPPLY_RE = re.compile(
    r"(?:"
    r"\bсрочн\w*.{0,30}\bпродаж\w*\b|"
    r"\bнов\w*\s+объявлен\w*\b|"
    r"\bклиент\w*.{0,80}\b(?:нужно|надо|хочет|хотят)\b.{0,60}\bпродать\b|"
    r"\b(?:продажа|продаю|продаем|продаём|продать)\b.{0,70}\b(?:вилл\w*|квартир\w*|апартамент\w*|дом\w*|недвижимост\w*)\b|"
    r"\bpulsemarket\b|"
    r"\bбольше\s+фотографий\b|\bсмотреть\s+на\s+сайте\b|"
    r"\bподключить\s+алерт\w*\b|\bполучать\s+новые\s+объявлен\w*\b|"
    r"\bновое\s+объявление\b.{0,120}\b(?:цена|контакт)\s*[:：]"
    r")",
    re.I | re.S,
)

# Requests for a tradesperson/service often contain a property word later in the
# sentence ("plumber ... our apartment") and used to enter the buyer candidate net.
TG_SERVICE_REQUEST_RE = re.compile(
    r"(?:"
    r"\b(?:ищу|ищем|нужен|нужна|нужно)\b.{0,90}\b(?:сантехник\w*|электрик\w*|мастер\w*|"
    r"ремонтник\w*|клининг\w*|уборк\w*|риэлтор\w*|адвокат\w*)\b|"
    r"\b(?:looking\s+for|need)\b.{0,90}\b(?:plumber|electrician|handyman|repairman|cleaner|cleaning\s+service)\b|"
    r"\b(?:arıyorum|ariyorum|lazım|lazim)\b.{0,90}\b(?:tesisatçı|tesisatci|elektrikçi|elektrikci|usta|tamirci|temizlikçi|temizlikci)\b"
    r")",
    re.I | re.S,
)

# Public explicit names; no monkey-patching of historical modules.
WEB_RENTAL_RE = _WEB_RENTAL_RE
WEB_LISTING_RE = _WEB_LISTING_RE
web_listing_url = _web_listing_url
